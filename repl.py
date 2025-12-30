from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

emb = client.embeddings.create(
    model="text-embedding-3-small",
    input="test"
).data[0].embedding

print(len(emb))

