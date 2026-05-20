from __future__ import annotations

import json
from datetime import date, timedelta

from collectors.base import make_job_row
from collectors.http_client import (
    NetworkRequestError,
    browser_headers,
    fetch_json_with_playwright,
    post,
)


API_URL = "https://www.alio.go.kr/information/getRecruitList.json"
REFERER_URL = "https://www.alio.go.kr/mobile/information/informationRecruitList.do"
MAX_SCAN_PAGES = 30


def collect(site: dict, search_keyword: str = "", max_items: int = 20) -> list[dict]:
    rows = []
    seen = set()

    for page_no in range(1, MAX_SCAN_PAGES + 1):
        data = fetch_page(search_keyword, page_no)
        if data.get("status") != "success":
            message = data.get("message") or "잡알리오 API 응답 오류"
            raise RuntimeError(message)

        items = data.get("data", {}).get("recruitList", [])
        if not items:
            break

        for item in items:
            full_text = " ".join(
                str(item.get(key, ""))
                for key in ("pname", "title", "locationNa", "workTypeNa", "carrerNa")
            )
            if search_keyword and search_keyword not in full_text:
                continue

            seq = item.get("seq", "")
            row = make_job_row(
                source=site["name"],
                region=item.get("locationNa", ""),
                department=item.get("pname", ""),
                title=item.get("title", ""),
                posted_date=normalize_date(item.get("frstDate", "")),
                deadline=normalize_date(item.get("termEnd", "")),
                is_closed=item.get("ing", ""),
                post_url=f"https://www.alio.go.kr/mobile/information/informationRecruitDtl.do?seq={seq}",
                status="성공",
            )
            key = (row["공고명"], row["URL"])
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)

            if len(rows) >= max_items:
                return rows

        total_page = data.get("data", {}).get("page", {}).get("totalPage")
        if total_page and page_no >= int(total_page):
            break

    if not rows:
        rows.append(make_job_row(source=site["name"], status="성공: 조건에 맞는 공고 없음"))

    return rows


def fetch_page(search_keyword: str, page_no: int) -> dict:
    payload = build_payload(search_keyword, page_no)
    try:
        response = post(
            API_URL,
            json=payload,
            headers={
                "Referer": REFERER_URL,
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Content-Type": "application/json;charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        return response.json()
    except NetworkRequestError as request_error:
        try:
            return fetch_json_with_playwright(API_URL, payload=payload, referer=REFERER_URL)
        except NetworkRequestError as fallback_error:
            if "Playwright fallback 모두 사용할 수 없습니다" in fallback_error.user_message:
                raise request_error from fallback_error
            raise
    except Exception:
        return fetch_json_with_playwright(API_URL, payload=payload, referer=REFERER_URL)


def build_payload(search_keyword: str, page_no: int) -> dict:
    today = date.today()
    start_date = today - timedelta(days=210)
    return {
        "detailcodeValueArr": [],
        "locationValueArr": [],
        "worktypeValueArr": [],
        "eduValueArr": [],
        "areaValueArr": [],
        "carrerValueArr": [],
        "apba_type": "",
        "apba_id": "",
        "replacement": "",
        "title": search_keyword,
        "s_date": start_date.strftime("%Y.%m.%d"),
        "e_date": today.strftime("%Y.%m.%d"),
        "ing": "",
        "order": "IDATE",
        "pageNo": str(page_no),
    }


def normalize_date(value: str) -> str:
    return (value or "").replace(".", "-")


def debug_network(site: dict) -> None:
    response = post(
        API_URL,
        json=build_payload("", 1),
        headers=browser_headers(
            Referer=REFERER_URL,
            Accept="application/json, text/javascript, */*; q=0.01",
            Content_Type="application/json;charset=UTF-8",
            X_Requested_With="XMLHttpRequest",
        ),
    )
    print(json.dumps({
        "url": response.url,
        "status": response.status_code,
        "content_type": response.headers.get("content-type", ""),
        "preview": response.text[:500],
    }, ensure_ascii=False))
