import os
from openai import OpenAI

def call_llm(prompt: str, model: str = "gpt-5-mini-2025-08-07") -> str:
    """
    Sends a prompt to the OpenAI Responses API and returns the text output.
    Requires: OPENAI_API_KEY set in your environment (or .env loaded by your IDE).
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Set it in your environment or .env.")

    client = OpenAI(api_key=api_key)

    resp = client.responses.create(
        model=model,
        input=prompt,
    )

    return (resp.output_text or "").strip()

if __name__ == "__main__":
    test_prompt = """
You are a coding assistant.
Explain what a null pointer dereference is, and show a tiny Python example of a similar bug pattern.
Keep it short.
""".strip()

    print(call_llm(test_prompt))