from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from collectors.base import RESULT_COLUMNS
from services.config_loader import load_sites_config
from services.runner import collect_jobs


APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "sites_config.json"
DEFAULT_COLLECT_FILTER_NAMES = ["나라일터", "클린아이잡플러스", "잡알리오", "잡아바"]


def normalize_multiselect_values(values: object, options: list[str]) -> list[str]:
    if values is None:
        return list(options)

    if isinstance(values, str):
        previous_values = [values]
    else:
        try:
            previous_values = list(values)
        except TypeError:
            previous_values = [values]

    return [str(value) for value in previous_values if str(value) in options]


def unique_ordered(values: list[str]) -> list[str]:
    unique_values = []
    seen = set()

    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)

    return unique_values


def get_site_filter_name(site: dict) -> str:
    filter_name = str(site.get("filter_name") or "").strip()
    if filter_name:
        return filter_name

    site_name = str(site.get("name", "")).strip()
    if " > " in site_name:
        return site_name.split(" > ", 1)[0].strip()

    return site_name


def get_site_board_name(site: dict) -> str:
    site_name = str(site.get("name", "")).strip()
    if " > " in site_name:
        return site_name.split(" > ", 1)[1].strip()

    return site_name


def normalize_collect_filter_values(
    values: object,
    filter_options: list[str],
    site_name_to_filter_name: dict[str, str],
) -> list[str]:
    if values is None:
        return list(filter_options)

    if isinstance(values, str):
        previous_values = [values]
    else:
        try:
            previous_values = list(values)
        except TypeError:
            previous_values = [values]

    normalized_values = []
    for value in previous_values:
        text = str(value)
        filter_name = text if text in filter_options else site_name_to_filter_name.get(text)
        if filter_name in filter_options and filter_name not in normalized_values:
            normalized_values.append(filter_name)

    return normalized_values


def make_multiselect_options(df: pd.DataFrame | None, column_name: str) -> list[str]:
    if df is None or df.empty or column_name not in df.columns:
        return []

    return sorted({
        value.strip()
        for value in df[column_name].dropna().astype(str).unique().tolist()
        if value and value.strip()
    })


def has_active_filter(df: pd.DataFrame, column_name: str, selected_values: list[str]) -> bool:
    if not selected_values or column_name not in df.columns:
        return False

    options = make_multiselect_options(df, column_name)
    return set(selected_values) != set(options)


def reset_result_filter_state(df: pd.DataFrame) -> None:
    filter_keys = {
        "result_source_filter_출처": "출처",
        "result_region_filter_지역": "지역",
        "result_status_filter_마감여부": "마감여부",
    }

    for session_key, column_name in filter_keys.items():
        st.session_state[session_key] = make_multiselect_options(df, column_name)


def apply_keyword_filter(df: pd.DataFrame, keyword: str) -> pd.DataFrame:
    keyword = keyword.strip()
    if not keyword or df.empty:
        return df

    searchable_columns = ["공고명", "기관/부서", "지역", "출처"]
    mask = pd.Series(False, index=df.index)
    for column in searchable_columns:
        if column in df.columns:
            mask = mask | df[column].astype(str).str.contains(keyword, case=False, na=False, regex=False)

    return df[mask].copy()


def make_excel_download(df: pd.DataFrame) -> bytes:
    df = normalize_result_columns(df)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="채용공고")
    return output.getvalue()


def normalize_result_columns(df: pd.DataFrame) -> pd.DataFrame:
    normalized_df = df.copy()
    if "공고 URL" in normalized_df.columns:
        normalized_df = normalized_df.rename(columns={"공고 URL": "URL"})
    if "첨부파일 URL" in normalized_df.columns:
        normalized_df = normalized_df.drop(columns=["첨부파일 URL"])
    return normalized_df


