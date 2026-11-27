"""
This module includes functions to process request headers.
Refer to the PLAYWRIGHT_PROCESS_REQUEST_HEADERS setting for more information.
"""

from collections import UserDict
from typing import Dict, List
from urllib.parse import urlparse

from playwright.async_api import Request as PlaywrightRequest
from scrapy import version_info as scrapy_version_info
from scrapy.http import Headers


_SCRAPY_TO_TUPLE_LIST = scrapy_version_info >= (2, 15, 0)


class _CaseInsensitiveDict(UserDict):
    """Keys keep their case, lookups ignore it, like the dict returned by
    Headers.to_unicode_dict()."""

    def __init__(self) -> None:
        self._keys: Dict[str, str] = {}
        super().__init__()

    def __getitem__(self, key: str) -> str:
        return self.data[self._keys[key.lower()]]

    def __setitem__(self, key: str, value: str) -> None:
        if key in self:
            del self[key]
        self.data[key] = value
        self._keys[key.lower()] = key

    def __delitem__(self, key: str) -> None:
        del self.data[self._keys.pop(key.lower())]

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and key.lower() in self._keys


def _scrapy_headers_to_dict(headers: Headers) -> Dict[str, str]:
    """Same result as Headers.to_unicode_dict(): repeated headers are merged
    into a single comma-separated value, headers without values are kept
    with an empty value."""
    if not _SCRAPY_TO_TUPLE_LIST:
        return headers.to_unicode_dict()
    # to_tuple_list() skips headers without values, so take the names from headers
    values: Dict[str, List[str]] = {
        key.decode(headers.encoding, errors="replace"): [] for key in headers
    }
    for key, value in headers.to_tuple_list():
        values[key].append(value)
    result = _CaseInsensitiveDict()
    for key, key_values in values.items():
        result[key] = ",".join(key_values)
    return result  # type: ignore[return-value]


async def use_scrapy_headers(
    *,
    browser_type_name: str,
    playwright_request: PlaywrightRequest,
    scrapy_request_data: dict,
) -> Dict[str, str]:
    """Scrapy headers take precedence over Playwright headers for navigation requests.
    For non-navigation requests, only User-Agent is taken from the Scrapy headers."""

    scrapy_headers_str = _scrapy_headers_to_dict(scrapy_request_data["headers"])
    playwright_headers = await playwright_request.all_headers()

    # Scrapy's user agent has priority over Playwright's
    scrapy_headers_str.setdefault("user-agent", playwright_headers.get("user-agent"))

    if playwright_request.is_navigation_request():
        # if referer header is set via playwright_page_goto_kwargs
        if referer := playwright_headers.get("referer"):
            scrapy_headers_str.setdefault("referer", referer)

        # otherwise it fails with playwright.helper.Error: NS_ERROR_NET_RESET
        if browser_type_name == "firefox":
            scrapy_headers_str["host"] = urlparse(playwright_request.url).netloc

        return scrapy_headers_str

    # override user agent, for consistency with other requests
    if scrapy_headers_str.get("user-agent"):
        playwright_headers["user-agent"] = scrapy_headers_str["user-agent"]
    return playwright_headers
