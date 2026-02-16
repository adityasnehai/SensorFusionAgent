import os
from openai import OpenAI


def get_llm_client():
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise ValueError("OPENAI_API_KEY not set in .env")

    return OpenAI(api_key=api_key)
