from __future__ import annotations

from collectors.common_static import collect_static_links


def collect(site: dict, search_keyword: str = "", max_items: int = 20) -> list[dict]:
    return collect_static_links(site, search_keyword, max_items)
