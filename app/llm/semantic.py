import json
from app.llm.client import get_llm_client


def semantic_column_alignment(columns_a, columns_b):

    client = get_llm_client()

    prompt = f"""
You are a sensor data harmonization expert.

Dataset A columns:
{columns_a}

Dataset B columns:
{columns_b}

Return JSON mapping of semantically equivalent columns.
Only return JSON. Example:

{{
  "acc_x": "accel_x",
  "acc_y": "accel_y"
}}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        messages=[{"role": "user", "content": prompt}],
    )

    content = response.choices[0].message.content

    try:
        return json.loads(content)
    except:
        return {}
