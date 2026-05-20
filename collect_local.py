from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from collectors.base import RESULT_COLUMNS
from services.config_loader import load_sites_config
from services.runner import collect_jobs


APP_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = APP_DIR / "data" / "output" / "lilyjobs_results.xlsx"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect job postings locally and save them to an Excel file.",
    )
    parser.add_argument(
        "--keyword",
        default="",
        help="Optional keyword to filter collected postings.",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=20,
        help="Maximum postings to collect per selected site.",
    )
    parser.add_argument(
        "--sites",
        nargs="*",
        default=[],
        help="Optional site names to collect. Matches either source name or collector id.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Excel output path.",
    )
    return parser.parse_args()


def select_sites(sites: list[dict], names: list[str]) -> list[dict]:
    if not names:
        return sites

    wanted = {name.lower() for name in names}
    return [
        site
        for site in sites
        if str(site.get("name", "")).lower() in wanted
        or str(site.get("collector", "")).lower() in wanted
    ]


def main() -> None:
    args = parse_args()
    sites = load_sites_config(APP_DIR / "sites_config.json")
    selected_sites = select_sites(sites, args.sites)

    if not selected_sites:
        raise SystemExit("No matching sites found. Check --sites values.")

    rows = collect_jobs(
        sites=selected_sites,
        search_keyword=args.keyword.strip(),
        max_items=max(1, args.max_items),
    )
    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(rows, columns=RESULT_COLUMNS)
    df.to_excel(output, index=False)
    print(f"Saved {len(df)} rows to {output}")


if __name__ == "__main__":
    main()
