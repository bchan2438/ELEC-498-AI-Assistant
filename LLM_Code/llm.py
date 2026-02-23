from __future__ import annotations

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


def retrieve_topk(conn, query: str, k: int = 3) -> List[RetrievedRow]:
    """
    Retrieve the top-k nearest rows from swebench_data using pgvector.

    Requirements:
    - swebench_data.embedding must be a pgvector column (VECTOR type)
    - pgvector extension must be installed: CREATE EXTENSION vector;
    """
    
    # 1) Convert query text to embedding vector (Python list[float])
    q_emb = embed_text(query)
    

    # code was taking q_emb as a numeric array, so this manually casts to vector 
    q_vec = "[" + ",".join(map(str, q_emb)) + "]"

    # 2) Run nearest-neighbor search in SQL
    # '<=>': pgvector distance operator (depends on your index/operator class)
    sql = """
        SELECT instance_id, repo, problem_statement, patch
        FROM swebench_data
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> %s
        LIMIT %s;
    """

    with conn.cursor() as cur:
        cur.execute(sql, (q_vec, k))
        rows = cur.fetchall()

    return rows

# RAG answer function

def rag_answer(
    conn: psycopg2.extensions.connection,
    user_question: str,
    k: int = 5,
    model: str = "gpt-5-mini-2025-08-07",
) -> str:
    """
    Main RAG entry point:
    - Retrieve top-k similar examples
    - Build a prompt that includes those examples
    - Ask the LLM for an answer grounded in retrieved context
    """
    
    rows = retrieve_topk(conn, user_question, k=k)
    

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
- They are provided only as patterns.
- Do NOT answer issues inside the retrieved examples.
- Only answer the USER QUESTION.

========== RETRIEVED EXAMPLES ==========
{context}

========== USER QUESTION ==========
{user_question}

Provide an explanation of the issues, one best practice corrected code. 
"""
   
    return call_llm(prompt, model=model)



