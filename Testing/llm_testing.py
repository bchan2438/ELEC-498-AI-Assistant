from __future__ import annotations
import os
import re
from typing import List, Tuple

from openai import OpenAI
import psycopg2

from Database_Code.embeddings import embed_text

RAG_VERSION = "testing_retrieval_v4_repo_boost"


def get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Put it in your .env file or environment variables."
        )
    return OpenAI(api_key=api_key)


def call_llm(prompt: str, model: str = "gpt-5-2025-08-07") -> str:
    client = get_openai_client()

    resp = client.responses.create(
        model=model,
        input=prompt,
        max_output_tokens=3000,
        text={"format": {"type": "text"}}
    )

    # 1. Fast path
    text = getattr(resp, "output_text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()

    # 2. Structured fallback
    output = getattr(resp, "output", None)
    collected = []

    if output:
        for item in output:
            item_type = getattr(item, "type", None)

            if item_type == "message":
                content_list = getattr(item, "content", None) or []

                for content in content_list:
                    content_type = getattr(content, "type", None)

                    # Most common case
                    if content_type == "output_text":
                        content_text = getattr(content, "text", None)
                        if isinstance(content_text, str) and content_text.strip():
                            collected.append(content_text.strip())

                    # Extra-safe fallback
                    elif content_type == "text":
                        content_text = getattr(content, "text", None)
                        if isinstance(content_text, str) and content_text.strip():
                            collected.append(content_text.strip())

    if collected:
        return "\n\n".join(collected).strip()

    # 3. Last resort: inspect object fields as strings
    try:
        output_str = str(output)
        if output_str and "ResponseReasoningItem" not in output_str:
            return output_str.strip()
    except Exception:
        pass

    return "No text output returned by the model."

    # First try the convenience field
    text = getattr(resp, "output_text", None)
    if text and text.strip():
        return text.strip()

    # Fallback: walk through structured output safely
    output = getattr(resp, "output", None)
    if output:
        collected = []

        for item in output:
            item_type = getattr(item, "type", None)

            if item_type == "message":
                content_list = getattr(item, "content", []) or []

                for content in content_list:
                    content_type = getattr(content, "type", None)

                    if content_type in ("output_text", "text"):
                        content_text = getattr(content, "text", None)
                        if content_text:
                            collected.append(content_text)

        final_text = "\n".join(collected).strip()
        if final_text:
            return final_text

    return "No text output returned by the model."


def extract_error_type(error: str) -> str:
    if not error:
        return ""
    match = re.search(r"\b([A-Za-z]+Error)\b", error)
    return match.group(1) if match else ""


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z_]+", text.lower()))


def detect_repo_hints(text: str) -> set[str]:
    text_lower = text.lower()
    hints = set()

    mapping = {
        "django": "django/django",
        "pytest": "pytest-dev/pytest",
        "sphinx": "sphinx-doc/sphinx",
        "sympy": "sympy/sympy",
        "xarray": "pydata/xarray",
        "astropy": "astropy/astropy",
        "matplotlib": "matplotlib/matplotlib",
        "sklearn": "scikit-learn/scikit-learn",
        "scikit-learn": "scikit-learn/scikit-learn",
    }

    for key, repo in mapping.items():
        if key in text_lower:
            hints.add(repo)

    return hints


RetrievedRow = Tuple[str, str, str, str]


def retrieve_topk_debug(
    conn: psycopg2.extensions.connection,
    code: str,
    error: str,
    k: int = 5
):
    error_type = extract_error_type(error)

    query_text = f"""Python bug report

Error:
{error}

Code:
{code[:1500]}
""".strip()

    q_emb = embed_text(query_text)
    q_vec = "[" + ",".join(map(str, q_emb)) + "]"

    sql = """
        SELECT
            instance_id,
            repo,
            problem_statement,
            patch,
            embedding <=> %s AS distance
        FROM swebench_data
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> %s
        LIMIT %s;
    """

    with conn.cursor() as cur:
        cur.execute(sql, (q_vec, q_vec, 20))
        rows = cur.fetchall()

    repo_hints = detect_repo_hints(code + "\n" + error)
    error_words = tokenize(error)
    code_words = tokenize(code)

    scored_rows = []
    for row in rows:
        instance_id, repo, problem_statement, patch, distance = row
        ps = problem_statement or ""
        ps_lower = ps.lower()
        ps_words = tokenize(ps)

        rerank_bonus = 0.0

        if repo in repo_hints:
            rerank_bonus += 0.18

        if error_type and error_type.lower() in ps_lower:
            rerank_bonus += 0.08

        overlap_error = len(error_words & ps_words)
        overlap_code = len(code_words & ps_words)

        rerank_bonus += min(overlap_error * 0.02, 0.10)
        rerank_bonus += min(overlap_code * 0.01, 0.05)

        final_score = distance - rerank_bonus

        scored_rows.append((
            instance_id,
            repo,
            problem_statement,
            patch,
            distance,
            final_score
        ))

    scored_rows.sort(key=lambda x: x[5])
    return [(r[0], r[1], r[2], r[3], r[4]) for r in scored_rows[:k]]


def retrieve_topk(
    conn: psycopg2.extensions.connection,
    code: str,
    error: str,
    query: str,
    k: int = 5
) -> List[RetrievedRow]:
    rows = retrieve_topk_debug(conn, code, error, k=k)
    return [(r[0], r[1], r[2], r[3]) for r in rows]


def rag_answer(
    conn: psycopg2.extensions.connection,
    code: str,
    error: str,
    user_question: str,
    k: int = 5,
    model: str = "gpt-5-2025-08-07",
) -> str:
    rows = retrieve_topk(conn, code, error, user_question, k=k)

    context_blocks = []
    for (iid, repo, problem_statement, patch) in rows:
        block = (
            f"INSTANCE_ID: {iid}\n"
            f"REPO: {repo}\n"
            f"PROBLEM_STATEMENT:\n{problem_statement}\n\n"
            f"PATCH:\n{patch}"
        )
        context_blocks.append(block)

    context = "\n\n---\n\n".join(context_blocks)

    prompt = f"""You are a coding assistant helping debug Python and library/framework code.

Important rules:
- The retrieved examples may be useful, but some may still be imperfect matches.
- Use retrieved examples only if they help.
- Do not answer the retrieved examples themselves.
- Only answer the user's bug.

Your task:
1. Identify the most likely cause of the user's error.
2. Explain it clearly.
3. Suggest a concrete fix.
4. Provide one corrected code example if possible.

========== RETRIEVED EXAMPLES ==========
{context}

========== USER QUESTION ==========
{user_question}

Answer in this format:

Cause:
...

Why it happens:
...

Fix:
...

Corrected code:
...
"""

    answer = call_llm(prompt, model=model)
    return answer if answer else "No text output returned by the model."