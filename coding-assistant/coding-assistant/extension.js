const vscode = require('vscode');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');

let sidebarProvider;

function activate(context) {
  sidebarProvider = new SidebarProvider(context.extensionUri);

  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(
      'codingAssistant.sidebarView',
      sidebarProvider
    )
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('codingAssistant.runFile', () => {
      runActiveFile();
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('codingAssistant.askLLM', () => {
      askLLMManually();
    })
  );
}

function deactivate() {}

// ─── Run Logic ───────────────────────────────────────────────────────────────

function runActiveFile() {
  const editor = vscode.window.activeTextEditor;

  if (!editor) {
    vscode.window.showErrorMessage('Coding Assistant: No active file open.');
    return;
  }

  const filePath = editor.document.uri.fsPath;

  if (path.extname(filePath).toLowerCase() !== '.py') {
    vscode.window.showErrorMessage('Coding Assistant: Active file is not a Python file (.py).');
    return;
  }

  editor.document.save().then(() => {
    const cwd = path.dirname(filePath);
    const filename = path.basename(filePath);

    sidebarProvider?.startRun(filename);

    const proc = spawn('python3', [filePath], { cwd });
    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (data) => {
      const chunk = data.toString();
      stdout += chunk;
      sidebarProvider?.appendOutput(chunk);
    });

    proc.stderr.on('data', (data) => {
      const chunk = data.toString();
      stderr += chunk;
      sidebarProvider?.appendError(chunk);
    });

    proc.on('close', (code) => {
      if (code !== 0 && stderr) {
        const snippets = parseTraceback(stderr, filePath);
        sidebarProvider?.finishRun(code, snippets);
        runLLMPipeline(filePath, stderr, snippets);
      } else {
        sidebarProvider?.finishRun(code, []);
      }
    });

    proc.on('error', (err) => {
      if (err.code === 'ENOENT') {
        const fallback = spawn('python', [filePath], { cwd });

        fallback.stdout.on('data', (data) => {
          const chunk = data.toString();
          stdout += chunk;
          sidebarProvider?.appendOutput(chunk);
        });

        fallback.stderr.on('data', (data) => {
          const chunk = data.toString();
          stderr += chunk;
          sidebarProvider?.appendError(chunk);
        });

        fallback.on('close', (code) => {
          if (code !== 0 && stderr) {
            const snippets = parseTraceback(stderr, filePath);
            sidebarProvider?.finishRun(code, snippets);
            runLLMPipeline(filePath, stderr, snippets);
          } else {
            sidebarProvider?.finishRun(code, []);
          }
        });

        fallback.on('error', () => {
          const msg = 'Could not find Python. Make sure Python is installed and on your PATH.';
          vscode.window.showErrorMessage(msg);
          sidebarProvider?.appendError(msg);
          sidebarProvider?.finishRun(1, []);
        });
      } else {
        const msg = `Error starting Python: ${err.message}`;
        vscode.window.showErrorMessage(msg);
        sidebarProvider?.appendError(msg);
        sidebarProvider?.finishRun(1, []);
      }
    });
  });
}

// ─── Manual LLM Trigger ──────────────────────────────────────────────────────

function askLLMManually() {
  const editor = vscode.window.activeTextEditor;

  if (!editor) {
    vscode.window.showErrorMessage('Coding Assistant: No active file open.');
    return;
  }

  const filePath = editor.document.uri.fsPath;

  if (path.extname(filePath).toLowerCase() !== '.py') {
    vscode.window.showErrorMessage('Coding Assistant: Active file is not a Python file (.py).');
    return;
  }

  editor.document.save().then(() => {
    // No stderr — pass empty string and no line numbers
    runLLMPipeline(filePath, '', []);
  });
}

// ─── LLM Pipeline ─────────────────────────────────────────────────────────────

/**
 * 1. Copies the user's code into a temp .txt file
 * 2. Calls main.py (in the repo root) passing the temp file path and the error
 * 3. Streams main.py's stdout back to the sidebar as the LLM response
 */
