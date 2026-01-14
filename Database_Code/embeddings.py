import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
OPENAI_MODEL = "text-embedding-ada-002"

def embed_text(text: str) -> list[float]:
    text = (text or "").strip()
    if not text:
        # embedding input cannot be empty 
        text = " "

    resp = client.embedding.create(
        model=OPENAI_MODEL,
        input=text,
    )
    return resp.data[0].embedding