import requests

BASE_URL = "https://api.dataforseo.com/v3"


def _make_session(login: str, password: str) -> requests.Session:
    session = requests.Session()
    session.auth = (login, password)
    session.headers.update({"Content-Type": "application/json"})
    return session


def _parse_task_result(response_json: dict) -> list[dict]:
    if response_json.get("status_code") != 20000:
        msg = response_json.get("status_message", "Unknown error")
        raise RuntimeError(f"DataForSEO error: {msg}")

    tasks = response_json.get("tasks", [])
    if not tasks:
        return []

    task = tasks[0]
    if task.get("status_code") != 20000:
        msg = task.get("status_message", "Unknown task error")
        raise RuntimeError(f"DataForSEO task error: {msg}")

    return task.get("result") or []


def get_google_keywords(
    seed: str,
    config: dict,
    location_code: int = 2840,
    language_code: str = "en",
    limit: int = 50,
) -> list[dict]:
    session = _make_session(config["dfs_login"], config["dfs_password"])

    payload = [
        {
            "keywords": [seed],
            "location_code": location_code,
            "language_code": language_code,
            "limit": limit,
            "include_adult_keywords": False,
            "sort_by": "search_volume",
        }
    ]

    resp = session.post(
        f"{BASE_URL}/keywords_data/google_ads/keywords_for_keywords/live",
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()

    results = _parse_task_result(resp.json())
    return [
        {
            "keyword": item["keyword"],
            "search_volume": item.get("search_volume"),
        }
        for item in results
    ]


def get_search_volumes(
    keywords: list[str],
    config: dict,
    location_code: int = 2840,
    language_code: str = "en",
) -> dict[str, int | None]:
    if not keywords:
        return {}

    session = _make_session(config["dfs_login"], config["dfs_password"])
    volume_map: dict[str, int | None] = {}

    # DataForSEO accepts up to 1000 keywords per task
    chunk_size = 1000
    for i in range(0, len(keywords), chunk_size):
        chunk = keywords[i : i + chunk_size]
        payload = [
            {
                "keywords": chunk,
                "location_code": location_code,
                "language_code": language_code,
            }
        ]

        resp = session.post(
            f"{BASE_URL}/keywords_data/google_ads/search_volume/live",
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()

        results = _parse_task_result(resp.json())
        for item in results:
            kw = item["keyword"].lower()
            volume_map[kw] = item.get("search_volume")

    return volume_map