function runLLMPipeline(filePath, stderr, snippets) {
  sidebarProvider?.startLLM();

  // Write the code to a temp text file
  const code = fs.readFileSync(filePath, 'utf8');
  const timestamp = Date.now();
  const tmpCodeFile   = path.join(os.tmpdir(), `coding_assistant_code_${timestamp}.txt`);
  const tmpOutputFile = path.join(os.tmpdir(), `coding_assistant_out_${timestamp}.txt`);
  fs.writeFileSync(tmpCodeFile, code, 'utf8');

  // Extract just the line numbers from the parsed snippets
  const errorLines = snippets.map(s => s.line).join(',');

  // main.py lives one level up from the extension folder (repo root)
  const mainPy = path.join(__dirname, '..', '..', 'Main.py');

  if (!fs.existsSync(mainPy)) {
    sidebarProvider?.appendLLM(`[Coding Assistant] Could not find main.py at:\n${mainPy}\n`);
    sidebarProvider?.finishLLM();
    return;
  }

  // Invoke: python3 main.py <code_txt> <error> <line_numbers> <output_file>
  // main.py reads sys.argv[1..4], runs the LLM, writes result to sys.argv[4]
  // Use the venv Python if it exists, otherwise fall back to system python3
  const venvPython = path.join(__dirname, '..', '..', '.venv', 'bin', 'python3');
  const pythonCmd  = fs.existsSync(venvPython) ? venvPython : 'python3';

  const llmProc = spawn(pythonCmd, [mainPy, tmpCodeFile, stderr, errorLines, tmpOutputFile]);

  llmProc.stderr.on('data', (data) => {
    sidebarProvider?.appendLLM(`[main.py error] ${data.toString()}`);
  });

  llmProc.on('close', () => {
    // Read the output file that main.py wrote to
    try {
      if (fs.existsSync(tmpOutputFile)) {
        const result = fs.readFileSync(tmpOutputFile, 'utf8');
        sidebarProvider?.appendLLM(result);
      } else {
        sidebarProvider?.appendLLM('[Coding Assistant] main.py did not produce an output file.');
      }
    } catch (err) {
      sidebarProvider?.appendLLM(`[Coding Assistant] Could not read output file: ${err.message}`);
    }

    // Clean up temp files
    try { fs.unlinkSync(tmpCodeFile); }   catch (_) {}
    try { fs.unlinkSync(tmpOutputFile); } catch (_) {}

    sidebarProvider?.finishLLM();
  });

  llmProc.on('error', (err) => {
    sidebarProvider?.appendLLM(`[Coding Assistant] Failed to run main.py: ${err.message}\n`);
    sidebarProvider?.finishLLM();
  });
}

// ─── Traceback Parser ─────────────────────────────────────────────────────────

function parseTraceback(stderr, filePath) {
  const snippets = [];
  const lines = stderr.split('\n');
  const seen = new Set();
  const frameRegex = /^\s+File "(.+?)", line (\d+)/;

  for (let i = 0; i < lines.length; i++) {
    const match = lines[i].match(frameRegex);
    if (!match) continue;

    const frameFile = match[1];
    const lineNum = parseInt(match[2], 10);

    if (path.resolve(frameFile) !== path.resolve(filePath)) continue;

    const key = `${frameFile}:${lineNum}`;
    if (seen.has(key)) continue;
    seen.add(key);

    try {
      const src = fs.readFileSync(frameFile, 'utf8').split('\n');
      const start = Math.max(0, lineNum - 3);
      const end   = Math.min(src.length, lineNum + 2);

      const codeLines = [];
      for (let l = start; l < end; l++) {
        codeLines.push({
          number: l + 1,
          text: src[l],
          isError: l + 1 === lineNum,
        });
      }

      snippets.push({ file: path.basename(frameFile), line: lineNum, codeLines });
    } catch (_) {}
  }

  return snippets;
}

// ─── Sidebar Webview Provider ─────────────────────────────────────────────────

class SidebarProvider {
  constructor(extensionUri) {
    this._extensionUri = extensionUri;
    this._view = null;
  }

  resolveWebviewView(webviewView) {
    this._view = webviewView;
    webviewView.webview.options = { enableScripts: true };
    webviewView.webview.html = this._getHtml();

    webviewView.webview.onDidReceiveMessage((message) => {
      if (message.command === 'runFile') {
        runActiveFile();
      } else if (message.command === 'askLLM') {
        askLLMManually();
      } else if (message.command === 'clearOutput') {
        this._post({ command: 'clear' });
      }
    });
  }

  startRun(filename)          { this._post({ command: 'startRun', filename }); }
  appendOutput(text)          { this._post({ command: 'stdout', text }); }
  appendError(text)           { this._post({ command: 'stderr', text }); }
  finishRun(exitCode, snippets = []) { this._post({ command: 'finishRun', exitCode, snippets }); }
  startLLM()                  { this._post({ command: 'startLLM' }); }
  appendLLM(text)             { this._post({ command: 'llmChunk', text }); }
  finishLLM()                 { this._post({ command: 'finishLLM' }); }

  _post(message) { this._view?.webview.postMessage(message); }

