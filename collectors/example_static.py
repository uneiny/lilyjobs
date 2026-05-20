from __future__ import annotations

from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from collectors.base import make_job_row


def collect(site: dict, region_keyword: str = "", max_items: int = 20) -> list[dict]:
    url = site["url"]
    response = requests.get(url, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    selectors = site.get("selectors", {})
    list_selector = selectors.get("list", "a")

    rows = []
    for item in soup.select(list_selector)[:max_items]:
        title = item.get_text(" ", strip=True)
        post_url = urljoin(url, item.get("href", ""))

        if not title:
            continue

        if region_keyword and region_keyword not in title:
            continue

        rows.append(
            make_job_row(
                source=site["name"],
                region=region_keyword,
                title=title,
                post_url=post_url,
                status="성공",
            )
        )

    if not rows:
        rows.append(
            make_job_row(
                source=site["name"],
                region=region_keyword,
                status="성공: 조건에 맞는 공고 없음",
            )
        )

    return rows
