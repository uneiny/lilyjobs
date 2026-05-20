from __future__ import annotations

import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from collectors.base import make_job_row
from collectors.http_client import (
    NetworkRequestError,
    browser_headers,
    fetch_html_with_playwright,
    get,
)


LIST_URL = "https://www.gojobs.go.kr/apmList.do"
DETAIL_TEMPLATE = "https://www.gojobs.go.kr/apmView.do?empmnsn={empmnsn}&searchJobsecode={job_code}"
VIEW_PATTERN = re.compile(r"fn_apmView\('([^']+)'\s*,\s*'([^']+)'\)")
MAX_SCAN_PAGES = 20


def collect(site: dict, search_keyword: str = "", max_items: int = 20) -> list[dict]:
    rows = []
    seen = set()

    for page_index in range(1, MAX_SCAN_PAGES + 1):
        soup = fetch_page(search_keyword, page_index)
        page_rows = parse_rows(site, soup, search_keyword)

        if not page_rows:
            break

        for row in page_rows:
            key = (row.get("공고명", ""), row.get("URL", ""))
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)

            if len(rows) >= max_items:
                return rows

    if not rows:
        rows.append(make_job_row(source=site["name"], status="성공: 조건에 맞는 공고 없음"))

    return rows


def fetch_page(search_keyword: str, page_index: int) -> BeautifulSoup:
    params = {
        "empmnsn": "0",
        "menuNo": "3",
        "searchBbssecode": "0",
        "searchBbssn": "0",
        "searchJobsecode": "",
        "searchKeyword": search_keyword,
        "pageIndex": str(page_index),
    }
    try:
        response = get(
            LIST_URL,
            params=params,
            headers={
                "Referer": "https://www.gojobs.go.kr/mainIndex.do",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        html = response.text
    except NetworkRequestError as request_error:
        try:
            html = fetch_html_with_playwright(LIST_URL, params=params)
        except NetworkRequestError as fallback_error:
            if "Playwright fallback 모두 사용할 수 없습니다" in fallback_error.user_message:
                raise request_error from fallback_error
            raise
    except Exception:
        html = fetch_html_with_playwright(LIST_URL, params=params)
    return BeautifulSoup(html, "html.parser")


def parse_rows(site: dict, soup: BeautifulSoup, search_keyword: str) -> list[dict]:
    rows = []

    for tr in soup.select("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in tr.find_all(["td", "th"])]
        if len(cells) < 6 or not cells[0].isdigit():
            continue

        title = cells[1]
        department = cells[2]
        full_text = " ".join(cells)
        if search_keyword and search_keyword not in full_text:
            continue

        link = tr.find("a", href=True)
        post_url = ""
        if link:
            match = VIEW_PATTERN.search(link.get("href", ""))
            if match:
                job_code, empmnsn = match.groups()
                post_url = DETAIL_TEMPLATE.format(job_code=job_code, empmnsn=empmnsn)
            else:
                post_url = urljoin(LIST_URL, link.get("href", ""))

        rows.append(
            make_job_row(
                source=site["name"],
                region=infer_region(full_text),
                department=department,
                title=title,
                posted_date=cells[3],
                deadline=cells[4],
                is_closed="진행중",
                post_url=post_url,
                status="성공",
            )
        )

    return rows


def infer_region(text: str) -> str:
    region_keywords = [
        ("서울", "서울"),
        ("부산", "부산"),
        ("대구", "대구"),
        ("인천", "인천"),
        ("광주", "광주"),
        ("대전", "대전"),
        ("울산", "울산"),
        ("세종", "세종"),
        ("경기", "경기"),
        ("강원", "강원"),
        ("충북", "충북"),
        ("충청북도", "충북"),
        ("충남", "충남"),
        ("충청남도", "충남"),
        ("전북", "전북"),
        ("전라북도", "전북"),
        ("전남", "전남"),
        ("전라남도", "전남"),
        ("경북", "경북"),
        ("경상북도", "경북"),
        ("경남", "경남"),
        ("경상남도", "경남"),
        ("제주", "제주"),
        ("춘천", "강원"),
        ("원주", "강원"),
        ("청주", "충북"),
        ("천안", "충남"),
        ("전주", "전북"),
        ("목포", "전남"),
        ("포항", "경북"),
        ("창원", "경남"),
    ]
    for keyword, region in region_keywords:
        if keyword in text:
            return region
    return ""


def debug_network(site: dict) -> None:
    response = get(
        LIST_URL,
        params={
            "empmnsn": "0",
            "menuNo": "3",
            "searchBbssecode": "0",
            "searchBbssn": "0",
            "searchJobsecode": "",
            "pageIndex": "1",
        },
        headers=browser_headers(Referer="https://www.gojobs.go.kr/mainIndex.do"),
    )
    print(json.dumps({
        "url": response.url,
        "status": response.status_code,
        "content_type": response.headers.get("content-type", ""),
        "preview": response.text[:500],
    }, ensure_ascii=False))
