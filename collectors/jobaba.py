from __future__ import annotations

import json

import requests

from collectors.base import make_job_row


API_URL = "https://job.gg.go.kr/pblcEmpmn/listAjax.do"
DETAIL_TEMPLATE = "https://job.gg.go.kr/pblcEmpmn/publicJobDetail.do?seq={seq}&srchType=NEW&currentPageNo={page_no}"
MAX_SCAN_PAGES = 30


def collect(site: dict, search_keyword: str = "", max_items: int = 20) -> list[dict]:
    rows = []
    seen = set()

    for page_no in range(1, MAX_SCAN_PAGES + 1):
        data = fetch_page(search_keyword, page_no)
        items = data.get("PUBLIC_JOB_LIST", [])
        if not items:
            break

        for item in items:
            full_text = " ".join(
                str(item.get(key, ""))
                for key in ("workRgnCdsNm", "workRgnDtlCdsNm", "instNm", "title", "rcrutFldCdsNm")
            )
            if search_keyword and search_keyword not in full_text:
                continue

            row = make_job_row(
                source=site["name"],
                region=" ".join(part for part in [item.get("workRgnCdsNm", ""), item.get("workRgnDtlCdsNm", "")] if part),
                department=item.get("instNm", ""),
                title=item.get("title", ""),
                posted_date=item.get("regDt", ""),
                deadline=item.get("endDt", ""),
                is_closed="진행중" if str(item.get("diffDay", "")).isdigit() else "",
                post_url=item.get("dtlUrl") or DETAIL_TEMPLATE.format(seq=item.get("seq", ""), page_no=page_no),
                status="성공",
            )
            key = (row["공고명"], row["URL"])
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)

            if len(rows) >= max_items:
                return rows

        pagination = data.get("PAGINATION", {})
        total_page = pagination.get("totalPageCount") or pagination.get("lastPageNoOnPageList")
        if total_page and page_no >= int(total_page):
            break

    if not rows:
        rows.append(make_job_row(source=site["name"], region=site.get("region", ""), status="성공: 조건에 맞는 공고 없음"))

    return rows


def fetch_page(search_keyword: str, page_no: int) -> dict:
    response = requests.post(
        API_URL,
        data={
            "srchTxt": search_keyword,
            "srchWorkRgnCds": "",
            "srchWorkRgnDtlCds": "",
            "srchRcrutFldCds": "",
            "srchEmpFrCds": "",
            "srchRcrutSeCds": "",
            "srchType": "NEW",
            "currentPageNo": str(page_no),
            "fromDetailYn": "N",
            "recordCountPerPage": "16",
        },
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://job.gg.go.kr/pblcEmpmn/list.do",
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def debug_network(site: dict) -> None:
    response = requests.post(
        API_URL,
        data={
            "srchTxt": "",
            "srchType": "NEW",
            "currentPageNo": "1",
            "fromDetailYn": "N",
            "recordCountPerPage": "16",
        },
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://job.gg.go.kr/pblcEmpmn/list.do",
        },
        timeout=20,
    )
    print(json.dumps({
        "url": response.url,
        "status": response.status_code,
        "content_type": response.headers.get("content-type", ""),
        "preview": response.text[:500],
    }, ensure_ascii=False))
