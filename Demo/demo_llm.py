from __future__ import annotations
import code
import json
import os
from typing import List, Tuple

from dill.detect import code
from openai import OpenAI
import psycopg2  # only used for type hints / cursor usage
from pgvector.psycopg2 import register_vector

from Database_Code.embeddings import embed_text

import time

# OpenAI client + LLM call

def get_openai_client() -> OpenAI:
    """
    Create an OpenAI client from the OPENAI_API_KEY environment variable.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Put it in your .env file or environment variables."
        )
    return OpenAI(api_key=api_key)


def call_llm(prompt: str, model: str = "gpt-5-mini-2025-08-07") -> str:
    """
    Send a prompt to an LLM and return the model's text output.
    """
    client = get_openai_client()

    llm_start = time.time()
    resp = client.responses.create(
        model=model,
        input=prompt,
        max_output_tokens=1000
    )
    llm_time = time.time() - llm_start

    text = (resp.output_text or "").strip()
    if not text:
        text = "No text output returned by the model."

    print(f"LLM time: {llm_time:.2f}s")

    try:
        usage = getattr(resp, "usage", None)
        if usage:
            print(f"LLM input tokens: {getattr(usage, 'input_tokens', None)}")
            print(f"LLM output tokens: {getattr(usage, 'output_tokens', None)}")
            print(f"LLM total tokens: {getattr(usage, 'total_tokens', None)}")
    except Exception:
        print("Could not read LLM token usage.")

    return text


# -----------------------------
# Vector retrieval (pgvector)
# -----------------------------

RetrievedRow = Tuple[str, str, str, str]
# (instance_id, repo, problem_statement, patch)


def retrieve_topk(conn, code: str, error: str, query: str, k: int = 3) -> List[RetrievedRow]:
    """
    Retrieve the top-k nearest rows from swebench_data using pgvector.
    """
    retrieval_start = time.time()

    queries = generate_retrieval_queries(code, error)
    concat_queries = [
        error,
        f"Python error: {error}",
        code[:500],
        *queries
    ]

    print("\n=== Retrieval Queries ===")
    for i, q in enumerate(concat_queries, start=1):
        if q and q.strip():
            print(f"{i}. {q[:120]}")

    results = []

    sql = """
        SELECT instance_id, repo, problem_statement, patch
        FROM swebench_data
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
    """

    for q in concat_queries:
        if not q or not q.strip():
            continue

        q_emb = embed_text(q)
        q_vec = "[" + ",".join(map(str, q_emb)) + "]"

        with conn.cursor() as cur:
            query_start = time.time()
            cur.execute(sql, (q_vec, k))
            rows = cur.fetchall()
            query_time = time.time() - query_start

            print(f"Retrieved {len(rows)} rows in {query_time:.2f}s for query: {q[:80]!r}")
            results.extend(rows)

    unique = {r[0]: r for r in results}
    top_rows = list(unique.values())[:k]

    retrieval_time = time.time() - retrieval_start

    print("\n=== Retrieved Examples ===")
    for row in top_rows:
        print(f"INSTANCE_ID: {row[0]} | REPO: {row[1]}")

    print(f"Retrieval time: {retrieval_time:.2f}s")
    print(f"Unique retrieved rows: {len(unique)}")
    print(f"Top-k returned rows: {len(top_rows)}")

    return top_rows

def generate_retrieval_queries(code: str, error: str) -> list[str]:

    snippet = code[:1200] 

    prompt = f"""
You generate search queries for retrieving similar bugs from a dataset of GitHub issues.

Given:
- Python error message
- code snippet

Return EXACTLY a JSON array of 3 short strings.
Each string should be a GitHub-issue-style bug description (max 12 words).

Error:
{error}

Code snippet:
{snippet}
"""

    raw = call_llm(prompt)

    #parse raw 
    try:
        arr = json.loads(raw)
        if isinstance(arr, list):
            queries = [str(x).strip() for x in arr if str(x).strip()]
            return queries[:3]
    except json.JSONDecodeError:
        pass
        fallback = []
    if error:
                fallback.append(error)
                fallback.append(f"Python error: {error}")
    if code:
        fallback.append(code[:120])
    return fallback[:3]
# RAG answer function

def rag_answer(
    conn: psycopg2.extensions.connection, code: str, error: str,
    user_question: str,
    k: int = 5,
    model: str = "gpt-5-mini-2025-08-07",
) -> str:
 
    
    rows = retrieve_topk(conn, code, error, user_question, k=k)
    

    if not rows:
        # If retrieval returns nothing, still answer but admit no examples were found.
        prompt = f"""You are a coding assistant.

User question:
{user_question}

No retrieved examples were found in the database. Answer using general best practices.
"""
        return call_llm(prompt, model=model)

    # Build a readable context block from retrieved rows
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

    # Prompt with basic guardrails:
    # - Use the retrieved examples
    # - If unsure, say what is missing
    prompt = f"""
You are a coding assistant.

IMPORTANT:
- The retrieved examples below may contain unrelated bugs.
- The retrieved examples are provided to use as context for the answer if relevant.
- Do NOT answer issues inside the retrieved examples.
- Only answer the USER QUESTION.

========== RETRIEVED EXAMPLES ==========
{context}

========== USER QUESTION ==========
{user_question}

Provide an explanation of the issues, one best practice corrected code. 
"""
   
    return call_llm(prompt, model=model)