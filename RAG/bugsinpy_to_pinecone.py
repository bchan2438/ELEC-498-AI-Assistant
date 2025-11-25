import os
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple
import openai
from pinecone import Pinecone, ServerlessSpec

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()  # Loads from .env file in the project root
except ImportError:
    pass  # python-dotenv not installed, skip .env loading

# Configuration
OPENAI_MODEL = "text-embedding-ada-002"
PINECONE_INDEX_NAME = "bugsinpy-bug-fixes"
EMBEDDING_DIMENSION = 1536  # OpenAI ada-002 dimension
MAX_TOKENS = 8000  # ada-002 limit is 8192, use 8000 for safety
# Rough estimate: 1 token ≈ 4 characters
MAX_CHARACTERS = MAX_TOKENS * 4

# Initialize and return OpenAI client.
def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    return openai.OpenAI(api_key=api_key)

# Initialize Pinecone and return index.
def get_pinecone_index(index_name: str):
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        raise ValueError("PINECONE_API_KEY environment variable not set")
    
    pc = Pinecone(api_key=api_key)
    
    # Create index if it doesn't exist
    if index_name not in [idx.name for idx in pc.list_indexes()]:
        pc.create_index(
            name=index_name,
            dimension=EMBEDDING_DIMENSION,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1")
        )
    
    return pc.Index(index_name)

# Get list of project names from BugsInPy.
def get_bugsinpy_projects(bugsinpy_path: str) -> List[str]:
    projects_path = Path(bugsinpy_path) / "projects"
    if not projects_path.exists():
        raise FileNotFoundError(f"BugsInPy projects directory not found at {projects_path}")
    
    projects = [d.name for d in projects_path.iterdir() if d.is_dir()]
    return projects

# Checkout a bug version (0=buggy, 1=fixed) and return the path.
def checkout_bug_version(project_name: str, bug_id: int, version: int, 
                        bugsinpy_path: str, workspace: str) -> str:
    version_value = "0" if version == 0 else "1"
    # Use absolute path for checkout directory
    checkout_path = os.path.abspath(os.path.join(workspace, f"{project_name}_bug{bug_id}_v{version}"))
    
    # Use absolute path to bugsinpy-checkout command
    checkout_cmd = os.path.abspath(os.path.join(bugsinpy_path, "framework", "bin", "bugsinpy-checkout"))
    bugsinpy_abs_path = os.path.abspath(bugsinpy_path)
    
    # On Windows, use Git Bash to run shell scripts
    if os.name == 'nt':  # Windows
        # Try to find Git Bash
        git_bash_paths = [
            r"C:\Program Files\Git\bin\bash.exe",
            r"C:\Program Files (x86)\Git\bin\bash.exe",
        ]
        bash_exe = None
        for path in git_bash_paths:
            if os.path.exists(path):
                bash_exe = path
                break
        
        if not bash_exe:
            raise FileNotFoundError("Git Bash not found. Please install Git for Windows.")
        
        # Verify bash executable exists
        if not os.path.exists(bash_exe):
            raise FileNotFoundError(f"Git Bash executable not found at: {bash_exe}")
        
        # Convert Windows paths to forward slashes for bash
        checkout_cmd_bash = checkout_cmd.replace("\\", "/")
        checkout_path_bash = checkout_path.replace("\\", "/")
        bugsinpy_abs_path_bash = bugsinpy_abs_path.replace("\\", "/")
        
        # Verify paths exist before running
        if not os.path.exists(checkout_cmd):
            raise FileNotFoundError(f"bugsinpy-checkout not found at: {checkout_cmd}")
        
        # Use raw string for bash executable path to handle spaces
        cmd_args = [bash_exe, checkout_cmd_bash, "-p", project_name, "-v", version_value, 
                    "-i", str(bug_id), "-w", checkout_path_bash]
        
        # Debug output to see what's being executed
        print(f"DEBUG: Bash exe: {bash_exe}")
        print(f"DEBUG: Script: {checkout_cmd}")
        print(f"DEBUG: Command: {' '.join(cmd_args)}")
        
        try:
            result = subprocess.run(
                cmd_args,
                check=True,
                cwd=bugsinpy_abs_path_bash,
                capture_output=True,
                text=True
            )
        except subprocess.CalledProcessError as e:
            error_output = e.stderr if e.stderr else e.stdout if e.stdout else "No error output"
            raise RuntimeError(
                f"bugsinpy-checkout failed with exit code {e.returncode}.\n"
                f"Command: {' '.join(cmd_args)}\n"
                f"Error output: {error_output}"
            ) from e
        except FileNotFoundError as e:
            error_msg = (
                f"Failed to execute command.\n"
                f"Bash executable: {bash_exe} (exists: {os.path.exists(bash_exe)})\n"
                f"Script path: {checkout_cmd} (exists: {os.path.exists(checkout_cmd)})\n"
                f"Command args: {cmd_args}\n"
                f"Working dir: {bugsinpy_abs_path_bash}\n"
                f"Original error: {e}"
            )
            raise FileNotFoundError(error_msg) from e
    else:
        subprocess.run(
            [checkout_cmd, "-p", project_name, "-v", version_value, 
             "-i", str(bug_id), "-w", checkout_path],
            check=True,
            cwd=bugsinpy_abs_path,
            capture_output=True
        )
    return checkout_path


