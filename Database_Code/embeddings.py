import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# open ai model being used
OPENAI_MODEL = "text-embedding-3-small"

def embed_text(text: str) -> list[float]:

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    
    client = OpenAI(api_key=api_key)

    text = (text or "").strip()
    if not text:
        # embedding input cannot be empty 
        text = " "

    resp = client.embeddings.create(
        model=OPENAI_MODEL,
        input=text,
    )
    embedding = resp.data[0].embedding
    return embedding