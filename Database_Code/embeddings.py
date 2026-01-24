import os
from openai import OpenAI
from dotenv import load_dotenv
import tiktoken
load_dotenv()

# open ai model being used
OPENAI_MODEL = "text-embedding-3-small"

MAX_TOKENS = 8000
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY not set")
    
client = OpenAI(api_key=api_key)

enc = tiktoken.get_encoding("cl100k_base")

def truncate(text: str, max_tokens: int = MAX_TOKENS) -> str:
    
    text = (text or "").strip()
    if not text:
        # embedding input cannot be empty 
        text = " "
    tokens = enc.encode(text)
    if len(tokens) <= max_tokens:
        return text

    return enc.decode(tokens[:max_tokens])


def embed_text(text: str) -> list[float]:
    text = truncate(text)
    
    resp = client.embeddings.create(
        model=OPENAI_MODEL,
        input=text,
    )
    embedding = resp.data[0].embedding
    return embedding