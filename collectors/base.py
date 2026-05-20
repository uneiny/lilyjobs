from __future__ import annotations

from datetime import datetime
from typing import Any


RESULT_COLUMNS = [
    "출처",
    "지역",
    "기관/부서",
    "공고명",
    "등록일",
    "마감일",
    "마감여부",
    "URL",
    "수집일시",
    "추출상태",
]

REGION_ALIASES = {
    "강원": "강원특별자치도",
    "강원도": "강원특별자치도",
    "강원특별자치도": "강원특별자치도",
}


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def normalize_region(value: str) -> str:
    text = str(value or "").strip()
    return REGION_ALIASES.get(text, text)


def make_job_row(
    source: str,
    region: str = "",
    department: str = "",
    title: str = "",
    posted_date: str = "",
    deadline: str = "",
    is_closed: str = "",
    post_url: str = "",
    collected_at: str | None = None,
    status: str = "성공",
) -> dict[str, Any]:
    return {
        "출처": str(source or "").strip(),
        "지역": normalize_region(region),
        "기관/부서": department,
        "공고명": title,
        "등록일": posted_date,
        "마감일": deadline,
        "마감여부": is_closed,
        "URL": post_url,
        "수집일시": collected_at or now_text(),
        "추출상태": status,
    }


def make_error_row(source: str, message: str, region: str = "") -> dict[str, Any]:
    return make_job_row(source=source, region=region, status=f"실패: {message}")
