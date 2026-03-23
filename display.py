import csv
import re
from datetime import datetime


def print_table(rows: list[dict], seed: str) -> None:
    col_kw = 45
    col_vol = 15
    col_src = 8
    total_width = col_kw + col_vol + col_src + 4

    print(f"\nKeyword results for: \"{seed}\"")
    print("=" * total_width)
    print(
        f"{'KEYWORD':<{col_kw}} {'SEARCH VOLUME':>{col_vol}} {'SOURCE':>{col_src}}"
    )
    print("-" * total_width)

    for row in rows:
        kw = row["keyword"]
        if len(kw) > col_kw - 1:
            kw = kw[: col_kw - 4] + "..."
        vol = f"{row['search_volume']:,}" if row["search_volume"] is not None else "N/A"
        src = row["source"]
        print(f"{kw:<{col_kw}} {vol:>{col_vol}} {src:>{col_src}}")

    print("=" * total_width)

    by_source: dict[str, int] = {}
    for row in rows:
        by_source[row["source"]] = by_source.get(row["source"], 0) + 1

    summary = "  ".join(f"{src}: {count}" for src, count in sorted(by_source.items()))
    print(f"Total: {len(rows)} keywords  ({summary})")


def prompt_export(rows: list[dict], seed: str) -> None:
    answer = input("\nExport to CSV? [y/N]: ").strip().lower()
    if answer == "y":
        path = export_csv(rows, seed)
        print(f"Saved: {path}")


def export_csv(rows: list[dict], seed: str) -> str:
    slug = seed.lower().replace(" ", "_")
    slug = re.sub(r"[^a-z0-9_]", "", slug)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{slug}_{timestamp}.csv"

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["keyword", "search_volume", "source"])
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "keyword": row["keyword"],
                    "search_volume": row["search_volume"] if row["search_volume"] is not None else "",
                    "source": row["source"],
                }
            )

    return filename
