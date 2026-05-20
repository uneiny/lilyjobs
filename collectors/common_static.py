from __future__ import annotations

import re
import ssl
from datetime import date, datetime
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup, Tag
from requests.adapters import HTTPAdapter

from collectors.base import make_job_row


DEFAULT_KEYWORDS = ("채용", "모집", "임용", "기간제", "공무직", "근로자", "인턴")
SKIP_TITLE_WORDS = (
    "채용정보",
    "채용소식",
    "채용공고",
    "목록",
    "검색",
    "로그인",
    "회원가입",
    "사이트맵",
    "개인정보",
)
FILE_EXTENSIONS = (".hwp", ".hwpx", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip")
DATE_PATTERN = re.compile(r"(20\d{2})[.\-/년]\s*(\d{1,2})[.\-/월]\s*(\d{1,2})")


class LegacyTLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        context = ssl.create_default_context()
        context.set_ciphers("DEFAULT@SECLEVEL=1")
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        kwargs["ssl_context"] = context
        return super().init_poolmanager(*args, **kwargs)


def collect_static_links(site: dict, search_keyword: str = "", max_items: int = 20) -> list[dict]:
    rows = []
    seen = set()
    pagination = site.get("pagination", {})
    max_pages = int(pagination.get("max_pages", 1))

    for page_no in range(1, max_pages + 1):
        soup = fetch_soup(site, page_no)
        page_rows = extract_table_rows(soup, site, search_keyword, max_items)

        if not page_rows:
            if page_no == 1 and site.get("allow_fallback", False):
                page_rows = extract_fallback_links(soup, site, search_keyword, max_items)
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
        status = "성공: 조건에 맞는 공고 없음"
        if site.get("dynamic_hint", False):
            status = "확인 필요: 목록이 JavaScript로 렌더링되어 Playwright/API 수집기 구현 필요"

        rows.append(
            make_job_row(
                source=site["name"],
                region=site_region(site),
                status=status,
            )
        )

    return rows


def collect_from_soup(
    soup: BeautifulSoup,
    site: dict,
    search_keyword: str = "",
    max_items: int = 20,
) -> list[dict]:
    rows = extract_table_rows(soup, site, search_keyword, max_items)

    if not rows and site.get("allow_fallback", False):
        rows = extract_fallback_links(soup, site, search_keyword, max_items)

    if not rows:
        status = "성공: 조건에 맞는 공고 없음"
        if site.get("dynamic_hint", False):
            status = "확인 필요: 목록이 JavaScript로 렌더링되어 Playwright/API 수집기 구현 필요"

        rows.append(
            make_job_row(
                source=site["name"],
                region=site_region(site),
                status=status,
            )
        )

    return rows


def fetch_soup(site: dict, page_no: int = 1) -> BeautifulSoup:
    url = build_page_url(site, page_no)
    client = requests.Session() if site.get("legacy_ssl", False) else requests
    if site.get("legacy_ssl", False):
        client.mount("https://", LegacyTLSAdapter())

    response = client.get(
        url,
        timeout=15,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0 Safari/537.36"
            )
        },
    )
    response.raise_for_status()
    if not response.encoding or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding or "utf-8"
    return BeautifulSoup(response.text, "html.parser")


def build_page_url(site: dict, page_no: int) -> str:
    url = site.get("list_url") or site["url"]
    pagination = site.get("pagination", {})
    page_param = pagination.get("page_param")
    if not page_param:
        return url

    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query[page_param] = str(page_no)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def extract_table_rows(
    soup: BeautifulSoup,
    site: dict,
    search_keyword: str,
    max_items: int,
) -> list[dict]:
    rows = []
    base_url = site.get("list_url") or site["url"]
    table_config = site.get("table", {})

    for tr in soup.select("tr"):
        cells = [cell for cell in tr.find_all(["th", "td"])]
        if len(cells) < int(table_config.get("min_cells", 3)):
            continue

        row = build_row_from_cells(site, base_url, cells, search_keyword)
        if row:
            rows.append(row)

        if len(rows) >= max_items:
            break

    return rows


