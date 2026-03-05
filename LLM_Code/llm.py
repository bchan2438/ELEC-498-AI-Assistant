from __future__ import annotations
import json
import os
from typing import List, Tuple

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

    Note:
    - This uses the OpenAI Responses API.
    - 'resp.output_text' is a convenience property that returns the concatenated text output.
    """
    
    client = get_openai_client()

    resp = client.responses.create(
        model=model,
        input=prompt,
        max_output_tokens=1000
    )

    # output_text is typically present for text-only requests
    text = (resp.output_text or "").strip()
    if not text:
        # Fallback: return something safe instead of empty
        return "No text output returned by the model."
    
    return text


# -----------------------------
# Vector retrieval (pgvector)
# -----------------------------

RetrievedRow = Tuple[str, str, str, str]
# (instance_id, repo, problem_statement, patch)


def retrieve_topk(conn, code: str, error:str, query: str, k: int = 3) -> List[RetrievedRow]:
    """
    Retrieve the top-k nearest rows from swebench_data using pgvector.

    Requirements:
    - swebench_data.embedding must be a pgvector column (VECTOR type)
    - pgvector extension must be installed: CREATE EXTENSION vector;
    """
    queries = generate_retrieval_queries(code, error)
    concat_queries= [
        error,
        f"Python error: {error}",
        code[:500],  # small snippet
        *queries
    ]
    

    results = []

    sql = """
        SELECT instance_id, repo, problem_statement, patch
        FROM swebench_data
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> %s
        LIMIT %s;
    """

    for q in concat_queries:
        q_emb = embed_text(q)
        q_vec = "[" + ",".join(map(str, q_emb)) + "]"

        with conn.cursor() as cur:
            cur.execute(sql, (q_vec, k))
            rows = cur.fetchall()
            results.extend(rows)

    # remove duplicates using instance_id
    unique = {r[0]: r for r in results}

    return list(unique.values())[:k]

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
    if error:
        return [""]

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



