#!/usr/bin/env python3
import argparse
import os
import sys
import threading

from dotenv import load_dotenv

import claude_client
import dataforseo_client
import display
import merger
import openai_client


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SEO keyword research tool — Claude + ChatGPT + Google (DataForSEO)"
    )
    parser.add_argument("-k", "--keyword", help="Seed keyword to research")
    parser.add_argument(
        "--limit", type=int, default=50, help="Max keywords per source (default: 50)"
    )
    parser.add_argument(
        "--location-code",
        type=int,
        default=2840,
        help="DataForSEO location code (default: 2840 = United States)",
    )
    parser.add_argument(
        "--language-code",
        default="en",
        help="Language code (default: en)",
    )
    parser.add_argument(
        "--export", action="store_true", help="Auto-export results to CSV"
    )
    parser.add_argument(
        "--no-export", action="store_true", help="Skip CSV export prompt"
    )
    return parser.parse_args()


def load_config() -> dict:
    load_dotenv()
    config = {
        "anthropic_key": os.environ.get("ANTHROPIC_API_KEY", ""),
        "openai_key": os.environ.get("OPENAI_API_KEY", ""),
        "dfs_login": os.environ.get("DATAFORSEO_LOGIN", ""),
        "dfs_password": os.environ.get("DATAFORSEO_PASSWORD", ""),
    }
    missing = [k for k, v in [
        ("ANTHROPIC_API_KEY", config["anthropic_key"]),
        ("OPENAI_API_KEY", config["openai_key"]),
        ("DATAFORSEO_LOGIN", config["dfs_login"]),
        ("DATAFORSEO_PASSWORD", config["dfs_password"]),
    ] if not v]
    if missing:
        print(f"Error: Missing environment variables: {', '.join(missing)}")
        print("Copy .env.example to .env and fill in your credentials.")
        sys.exit(1)
    return config


def fetch_concurrently(
    seed: str,
    config: dict,
    location_code: int,
    language_code: str,
    limit: int,
) -> tuple[dict[str, list[str]], list[dict]]:
    results: dict[str, object] = {}
    errors: dict[str, Exception] = {}

    def run_claude():
        try:
            results["Claude"] = claude_client.get_claude_keywords(
                seed, config["anthropic_key"], limit
            )
        except Exception as e:
            errors["Claude"] = e

    def run_chatgpt():
        try:
            results["ChatGPT"] = openai_client.get_chatgpt_keywords(
                seed, config["openai_key"], limit
            )
        except Exception as e:
            errors["ChatGPT"] = e

    def run_google():
        try:
            results["google"] = dataforseo_client.get_google_keywords(
                seed, config, location_code, language_code, limit
            )
        except Exception as e:
            errors["google"] = e

    threads = [
        threading.Thread(target=run_claude),
        threading.Thread(target=run_chatgpt),
        threading.Thread(target=run_google),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    for source, err in errors.items():
        print(f"  Warning: {source} fetch failed — {err}")

    llm_keywords: dict[str, list[str]] = {
        src: results.get(src, [])  # type: ignore[assignment]
        for src in ("Claude", "ChatGPT")
    }
    google_rows: list[dict] = results.get("google", [])  # type: ignore[assignment]

    if not any(llm_keywords.values()) and not google_rows:
        print("Error: All sources failed. Exiting.")
        sys.exit(1)

    return llm_keywords, google_rows


def main() -> None:
    args = parse_args()
    config = load_config()

    seed = args.keyword
    if not seed:
        seed = input("Enter seed keyword: ").strip()
    if not seed:
        print("Error: Seed keyword cannot be empty.")
        sys.exit(1)

    print(f'\nResearching keywords for: "{seed}"')
    print("  Fetching from Claude, ChatGPT, and Google in parallel...")

    llm_keywords, google_rows = fetch_concurrently(
        seed, config, args.location_code, args.language_code, args.limit
    )

    counts = "  |  ".join(
        f"{src}: {len(kws)}" for src, kws in llm_keywords.items()
    )
    print(f"  {counts}  |  Google: {len(google_rows)}")

    # Back-fill search volumes for LLM-only keywords
    llm_only = merger.split_llm_only(llm_keywords, google_rows)
    volume_map: dict[str, int | None] = {}
    if llm_only:
        print(f"  Fetching search volumes for {len(llm_only)} LLM-only keywords...")
        try:
            volume_map = dataforseo_client.get_search_volumes(
                llm_only, config, args.location_code, args.language_code
            )
        except Exception as e:
            print(f"  Warning: Could not fetch volumes for LLM keywords — {e}")

    merged = merger.merge(llm_keywords, google_rows, volume_map)
    display.print_table(merged, seed)

    if args.export:
        path = display.export_csv(merged, seed)
        print(f"Saved: {path}")
    elif not args.no_export:
        try:
            display.prompt_export(merged, seed)
        except EOFError:
            print("\nTip: use --export to auto-save CSV, or --no-export to skip.")


if __name__ == "__main__":
    main()