  _getHtml() {
    return /* html */ `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Coding Assistant</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: var(--vscode-font-family);
    font-size: var(--vscode-font-size);
    color: var(--vscode-foreground);
    background: var(--vscode-sideBar-background);
    padding: 12px;
    display: flex;
    flex-direction: column;
    height: 100vh;
    gap: 10px;
    overflow-y: auto;
  }

  h2 {
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--vscode-sideBarTitle-foreground);
  }

  .section-label {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--vscode-descriptionForeground);
  }

  .btn-row { display: flex; gap: 6px; }

  button {
    flex: 1;
    padding: 6px 10px;
    border: none;
    border-radius: 3px;
    cursor: pointer;
    font-size: 12px;
    font-family: inherit;
  }

  #btn-run {
    background: var(--vscode-button-background);
    color: var(--vscode-button-foreground);
  }
  #btn-run:hover { background: var(--vscode-button-hoverBackground); }
  #btn-run:disabled { opacity: 0.5; cursor: not-allowed; }

  #btn-clear {
    background: var(--vscode-button-secondaryBackground);
    color: var(--vscode-button-secondaryForeground);
  }
  #btn-clear:hover { background: var(--vscode-button-secondaryHoverBackground); }

  #btn-ask {
    background: #4a2d6e;
    color: #e0b8ff;
    flex: 1;
  }
  #btn-ask:hover { background: #5a3d7e; }
  #btn-ask:disabled { opacity: 0.5; cursor: not-allowed; }

  #status {
    font-size: 11px;
    color: var(--vscode-descriptionForeground);
    min-height: 15px;
  }
  #status.success { color: #4ec94e; }
  #status.error   { color: var(--vscode-errorForeground); }
  #status.running { color: var(--vscode-progressBar-background); }

  .output-box {
    overflow-y: auto;
    background: var(--vscode-terminal-background, #1e1e1e);
    border: 1px solid var(--vscode-panel-border);
    border-radius: 4px;
    padding: 8px;
    max-height: 180px;
  }

  .output-box pre {
    font-family: var(--vscode-editor-font-family, 'Courier New', monospace);
    font-size: 12px;
    white-space: pre-wrap;
    word-break: break-all;
    line-height: 1.5;
  }

  .stdout { color: var(--vscode-terminal-foreground, #cccccc); }
  .stderr { color: #f48771; }
  .placeholder { color: var(--vscode-descriptionForeground); font-style: italic; }

  /* Code snippets */
  #snippets { display: flex; flex-direction: column; gap: 8px; }

  .snippet {
    border: 1px solid #f48771;
    border-radius: 4px;
    overflow: hidden;
    font-family: var(--vscode-editor-font-family, monospace);
    font-size: 12px;
  }
  .snippet-header {
    background: #3a1a1a;
    color: #f48771;
    padding: 4px 8px;
    font-size: 11px;
  }
  .snippet table { width: 100%; border-collapse: collapse; }
  .snippet tr { line-height: 1.6; }
  .snippet td.ln {
    width: 36px; text-align: right; padding: 0 8px;
    color: #666; user-select: none; border-right: 1px solid #333;
  }
  .snippet td.code { padding: 0 8px; white-space: pre; color: #cccccc; }
  .snippet tr.error-line { background: #3a1a1a; }
  .snippet tr.error-line td.ln { color: #f48771; }
  .snippet tr.error-line td.code { color: #f48771; font-weight: bold; }

  /* LLM section */
  #llm-section { display: flex; flex-direction: column; gap: 6px; }

  #llm-status {
    font-size: 11px;
    color: var(--vscode-descriptionForeground);
    min-height: 15px;
  }
  #llm-status.thinking { color: #c586c0; }
  #llm-status.done     { color: #4ec94e; }

  #llm-box {
    overflow-y: auto;
    background: #1a1a2e;
    border: 1px solid #4a4a7a;
    border-radius: 4px;
    padding: 8px;
    max-height: 220px;
    display: none;
  }

  #llm-output {
    font-family: var(--vscode-font-family);
    font-size: 12px;
    white-space: pre-wrap;
    word-break: break-word;
    line-height: 1.6;
    color: #ce9178;
  }
</style>
</head>
<body>

<h2>Coding Assistant</h2>

<div class="btn-row">
  <button id="btn-run">▶ Run Active File</button>
  <button id="btn-clear">✕ Clear</button>
</div>
<div class="btn-row">
  <button id="btn-ask">⚡ Ask AI About This File</button>
</div>

<div id="status">Open a .py file and press Run.</div>

<div class="section-label">Output</div>
<div class="output-box">
  <pre id="output"><span class="placeholder">Output will appear here...</span></pre>
</div>

<div id="snippets"></div>

<div id="llm-section">
  <div class="section-label">AI Suggestion</div>
  <div id="llm-status"></div>
  <div id="llm-box">
    <pre id="llm-output"></pre>
  </div>
</div>

<script>
  const vscode = acquireVsCodeApi();
  const output    = document.getElementById('output');
  const snippets  = document.getElementById('snippets');
  const status    = document.getElementById('status');
  const btnRun    = document.getElementById('btn-run');
  const llmBox    = document.getElementById('llm-box');
  const llmOut    = document.getElementById('llm-output');
  const llmStatus = document.getElementById('llm-status');
  let firstChunk  = true;

  btnRun.addEventListener('click', () => vscode.postMessage({ command: 'runFile' }));
  document.getElementById('btn-ask').addEventListener('click', () => vscode.postMessage({ command: 'askLLM' }));
  document.getElementById('btn-clear').addEventListener('click', () => vscode.postMessage({ command: 'clearOutput' }));

  window.addEventListener('message', ({ data: msg }) => {
    switch (msg.command) {

      case 'askLLM':
        vscode.postMessage({ command: 'askLLM' });
        break;

      case 'startRun':
        firstChunk = true;
        output.innerHTML = '';
        snippets.innerHTML = '';
        llmBox.style.display = 'none';
        llmOut.textContent = '';
        llmStatus.textContent = '';
        llmStatus.className = '';
        btnRun.disabled = true;
        document.getElementById('btn-ask').disabled = true;
        status.className = 'running';
        status.textContent = 'Running: ' + msg.filename + '…';
        break;

      case 'stdout':
        if (firstChunk) { output.innerHTML = ''; firstChunk = false; }
        appendTo(output, msg.text, 'stdout');
        scrollBottom('output');
        break;

      case 'stderr':
        if (firstChunk) { output.innerHTML = ''; firstChunk = false; }
        appendTo(output, msg.text, 'stderr');
        scrollBottom('output');
        break;

      case 'finishRun':
        btnRun.disabled = false;
        document.getElementById('btn-ask').disabled = false;
        if (msg.exitCode === 0) {
          status.className = 'success';
          status.textContent = '✓ Finished successfully (exit 0)';
        } else {
          status.className = 'error';
          status.textContent = '✗ Exited with code ' + msg.exitCode;
          renderSnippets(msg.snippets || []);
        }
        break;

      // ── LLM events ──
      case 'startLLM':
        llmStatus.className = 'thinking';
        llmStatus.textContent = '⏳ Asking AI for suggestions…';
        llmBox.style.display = 'block';
        llmOut.textContent = '';
        break;

      case 'llmChunk':
        llmOut.textContent += msg.text;
        scrollBottom('llm-box');
        break;

      case 'finishLLM':
        llmStatus.className = 'done';
        llmStatus.textContent = '✓ AI response ready';
        break;

      case 'clear':
        output.innerHTML = '<span class="placeholder">Output will appear here...</span>';
        snippets.innerHTML = '';
        llmBox.style.display = 'none';
        llmOut.textContent = '';
        llmStatus.textContent = '';
        llmStatus.className = '';
        status.className = '';
        status.textContent = 'Open a .py file and press Run.';
        break;
    }
  });

  function appendTo(el, text, cls) {
    const span = document.createElement('span');
    span.className = cls;
    span.textContent = text;
    el.appendChild(span);
  }

  function scrollBottom(id) {
    const el = document.getElementById(id);
    if (el) el.scrollTop = el.scrollHeight;
  }

  function renderSnippets(data) {
    if (!data.length) return;
    data.forEach(({ file, line, codeLines }) => {
      const div = document.createElement('div');
      div.className = 'snippet';

      const header = document.createElement('div');
      header.className = 'snippet-header';
      header.textContent = file + ' — error on line ' + line;
      div.appendChild(header);

      const table = document.createElement('table');
      codeLines.forEach(({ number, text, isError }) => {
        const tr = document.createElement('tr');
        if (isError) tr.className = 'error-line';

        const tdLn = document.createElement('td');
        tdLn.className = 'ln';
        tdLn.textContent = number;

        const tdCode = document.createElement('td');
        tdCode.className = 'code';
        tdCode.textContent = text;

        tr.appendChild(tdLn);
        tr.appendChild(tdCode);
        table.appendChild(tr);
      });

      div.appendChild(table);
      snippets.appendChild(div);
    });
  }
</script>
</body>
</html>`;
  }
}

module.exports = { activate, deactivate };