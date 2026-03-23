import anthropic


def _build_prompt(seed: str, limit: int) -> str:
    return (
        f"Generate {limit} keyword ideas related to: {seed}\n\n"
        "Rules:\n"
        "- One keyword per line\n"
        "- No numbering, bullets, or punctuation\n"
        "- No explanations or extra text\n"
        "- Plain keywords only"
    )


def get_claude_keywords(seed: str, api_key: str, limit: int = 50) -> list[str]:
    client = anthropic.Anthropic(api_key=api_key)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system="You are a keyword research assistant. Respond only with a plain list of keywords, one per line, no numbering, no bullets, no extra text.",
            messages=[{"role": "user", "content": _build_prompt(seed, limit)}],
        )
    except anthropic.APIError as e:
        raise RuntimeError(f"Claude API error: {e}") from e

    lines = response.content[0].text.strip().splitlines()
    seen = set()
    keywords = []
    for line in lines:
        kw = line.strip()
        if kw and kw.lower() not in seen:
            seen.add(kw.lower())
            keywords.append(kw)

    return keywords
