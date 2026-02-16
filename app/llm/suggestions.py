from app.llm.client import get_llm_client


def suggest_sampling_rate(sensor_list):

    client = get_llm_client()

    prompt = f"""
You are an expert in human activity recognition datasets.

Sensors detected:
{sensor_list}

What is a commonly used sampling rate for smartphone + wearable HAR datasets?

Return only a number in Hz.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        messages=[{"role": "user", "content": prompt}],
    )

    content = response.choices[0].message.content.strip()

    try:
        return float(content)
    except:
        return None
