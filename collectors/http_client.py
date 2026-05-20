from __future__ import annotations

import json
from typing import Any

import requests


DEFAULT_TIMEOUT = 25
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
    "application/json;q=0.8,*/*;q=0.7",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
}


class NetworkRequestError(RuntimeError):
    def __init__(self, user_message: str, original: BaseException | None = None) -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.original = original


def browser_headers(**headers: str) -> dict[str, str]:
    merged = DEFAULT_HEADERS.copy()
    for key, value in headers.items():
        if value:
            merged[key.replace("_", "-")] = value
    return merged


def get(url: str, **kwargs: Any) -> requests.Response:
    return request("GET", url, **kwargs)


def post(url: str, **kwargs: Any) -> requests.Response:
    return request("POST", url, **kwargs)


def request(method: str, url: str, **kwargs: Any) -> requests.Response:
    headers = browser_headers(**kwargs.pop("headers", {}))
    timeout = kwargs.pop("timeout", DEFAULT_TIMEOUT)

    try:
        response = requests.request(method, url, headers=headers, timeout=timeout, **kwargs)
        response.raise_for_status()
        return response
    except requests.exceptions.Timeout as error:
        raise NetworkRequestError(
            "접속 지연: 서버 응답 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.",
            error,
        ) from error
    except requests.exceptions.ConnectionError as error:
        if _contains_connection_reset(error):
            message = "접속 실패: 서버가 연결을 종료했습니다. 잠시 후 다시 시도해 주세요."
        else:
            message = "접속 실패: 서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요."
        raise NetworkRequestError(message, error) from error
    except ConnectionResetError as error:
        raise NetworkRequestError(
            "접속 실패: 서버가 연결을 종료했습니다. 잠시 후 다시 시도해 주세요.",
            error,
        ) from error
    except requests.exceptions.RequestException as error:
        raise NetworkRequestError(
            "접속 실패: 요청 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
            error,
        ) from error


def fetch_html_with_playwright(url: str, *, params: dict[str, str] | None = None) -> str:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as error:
        raise NetworkRequestError(
            "접속 실패: requests와 Playwright fallback 모두 사용할 수 없습니다.",
            error,
        ) from error

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(extra_http_headers=browser_headers(), locale="ko-KR")
            response = context.request.get(url, params=params or {}, timeout=DEFAULT_TIMEOUT * 1000)
            if not response.ok:
                raise NetworkRequestError(
                    f"접속 실패: 서버 응답 코드가 {response.status}입니다. 잠시 후 다시 시도해 주세요."
                )
            text = response.text()
            browser.close()
            return text
    except NetworkRequestError:
        raise
    except Exception as error:
        raise NetworkRequestError(
            "접속 실패: Playwright fallback 수집 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
            error,
        ) from error


def fetch_json_with_playwright(
    url: str,
    *,
    payload: dict[str, Any],
    referer: str,
) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as error:
        raise NetworkRequestError(
            "접속 실패: requests와 Playwright fallback 모두 사용할 수 없습니다.",
            error,
        ) from error

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                extra_http_headers=browser_headers(
                    Referer=referer,
                    Accept="application/json, text/javascript, */*; q=0.01",
                    Content_Type="application/json;charset=UTF-8",
                    X_Requested_With="XMLHttpRequest",
                ),
                locale="ko-KR",
            )
            response = context.request.post(
                url,
                data=json.dumps(payload, ensure_ascii=False),
                headers={"Content-Type": "application/json;charset=UTF-8"},
                timeout=DEFAULT_TIMEOUT * 1000,
            )
            if not response.ok:
                raise NetworkRequestError(
                    f"접속 실패: 서버 응답 코드가 {response.status}입니다. 잠시 후 다시 시도해 주세요."
                )
            data = response.json()
            browser.close()
            return data
    except NetworkRequestError:
        raise
    except Exception as error:
        raise NetworkRequestError(
            "접속 실패: Playwright fallback 수집 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
            error,
        ) from error


def friendly_error_message(error: BaseException) -> str:
    if isinstance(error, NetworkRequestError):
        return error.user_message
    if isinstance(error, TimeoutError):
        return "접속 지연: 서버 응답 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요."
    if isinstance(error, ConnectionResetError) or _contains_connection_reset(error):
        return "접속 실패: 서버가 연결을 종료했습니다. 잠시 후 다시 시도해 주세요."
    if isinstance(error, requests.exceptions.ConnectionError):
        return "접속 실패: 서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요."
    if isinstance(error, requests.exceptions.Timeout):
        return "접속 지연: 서버 응답 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요."
    return "수집 실패: 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."


def _contains_connection_reset(error: BaseException) -> bool:
    text = repr(error)
    return "ConnectionResetError" in text or "Connection reset by peer" in text
