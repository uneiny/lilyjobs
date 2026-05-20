from __future__ import annotations

import json

import requests

from collectors.base import make_job_row


API_URL = "https://job.cleaneye.go.kr/user/selectYpRecruitment.do"
DETAIL_URL = "https://job.cleaneye.go.kr/user/ypCareersData.do"
MAX_SCAN_PAGES = 30
STATUS_NAMES = {
    "709001": "모집중",
    "709002": "모집예정",
    "709003": "모집마감",
}
SIDO_NAMES = {
    "007001": "서울특별시",
    "007002": "부산광역시",
    "007003": "대구광역시",
    "007004": "인천광역시",
    "007005": "광주광역시",
    "007006": "대전광역시",
    "007007": "울산광역시",
    "007017": "세종특별자치시",
    "007008": "경기도",
    "007009": "강원특별자치도",
    "007010": "충청북도",
    "007011": "충청남도",
    "007012": "전북특별자치도",
    "007013": "전라남도",
    "007014": "경상북도",
    "007015": "경상남도",
    "007016": "제주특별자치도",
}


def collect(site: dict, search_keyword: str = "", max_items: int = 20) -> list[dict]:
    rows = []
    seen = set()

    for page_index in range(1, MAX_SCAN_PAGES + 1):
        data = fetch_page(page_index)
        items = data.get("list", [])
        if not items:
            break

        for item in items:
            full_text = " ".join(str(item.get(key, "")) for key in ("entName", "entTitle", "sidoCd"))
            if search_keyword and search_keyword not in full_text:
                continue

            row = make_job_row(
                source=site["name"],
                region=SIDO_NAMES.get(item.get("sidoCd", ""), item.get("sidoCd", "")),
                department=item.get("entName", ""),
                title=item.get("entTitle", ""),
                posted_date=item.get("pubDate", ""),
                deadline=item.get("pubEndDate", ""),
                is_closed=STATUS_NAMES.get(item.get("status", ""), item.get("status", "")),
                post_url=build_detail_url(item),
                status="성공",
            )
            key = (row["공고명"], row["URL"])
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)

            if len(rows) >= max_items:
                return rows

    if not rows:
        rows.append(make_job_row(source=site["name"], status="성공: 조건에 맞는 공고 없음"))

    return rows


def fetch_page(page_index: int) -> dict:
    response = requests.post(
        API_URL,
        data={
            "pageIndex": str(page_index),
            "entRecruitList": "",
            "localYnList": "",
            "specialItemList": "",
            "jobTypeList": "",
            "employGbList": "",
            "workPlaceList": "",
            "officeHoursList": "",
            "reManYnList": "",
            "entGbList": "",
            "entKindList": "",
            "yearincome": "",
            "status": "",
            "pubDate": "",
            "pubEndDate": "",
            "entName": "",
        },
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://job.cleaneye.go.kr/user/ypRecruitment.do",
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def build_detail_url(item: dict) -> str:
    return (
        f"{DETAIL_URL}?empyear={item.get('empyear', '')}"
        f"&ypEntId={item.get('ypEntId', '')}"
        f"&entSeq={item.get('entSeq', '')}"
    )


def debug_network(site: dict) -> None:
    response = requests.post(
        API_URL,
        data={"pageIndex": "1"},
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://job.cleaneye.go.kr/user/ypRecruitment.do",
        },
        timeout=20,
    )
    print(json.dumps({
        "url": response.url,
        "status": response.status_code,
        "content_type": response.headers.get("content-type", ""),
        "preview": response.text[:500],
    }, ensure_ascii=False))