def build_row_from_cells(
    site: dict,
    base_url: str,
    cells: list[Tag],
    search_keyword: str,
) -> dict | None:
    table_config = site.get("table", {})
    title_col = table_config.get("title_col")
    department_col = table_config.get("department_col")
    posted_col = table_config.get("posted_col")
    deadline_col = table_config.get("deadline_col")

    title_cell = get_cell(cells, title_col) if title_col is not None else find_title_cell(cells)
    if title_cell is None:
        return None

    title = clean_text(title_cell.get_text(" ", strip=True))
    link = title_cell.find("a", href=True)

    if link and clean_text(link.get_text(" ", strip=True)):
        title = clean_text(link.get_text(" ", strip=True))

    if not is_valid_title(title, site):
        return None

    full_row_text = clean_text(" ".join(cell.get_text(" ", strip=True) for cell in cells))
    if search_keyword and search_keyword not in full_row_text:
        return None

    posted_date = pick_date(get_cell_text(cells, posted_col)) if posted_col is not None else pick_date(full_row_text)
    deadline_text = get_cell_text(cells, deadline_col) if deadline_col is not None else ""
    deadline = pick_last_date(deadline_text)

    if not deadline and table_config.get("deadline_from_row", False):
        deadline = pick_last_date(full_row_text)

    post_url = resolve_post_url(site, base_url, link)

    return make_job_row(
        source=site["name"],
        region=site_region(site),
        department=get_cell_text(cells, department_col) if department_col is not None else "",
        title=title,
        posted_date=posted_date,
        deadline=deadline,
        is_closed=deadline_status(deadline),
        post_url=post_url,
        status="성공",
    )


def extract_fallback_links(
    soup: BeautifulSoup,
    site: dict,
    search_keyword: str,
    max_items: int,
) -> list[dict]:
    rows = []
    base_url = site.get("list_url") or site["url"]

    for link in soup.select("a[href]"):
        title = clean_text(link.get_text(" ", strip=True))
        href = link.get("href", "")
        parent_text = clean_text(link.parent.get_text(" ", strip=True)) if link.parent else title

        if not is_valid_title(title, site):
            continue
        if search_keyword and search_keyword not in parent_text:
            continue

        posted_date = pick_date(parent_text)
        deadline = pick_last_date(parent_text)
        rows.append(
            make_job_row(
                source=site["name"],
                region=site_region(site),
                title=title,
                posted_date=posted_date,
                deadline=deadline if deadline != posted_date else "",
                is_closed=deadline_status(deadline if deadline != posted_date else ""),
                post_url=urljoin(base_url, href),
                status="성공",
            )
        )

        if len(rows) >= max_items:
            break

    return rows


def is_valid_title(title: str, site: dict) -> bool:
    if len(title) < 6:
        return False
    if any(word == title for word in SKIP_TITLE_WORDS):
        return False
    if any(title.lower().endswith(ext) for ext in FILE_EXTENSIONS):
        return False

    keywords = tuple(site.get("keywords") or DEFAULT_KEYWORDS)
    if keywords and not any(keyword in title for keyword in keywords):
        return False

    return True


def resolve_post_url(site: dict, base_url: str, link: Tag | None) -> str:
    if link is None:
        return ""

    href = link.get("href", "")
    if href and not href.lower().startswith("javascript:"):
        return urljoin(base_url, href)

    detail_url_template = site.get("detail_url_template")
    script_text = " ".join([href, link.get("onclick", "")])
    match = re.search(r"['\"]([^'\"]+)['\"]", script_text)
    if detail_url_template and match:
        return urljoin(base_url, detail_url_template.format(id=match.group(1)))

    return href


def find_title_cell(cells: list[Tag]) -> Tag | None:
    for cell in cells:
        link = cell.find("a", href=True)
        if link and clean_text(link.get_text(" ", strip=True)):
            return cell
    return None


def get_cell(cells: list[Tag], index: int | None) -> Tag | None:
    if index is None:
        return None
    if index < 0 or index >= len(cells):
        return None
    return cells[index]


def get_cell_text(cells: list[Tag], index: int | None) -> str:
    cell = get_cell(cells, index)
    if cell is None:
        return ""
    return clean_text(cell.get_text(" ", strip=True))


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def pick_date(text: str) -> str:
    match = DATE_PATTERN.search(text or "")
    if not match:
        return ""
    return normalize_date(match)


def pick_last_date(text: str) -> str:
    matches = list(DATE_PATTERN.finditer(text or ""))
    if not matches:
        return ""
    return normalize_date(matches[-1])


def normalize_date(match: re.Match) -> str:
    year, month, day = match.groups()
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def deadline_status(deadline: str) -> str:
    if not deadline:
        return ""

    try:
        deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()
    except ValueError:
        return ""

    return "마감" if deadline_date < date.today() else "진행중"


def site_region(site: dict) -> str:
    return site.get("region", "")
