def normalize(keyword: str) -> str:
    return keyword.strip().lower()


def split_llm_only(
    llm_keywords: dict[str, list[str]],
    google_rows: list[dict],
) -> list[str]:
    """Return all LLM keywords (across all sources) not found in Google results."""
    google_keys = {normalize(row["keyword"]) for row in google_rows}
    seen = set()
    result = []
    for keywords in llm_keywords.values():
        for kw in keywords:
            key = normalize(kw)
            if key not in google_keys and key not in seen:
                seen.add(key)
                result.append(kw)
    return result


def merge(
    llm_keywords: dict[str, list[str]],
    google_rows: list[dict],
    volume_map: dict[str, int | None],
) -> list[dict]:
    """
    llm_keywords: {"Claude": [...], "ChatGPT": [...], ...}
    google_rows:  [{"keyword": str, "search_volume": int|None}, ...]
    volume_map:   {normalized_keyword: search_volume} for LLM-only keywords
    """
    google_index = {normalize(row["keyword"]): row for row in google_rows}

    # Build per-keyword source sets
    all_keys: dict[str, set[str]] = {}

    for source, keywords in llm_keywords.items():
        for kw in keywords:
            key = normalize(kw)
            if key not in all_keys:
                all_keys[key] = set()
            all_keys[key].add(source)

    for row in google_rows:
        key = normalize(row["keyword"])
        if key not in all_keys:
            all_keys[key] = set()
        all_keys[key].add("Google")

    all_sources = set(llm_keywords.keys()) | {"Google"}
    rows = []

    for key, sources in all_keys.items():
        # Display form: prefer Google casing, then first LLM source
        if key in google_index:
            display_kw = google_index[key]["keyword"]
            volume = google_index[key]["search_volume"]
        else:
            # Find original casing from any LLM source
            display_kw = key  # fallback
            for source, keywords in llm_keywords.items():
                for kw in keywords:
                    if normalize(kw) == key:
                        display_kw = kw
                        break
            volume = volume_map.get(key)

        if sources == all_sources:
            source_label = "All"
        else:
            source_label = ", ".join(sorted(sources))

        rows.append({"keyword": display_kw, "search_volume": volume, "source": source_label})

    rows.sort(key=lambda r: r["search_volume"] if r["search_volume"] is not None else -1, reverse=True)
    return rows
