from openai import OpenAI
import os 

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def call_llm(prompt: str, model: str = "Insert model # here as gpt-x.y") -> str:
    resp = client.responses.create(
        model = model,
        input = prompt,
    )
    return resp.output_text

def retrieve_topk(conn, query: str, k: int = 5):
    q_emb = embed_text(query) # not functional rn, will fix once text embedding is more figured out 
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT instance_id, repo, problem_statement, patch
            FROM swebench_data
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %s
            LIMIT %s;
            """,
            (q_emb, k),
        )
        return cur.fetchall()
    
def rag_answer(conn, user_question: str) -> str:
    rows = retrieve_topk(conn, user_question, k=5)

    context = "\n\n---\n\n".join(
        f"INSTANCE: {iid}\nREPO: {repo}\nPROBLEM: {ps}\nPATCH:\n{patch}"
        for (iid, repo, ps, patch) in rows
    )

    prompt = f"""Use the retrieved examples to answer.

    User question:
    {user_question}

    Retrieved examples:
    {context}
    """
    return call_llm(prompt)