# Get list of files that changed between buggy and fixed versions.
def get_changed_files(buggy_path: str, fixed_path: str) -> List[str]:
    changed_files = []
    
    buggy_path_obj = Path(buggy_path)
    fixed_path_obj = Path(fixed_path)
    
    if not buggy_path_obj.exists() or not fixed_path_obj.exists():
        return changed_files
    
    # Find all Python files in both directories
    buggy_files = {f.relative_to(buggy_path_obj): f 
                   for f in buggy_path_obj.rglob("*.py")}
    fixed_files = {f.relative_to(fixed_path_obj): f 
                  for f in fixed_path_obj.rglob("*.py")}
    
    # Find files that exist in both or were added/modified
    all_files = set(buggy_files.keys()) | set(fixed_files.keys())
    
    for rel_path in all_files:
        buggy_file = buggy_files.get(rel_path)
        fixed_file = fixed_files.get(rel_path)
        
        if buggy_file and fixed_file:
            buggy_content = buggy_file.read_text(encoding='utf-8', errors='ignore')
            fixed_content = fixed_file.read_text(encoding='utf-8', errors='ignore')
            if buggy_content != fixed_content:
                changed_files.append(str(rel_path))
        elif fixed_file:
            changed_files.append(str(rel_path))
    
    return changed_files

# Read file content.
def get_file_content(file_path: str) -> str:
    return Path(file_path).read_text(encoding='utf-8', errors='ignore')

# Create a bug/fix pair text and metadata from checked out versions.
def create_bug_fix_pair(project_name: str, bug_id: int, buggy_path: str, 
                       fixed_path: str) -> Tuple[str, Dict]:
    changed_files = get_changed_files(buggy_path, fixed_path)
    
    if not changed_files:
        return None, None
    
    buggy_path_obj = Path(buggy_path)
    fixed_path_obj = Path(fixed_path)
    
    bug_code = []
    fix_code = []
    
    for rel_path in changed_files:
        buggy_file = buggy_path_obj / rel_path
        fixed_file = fixed_path_obj / rel_path
        
        if buggy_file.exists():
            bug_code.append(f"File: {rel_path}\n{get_file_content(str(buggy_file))}")
        if fixed_file.exists():
            fix_code.append(f"File: {rel_path}\n{get_file_content(str(fixed_file))}")
    
    bug_text = "\n\n---\n\n".join(bug_code)
    fix_text = "\n\n---\n\n".join(fix_code)
    
    combined_text = f"Bug Code:\n{bug_text}\n\n---\n\nFixed Code:\n{fix_text}"
    
    metadata = {
        "project": project_name,
        "bug_id": bug_id,
        "changed_files": ",".join(changed_files),
        "num_files": len(changed_files)
    }
    
    return combined_text, metadata

# Truncate text to fit within token limits.
def truncate_text(text: str, max_chars: int = MAX_CHARACTERS) -> str:
    """Truncate text to fit within embedding model token limits."""
    if len(text) <= max_chars:
        return text
    # Truncate and add indicator
    return text[:max_chars - 50] + "\n\n[Text truncated due to length limit...]"

# Generate embedding for text using OpenAI.
def generate_embedding(text: str, client: openai.OpenAI) -> List[float]:
    # Truncate text if too long
    truncated_text = truncate_text(text)
    if len(text) > len(truncated_text):
        print(f"  Warning: Text truncated from {len(text)} to {len(truncated_text)} characters")
    
    response = client.embeddings.create(
        model=OPENAI_MODEL,
        input=truncated_text
    )
    return response.data[0].embedding

# Insert embedding into Pinecone index.
def upsert_to_pinecone(index, vector_id: str, embedding: List[float], metadata: Dict):
    index.upsert(vectors=[{
        "id": vector_id,
        "values": embedding,
        "metadata": metadata
    }])

# Process a single bug: checkout, create pair, embed, and insert.
def process_bug(project_name: str, bug_id: int, bugsinpy_path: str, 
               workspace: str, openai_client: openai.OpenAI, 
               pinecone_index):
    print(f"Processing {project_name} bug {bug_id}...")
    buggy_path = checkout_bug_version(project_name, bug_id, 0, bugsinpy_path, workspace)
    fixed_path = checkout_bug_version(project_name, bug_id, 1, bugsinpy_path, workspace)
    
    pair_text, metadata = create_bug_fix_pair(project_name, bug_id, buggy_path, fixed_path)
    if not pair_text:
        print(f"  No changes found, skipping")
        return
    
    print(f"  Generating embedding...")
    embedding = generate_embedding(pair_text, openai_client)
    vector_id = f"{project_name}_bug{bug_id}"
    upsert_to_pinecone(pinecone_index, vector_id, embedding, metadata)
    print(f"  Inserted into Pinecone: {vector_id}")

# Main function to process BugsInPy dataset.
def main():
    print("Initializing...")
    bugsinpy_path = os.getenv("BUGSINPY_PATH", "./BugsInPy")
    workspace = os.getenv("BUGSINPY_WORKSPACE", "./bugsinpy_workspace")
    bug_ids_str = os.getenv("BUG_IDS", "")  # Comma-separated bug IDs
    
    os.makedirs(workspace, exist_ok=True)
    
    openai_client = get_openai_client()
    pinecone_index = get_pinecone_index(PINECONE_INDEX_NAME)
    
    projects = get_bugsinpy_projects(bugsinpy_path)
    bug_ids = [int(x.strip()) for x in bug_ids_str.split(",") if x.strip()] if bug_ids_str else []
    
    print(f"Found {len(projects)} projects, processing {len(bug_ids)} bug(s) per project\n")
    
    for project in projects:
        for bug_id in bug_ids:
            process_bug(project, bug_id, bugsinpy_path, workspace, 
                       openai_client, pinecone_index)
    
    print("\nComplete")


if __name__ == "__main__":
    main()

