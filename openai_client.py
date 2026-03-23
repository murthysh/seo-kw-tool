from openai import OpenAI


def get_chatgpt_keywords(seed: str, api_key: str, limit: int = 50) -> list[str]:
    client = OpenAI(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=1024,
            messages=[
                {
                    "role": "system",
                    "content": "You are a keyword research assistant. Respond only with a plain list of keywords, one per line, no numbering, no bullets, no extra text.",
                },
                {
                    "role": "user",
                    "content": (
                        f"Generate {limit} keyword ideas related to: {seed}\n\n"
                        "Rules:\n"
                        "- One keyword per line\n"
                        "- No numbering, bullets, or punctuation\n"
                        "- No explanations or extra text\n"
                        "- Plain keywords only"
                    ),
                },
            ],
        )
    except Exception as e:
        raise RuntimeError(f"OpenAI API error: {e}") from e

    lines = response.choices[0].message.content.strip().splitlines()
    seen = set()
    keywords = []
    for line in lines:
        kw = line.strip()
        if kw and kw.lower() not in seen:
            seen.add(kw.lower())
            keywords.append(kw)

    return keywords
