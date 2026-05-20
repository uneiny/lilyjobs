from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path

from collectors import (
    cleaneye_jobplus,
    gangbuk_recruit,
    geumcheon_recruit,
    guro_recruit,
    gwangmyeong_notice,
    job_alio,
    jobaba,
    local_gov_board,
    narailter,
)
from collectors.base import make_error_row, normalize_region
from collectors.http_client import friendly_error_message


APP_DIR = Path(__file__).resolve().parents[1]
LOG_DIR = APP_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    filename=LOG_DIR / "collector.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    encoding="utf-8",
)


COLLECTORS = {
    "narailter": narailter.collect,
    "cleaneye_jobplus": cleaneye_jobplus.collect,
    "job_alio": job_alio.collect,
    "jobaba": jobaba.collect,
    "gwangmyeong_notice": gwangmyeong_notice.collect,
    "guro_recruit": guro_recruit.collect,
    "geumcheon_recruit": geumcheon_recruit.collect,
    "gangbuk_recruit": gangbuk_recruit.collect,
    "local_gov_board": local_gov_board.collect,
}


def collect_jobs(
    sites: list[dict],
    search_keyword: str = "",
    max_items: int = 20,
    region_keyword: str = "",
) -> list[dict]:
    rows, _logs = collect_jobs_with_logs(sites, search_keyword, max_items, region_keyword)
    return rows


def collect_jobs_with_logs(
    sites: list[dict],
    search_keyword: str = "",
    max_items: int = 20,
    region_keyword: str = "",
) -> tuple[list[dict], list[dict]]:
    all_rows = []
    logs = []
    keyword = search_keyword or region_keyword

    for site in sites:
        source = site.get("name", "알 수 없는 사이트")
        collector_name = site.get("collector")
        log = {
            "site_key": collector_name or "",
            "site_label": source,
            "status": "success",
            "count": 0,
            "message": "",
        }

        collector = COLLECTORS.get(collector_name or "")

        if collector is None:
            message = "수집 함수가 COLLECTORS에 등록되지 않음"
            all_rows.append(make_error_row(source, message, site.get("region", "")))
            log.update(status="missing_collector", message=message)
            logs.append(log)
            continue

        try:
            collector_keyword = "" if site.get("type") == "static" else keyword
            rows = collector(site=site, search_keyword=collector_keyword, max_items=max_items)
            if rows is None:
                rows = []

            normalized_rows = normalize_deadline_status(normalize_result_values(rows, source))
            all_rows.extend(normalized_rows)
            log["count"] = len(normalized_rows)
        except Exception as error:
            logging.exception("%s 수집 실패", source)
            message = local_run_hint(collector_name or "", friendly_error_message(error))
            all_rows.append(make_error_row(source, message, site.get("region", "")))
            log.update(status="error", message=message)
        logs.append(log)

    return deduplicate_rows(all_rows), logs


def local_run_hint(collector_name: str, message: str) -> str:
    if collector_name not in {"narailter", "job_alio"}:
        return message

    if not any(keyword in message for keyword in ("접속 실패", "접속 지연")):
        return message

    return (
        f"{message} Streamlit Cloud 등 서버 환경에서는 접속이 제한될 수 있습니다. "
        "로컬 버전(run_local.bat)으로 실행해 주세요."
    )


def deduplicate_rows(rows: list[dict]) -> list[dict]:
    unique_rows = []
    seen_keys = set()

    for row in rows:
        source = str(row.get("출처", "") or "").strip()
        organization = source.split(" > ", 1)[0].strip()
        title = str(row.get("공고명", "") or "").strip()
        posted_date = str(row.get("등록일", "") or "").strip()
        post_url = str(row.get("URL", "") or "").strip()

        keys = []
        if post_url:
            keys.append(("post_url", post_url))
        if organization and title and posted_date:
            keys.append(("organization_title_date", organization, title, posted_date))
        if not keys:
            keys.append(("row", source, title, posted_date, row.get("기관/부서", "")))

        if any(key in seen_keys for key in keys):
            continue

        seen_keys.update(keys)
        unique_rows.append(row)

    return unique_rows


def normalize_result_values(rows: list[dict], source: str) -> list[dict]:
    for row in rows:
        row["출처"] = source
        row["지역"] = normalize_region(row.get("지역", ""))

    return rows


def normalize_deadline_status(rows: list[dict]) -> list[dict]:
    for row in rows:
        deadline = parse_date(row.get("마감일", ""))
        if deadline is None:
            continue

        today = date.today()
        if deadline < today:
            row["마감여부"] = "마감"
        elif deadline == today:
            row["마감여부"] = "마감당일"
        elif deadline == today + timedelta(days=1):
            row["마감여부"] = "마감전일"
        else:
            row["마감여부"] = "진행중"

    return rows


def parse_date(value: str) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None

    for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    return None