def render_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --navy: #1f4e79;
            --navy-2: #2b638f;
            --navy-3: #326fa0;
        }

        div[data-testid="stDecoration"] {
            background-image: none !important;
            background-color: var(--navy) !important;
        }

        header[data-testid="stHeader"] {
            height: 0 !important;
            min-height: 0 !important;
            background: transparent !important;
        }

        div[data-testid="stToolbar"] {
            top: 0.35rem !important;
        }

        section[data-testid="stSidebar"] {
            background: #eef3f8;
        }

        section[data-testid="stSidebar"] > div {
            padding-top: 0.25rem !important;
        }

        .stApp .block-container,
        section.main .block-container,
        div[data-testid="stAppViewBlockContainer"] {
            padding-top: 2.5rem !important;
            padding-bottom: 1rem !important;
            max-width: 1500px;
        }

        .stApp h1,
        h1 {
            margin-top: 0 !important;
            padding-top: 0 !important;
            margin-bottom: 0.25rem !important;
            font-size: 2.45rem !important;
        }

        h2, h3 {
            margin-top: 0.2rem !important;
            margin-bottom: 0.1rem !important;
        }

        h3 {
            font-size: 1.25rem !important;
            line-height: 1.25 !important;
        }

        div[data-testid="stCaptionContainer"] {
            margin-bottom: 0 !important;
            padding-bottom: 0 !important;
            font-size: 0.8rem !important;
        }

        div[data-testid="stMarkdownContainer"] p {
            margin-bottom: 0.02rem;
        }

        .stButton > button,
        .stDownloadButton > button {
            background: var(--navy) !important;
            border-color: var(--navy) !important;
            color: white !important;
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover {
            background: var(--navy-2) !important;
            border-color: var(--navy-2) !important;
            color: white !important;
        }

        button:focus,
        button:focus-visible,
        .stButton > button:focus,
        .stButton > button:focus-visible,
        .stDownloadButton > button:focus,
        .stDownloadButton > button:focus-visible {
            border-color: var(--navy-3) !important;
            box-shadow: 0 0 0 2px rgba(50, 111, 160, 0.25) !important;
            outline: none !important;
        }

        [data-testid="stTextInput"] [data-baseweb="input"]:focus-within {
            border-color: var(--navy-3) !important;
            box-shadow: 0 0 0 1px var(--navy-3) !important;
            outline: none !important;
        }

        div[data-baseweb="tag"],
        span[data-baseweb="tag"],
        [data-baseweb="select"] [data-baseweb="tag"],
        [data-baseweb="select"] span[data-baseweb="tag"],
        [data-baseweb="select"] div[data-baseweb="tag"] {
            background-color: var(--navy) !important;
            border-color: var(--navy) !important;
            color: white !important;
        }

        div[data-baseweb="tag"] span,
        span[data-baseweb="tag"] span,
        [data-baseweb="select"] [data-baseweb="tag"] span,
        div[data-baseweb="tag"] svg,
        span[data-baseweb="tag"] svg,
        [data-baseweb="select"] [data-baseweb="tag"] svg {
            color: white !important;
            fill: white !important;
        }

        .info-box {
            min-height: 3.5rem;
            padding: 0.9rem 1rem;
            display: flex;
            align-items: center;
            background: #e8f2ff;
            border-radius: 0.45rem;
            color: #0b4f8a;
            font-weight: 600;
            line-height: 1.45;
            border: 0;
            width: 100%;
            box-sizing: border-box;
        }

        div[data-testid="stDataFrame"] {
            margin-bottom: 0.15rem;
        }

        div[data-testid="stPopover"] button,
        div[data-testid="stHorizontalBlock"] .stButton > button {
            min-height: 1.35rem !important;
            height: 1.35rem !important;
            padding: 0.05rem 0.3rem !important;
            font-size: 0.8rem !important;
            line-height: 1 !important;
            border-radius: 0.3rem !important;
            white-space: nowrap !important;
        }

        div[data-testid="stPopover"] button,
        div[data-testid="stPopover"] button p {
            font-size: 0.72rem !important;
        }

        .filter-count {
            height: 1.35rem;
            display: flex;
            align-items: center;
            justify-content: flex-end;
            color: #52616f;
            font-size: 0.8rem;
            white-space: nowrap;
        }

        .result-note {
            min-height: 2.5rem;
            display: flex;
            align-items: center;
            justify-content: flex-end;
            color: rgba(49, 51, 63, 0.6);
            font-size: 0.8rem;
            font-family: "Source Sans Pro", sans-serif;
            line-height: 1.35;
            text-align: right;
        }

        .site-label-text {
            min-height: 1.35rem;
            display: flex;
            align-items: center;
            color: #1f2937;
            font-size: 0.9rem;
            line-height: 1.35;
            white-space: nowrap;
        }

        section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"]:has(.site-label-text) {
            gap: 0.2rem !important;
            align-items: flex-start !important;
            margin-bottom: 0 !important;
            overflow: visible !important;
        }

        section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"]:has(.site-label-text) .stButton > button {
            width: 1.05rem !important;
            min-width: 1.05rem !important;
            height: 1.05rem !important;
            min-height: 1.05rem !important;
            padding: 0 !important;
            border-radius: 999px !important;
            background: var(--navy) !important;
            border-color: var(--navy) !important;
            color: white !important;
            font-size: 0.68rem !important;
            line-height: 1 !important;
            margin: 0 !important;
            box-shadow: none !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
        }

        section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"]:has(.site-label-text) button[data-testid="stBaseButton-secondary"] {
            width: 1.05rem !important;
            min-width: 1.05rem !important;
            height: 1.05rem !important;
            min-height: 1.05rem !important;
            padding: 0 !important;
            border: 0 !important;
            border-radius: 999px !important;
            background: var(--navy) !important;
            color: white !important;
            box-shadow: none !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            transform: translate(0.35rem, 0.16rem);
            position: relative !important;
            overflow: visible !important;
        }

        section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"]:has(.site-label-text) div[data-testid="stTooltipHoverTarget"] {
            justify-content: flex-end !important;
            overflow: visible !important;
        }

        section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"]:has(.site-label-text) div[data-testid="column"]:has(button[data-testid="stBaseButton-secondary"]) {
            position: relative !important;
            overflow: visible !important;
        }

        section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"]:has(.site-label-text) button[data-testid="stBaseButton-secondary"]:hover::after {
            content: "선택한 사이트 전체 삭제";
            position: absolute;
            right: 1.35rem;
            top: -0.12rem;
            z-index: 9999;
            width: max-content;
            max-width: 12rem;
            padding: 0.25rem 0.45rem;
            border-radius: 0.45rem;
            background: white;
            border: 1px solid rgba(31, 78, 121, 0.16);
            box-shadow: 0 2px 8px rgba(15, 23, 42, 0.16);
            color: #1f2937;
            font-size: 0.78rem;
            font-weight: 400;
            line-height: 1.2;
            pointer-events: none;
            display: block;
            white-space: nowrap;
        }

        section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"]:has(.site-label-text) .stButton,
        section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"]:has(.site-label-text) div[data-testid="stButton"] {
            height: 1.35rem !important;
            min-height: 1.35rem !important;
            margin: 0 !important;
            padding: 0 !important;
            display: flex !important;
            align-items: flex-start !important;
        }

        section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"]:has(.site-label-text) .stButton > button p {
            font-size: 0.68rem !important;
            line-height: 1 !important;
            margin: 0 !important;
        }

        section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"]:has(.site-label-text) button[data-testid="stBaseButton-secondary"] p {
            color: white !important;
            font-size: 0.68rem !important;
            line-height: 1.05rem !important;
            margin: 0 !important;
        }

        div[data-testid="stVerticalBlock"] {
            gap: 0.35rem !important;
        }

        div[data-testid="stHorizontalBlock"] {
            gap: 0.45rem !important;
        }

        div[data-testid="stDownloadButton"] {
            margin-top: -0.25rem !important;
        }

        .info-box + div,
        div:has(> .info-box) + div {
            margin-top: 0.2rem !important;
        }

        .info-box {
            margin-bottom: 0.2rem !important;
        }

        div[data-testid="stPopoverBody"] div[data-baseweb="tag"],
        div[data-testid="stPopoverBody"] span[data-baseweb="tag"],
        div[data-testid="stPopoverBody"] [data-baseweb="tag"] {
            min-height: 1.25rem !important;
            height: 1.25rem !important;
            padding: 0.05rem 0.28rem !important;
            font-size: 0.72rem !important;
            border-radius: 0.28rem !important;
        }

        div[data-testid="stPopoverBody"] div[data-baseweb="tag"] span,
        div[data-testid="stPopoverBody"] span[data-baseweb="tag"] span,
        div[data-testid="stPopoverBody"] [data-baseweb="tag"] span {
            font-size: 0.72rem !important;
            line-height: 1 !important;
        }

        div[data-testid="stPopoverBody"] [data-baseweb="select"],
        div[data-testid="stPopoverBody"] [data-baseweb="select"] > div {
            font-size: 0.76rem !important;
        }

        section[data-testid="stSidebar"] [data-testid="stMultiSelect"],
        section[data-testid="stSidebar"] [data-testid="stMultiSelect"] *,
        section[data-testid="stSidebar"] [data-testid="stNumberInput"],
        section[data-testid="stSidebar"] [data-testid="stNumberInput"] * {
            outline: none !important;
            box-shadow: none !important;
        }

        section[data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="select"] {
            border: 0 !important;
            border-radius: 0.45rem !important;
            box-shadow: none !important;
            outline: none !important;
            cursor: pointer !important;
            transition: box-shadow 0.15s ease, background-color 0.15s ease !important;
        }

        section[data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="select"]:hover {
            box-shadow: inset 0 0 0 2px rgba(50, 111, 160, 0.62) !important;
        }

        section[data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="select"]:focus-within {
            border: 0 !important;
            box-shadow: inset 0 0 0 2px var(--navy-3) !important;
        }

        section[data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="select"] > div,
        section[data-testid="stSidebar"] [data-testid="stMultiSelect"] input,
        section[data-testid="stSidebar"] [data-testid="stMultiSelect"] [aria-invalid="true"] {
            border: 0 !important;
            box-shadow: none !important;
            outline: none !important;
            cursor: pointer !important;
        }

        section[data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="select"] *,
        section[data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="select"] svg,
        section[data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="select"] button,
        section[data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="select"] [role="button"] {
            cursor: pointer !important;
        }

        section[data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="select"] > div:last-child,
        section[data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="select"] > div:last-child svg {
            color: #3f4d5a !important;
            fill: #3f4d5a !important;
            transition: color 0.15s ease, fill 0.15s ease, background-color 0.15s ease, transform 0.15s ease !important;
        }

        section[data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="select"]:hover > div:last-child {
            background-color: rgba(31, 78, 121, 0.08) !important;
            border-radius: 0.35rem !important;
        }

        section[data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="select"]:hover > div:last-child svg {
            color: var(--navy) !important;
            fill: var(--navy) !important;
            transform: scale(1.08);
        }

        section[data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="tag"] {
            cursor: default !important;
        }

        section[data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="tag"] svg,
        section[data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="tag"] [role="button"] {
            cursor: pointer !important;
        }

        section[data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="select"] [data-baseweb="tag"] svg,
        section[data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="select"] [data-baseweb="tag"] svg path,
        section[data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="select"] [data-baseweb="tag"] [data-baseweb="icon"],
        section[data-testid="stSidebar"] [data-testid="stMultiSelect"] [data-baseweb="select"] [data-baseweb="tag"] [role="button"] {
            color: white !important;
            fill: white !important;
            opacity: 1 !important;
        }

        section[data-testid="stSidebar"] [data-testid="stMultiSelect"] button[aria-label="Clear all"] {
            display: none !important;
        }

        section[data-testid="stSidebar"] [data-testid="stMultiSelect"] [aria-label="Clear all"] {
            display: none !important;
        }

        section[data-testid="stSidebar"] [data-testid="stNumberInput"] > div:has(input) {
            border: 0 !important;
            border-radius: 0.45rem !important;
            box-shadow: none !important;
            outline: none !important;
            overflow: hidden !important;
        }

        section[data-testid="stSidebar"] [data-testid="stNumberInput"] > div:has(input:focus) {
            border: 2px solid var(--navy-3) !important;
        }

        section[data-testid="stSidebar"] [data-testid="stNumberInput"] > div:has(input) *,
        section[data-testid="stSidebar"] [data-testid="stNumberInput"] [data-baseweb="input"],
        section[data-testid="stSidebar"] [data-testid="stNumberInput"] [data-baseweb="base-input"],
        section[data-testid="stSidebar"] [data-testid="stNumberInput"] input,
        section[data-testid="stSidebar"] [data-testid="stNumberInput"] button {
            border: 0 !important;
            box-shadow: none !important;
            outline: none !important;
        }

        section[data-testid="stSidebar"] [data-testid="stNumberInput"] button {
            background: transparent !important;
        }
        </style>
        <script>
            document.documentElement.setAttribute("lang", "ko");
        </script>
        """,
        unsafe_allow_html=True,
    )


def render_result_controls(df: pd.DataFrame) -> pd.DataFrame:
    for legacy_key in ("filter_출처", "filter_지역", "filter_마감여부"):
        st.session_state.pop(legacy_key, None)

    st.markdown('<div class="filter-row">', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns([0.8, 0.8, 0.9, 3.7])

    with col1:
        source_filter = render_multiselect_filter(
            df,
            "출처",
            "출처 필터",
            key_prefix="result_source_filter",
        )
    with col2:
        region_filter = render_multiselect_filter(
            df,
            "지역",
            "지역 필터",
            key_prefix="result_region_filter",
        )
    with col3:
        status_filter = render_multiselect_filter(
            df,
            "마감여부",
            "마감여부 필터",
            key_prefix="result_status_filter",
        )
    filtered_df = df.copy()

    if has_active_filter(df, "출처", source_filter):
        filtered_df = filtered_df[filtered_df["출처"].isin(source_filter)]

    if has_active_filter(df, "지역", region_filter):
        filtered_df = filtered_df[filtered_df["지역"].isin(region_filter)]

    if has_active_filter(df, "마감여부", status_filter):
        filtered_df = filtered_df[filtered_df["마감여부"].isin(status_filter)]

    st.session_state["deadline_sort"] = None

    with col4:
        st.markdown(
            f'<div class="filter-count">표시 {len(filtered_df):,}건 / 전체 {len(df):,}건</div>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)
    return filtered_df


def render_multiselect_filter(
    df: pd.DataFrame | None,
    column_name: str,
    label: str,
    key_prefix: str = "result_filter",
) -> list[str]:
    session_key = f"{key_prefix}_{column_name}"

    if df is None or df.empty or column_name not in df.columns:
        st.session_state[session_key] = []
        return []

    options = make_multiselect_options(df, column_name)

    if not options:
        st.session_state[session_key] = []
        return []

    safe_default_values = normalize_multiselect_values(
        st.session_state.get(session_key, options),
        options,
    )
    st.session_state[session_key] = safe_default_values

    with st.popover(label, use_container_width=True):
        selected_values = st.multiselect(
            label,
            options=options,
            default=safe_default_values,
            key=session_key,
        )
    return selected_values


def render_result_table(df: pd.DataFrame) -> None:
    df = normalize_result_columns(df)
    styled_df = df.style.apply(format_deadline_row, axis=1)
    st.dataframe(
        styled_df,
        use_container_width=True,
        hide_index=True,
        height=560,
        column_config={
            "URL": st.column_config.LinkColumn("URL", display_text="열기"),
        },
    )


def format_deadline_row(row: pd.Series) -> list[str]:
    if row.get("마감여부") == "마감":
        return ["color: #8a8f98;" for _ in row]
    if row.get("마감여부") == "마감당일":
        return [
            "color: #d32f2f; font-weight: 700;" if column == "마감여부" else ""
            for column in row.index
        ]
    if row.get("마감여부") == "마감전일":
        return [
            "color: #1565c0; font-weight: 700;" if column == "마감여부" else ""
            for column in row.index
        ]
    return ["" for _ in row]


def main() -> None:
    st.set_page_config(page_title="잡아채용", page_icon="🔎", layout="wide")
    render_css()

    st.title("잡아채용")
    st.caption("여러 채용공고 사이트의 공고를 한 번에 수집합니다.")

    sites = load_sites_config(CONFIG_PATH)
    site_name_to_filter_name = {
        site["name"]: get_site_filter_name(site)
        for site in sites
    }
    filter_names = unique_ordered([get_site_filter_name(site) for site in sites])
    default_filter_names = [
        name for name in DEFAULT_COLLECT_FILTER_NAMES
        if name in filter_names
    ]

    previous_filter_names = set(st.session_state.get("collect_site_options_snapshot", []))
    current_filter_names = set(filter_names)
    newly_added_filter_names = [
        name for name in default_filter_names
        if name in current_filter_names and name not in previous_filter_names
    ]

    if "collect_sites" not in st.session_state:
        st.session_state["collect_sites"] = default_filter_names
    else:
        normalized_collect_sites = normalize_collect_filter_values(
            st.session_state.get("collect_sites"),
            filter_names,
            site_name_to_filter_name,
        )
        for filter_name in newly_added_filter_names:
            if filter_name not in normalized_collect_sites:
                normalized_collect_sites.append(filter_name)
        st.session_state["collect_sites"] = normalized_collect_sites

    st.session_state["collect_site_options_snapshot"] = filter_names

    with st.sidebar:
        st.header("설정")
        site_label_col, site_clear_col = st.columns([0.88, 0.12])
        with site_label_col:
            st.markdown('<div class="site-label-text">수집할 사이트</div>', unsafe_allow_html=True)
        with site_clear_col:
            if st.button("×", key="clear_collect_sites"):
                st.session_state["collect_sites"] = []

        selected_filter_names = st.multiselect(
            "수집할 사이트",
            options=filter_names,
            default=st.session_state["collect_sites"],
            key="collect_sites",
            label_visibility="collapsed",
        )
        search_keyword = st.text_input(
            "검색어",
            value="",
            placeholder="예: 지역, 기간제, 문화재단, 합격자",
        )
        max_items = st.number_input("사이트별 최대 수집 갯수", min_value=1, max_value=100, value=20)
        run_button = st.button("수집 시작", type="primary", use_container_width=True)

    selected_filter_names = normalize_collect_filter_values(
        selected_filter_names,
        filter_names,
        site_name_to_filter_name,
    )
    selected_filter_name_set = set(selected_filter_names)
    selected_sites = [
        site for site in sites
        if get_site_filter_name(site) in selected_filter_name_set
    ]

    if not sites:
        st.warning("sites_config.json에 사이트 정보가 없습니다.")
        return

    if run_button:
        if not selected_sites:
            st.warning("수집할 사이트를 1개 이상 선택하세요.")
            return

        if hasattr(st, "cache_data"):
            st.cache_data.clear()

        with st.spinner("채용공고를 수집하는 중입니다..."):
            rows = collect_jobs(
                sites=selected_sites,
                search_keyword=search_keyword.strip(),
                max_items=int(max_items),
            )

        raw_df = normalize_result_columns(pd.DataFrame(rows, columns=RESULT_COLUMNS))
        df = apply_keyword_filter(raw_df, search_keyword.strip())
        st.session_state["result_df"] = df
        st.session_state["last_collected_sites"] = selected_filter_names
        reset_result_filter_state(df)
    else:
        st.markdown(
            '<div class="info-box">왼쪽에서 사이트와 검색어를 선택한 뒤 수집을 시작하세요.</div>',
            unsafe_allow_html=True,
        )

    result_df = st.session_state.get("result_df")
    if result_df is not None:
        st.subheader("수집 결과")
        result_df = normalize_result_columns(result_df)
        display_df = render_result_controls(result_df)
        render_result_table(display_df)

        excel_data = make_excel_download(display_df)
        download_col, note_col = st.columns([0.28, 1.72])
        with download_col:
            st.download_button(
                label="Excel 다운로드",
                data=excel_data,
                file_name="jaba_recruit_jobs.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        with note_col:
            st.markdown(
                '<div class="result-note">수집 누락 된 공고가 있을 수 있습니다. 홈페이지를 확인하세요.</div>',
                unsafe_allow_html=True,
            )


if __name__ == "__main__":
    main()
