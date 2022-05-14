"""
This module includes functions to process request headers.
Refer to the PLAYWRIGHT_PROCESS_REQUEST_HEADERS setting for more information.
"""
import warnings
from urllib.parse import urlparse

from playwright.async_api import Request as PlaywrightRequest
from scrapy.exceptions import ScrapyDeprecationWarning
from scrapy.http.headers import Headers


async def use_scrapy_headers(
    browser_type: str,
    playwright_request: PlaywrightRequest,
    scrapy_headers: Headers,
) -> dict:
    """Scrapy headers take precedence over Playwright headers for navigation requests.
    For non-navigation requests, only User-Agent is taken from the Scrapy headers."""

    scrapy_headers_str = scrapy_headers.to_unicode_dict()
    playwright_headers = await playwright_request.all_headers()

    # Scrapy's user agent has priority over Playwright's
    scrapy_headers_str.setdefault("user-agent", playwright_headers.get("user-agent"))

    if playwright_request.is_navigation_request():
        if browser_type == "firefox":
            # otherwise this fails with playwright.helper.Error: NS_ERROR_NET_RESET
            scrapy_headers_str["host"] = urlparse(playwright_request.url).netloc
        return scrapy_headers_str

    # override user agent, for consistency with other requests
    if scrapy_headers_str.get("user-agent"):
        playwright_headers["user-agent"] = scrapy_headers_str["user-agent"]
    return playwright_headers


async def use_playwright_headers(
    browser_type: str,
    playwright_request: PlaywrightRequest,
    scrapy_headers: Headers,
) -> dict:
    warnings.warn(
        "The 'scrapy_playwright.headers.use_playwright_headers' function is"
        " deprecated, please set 'PLAYWRIGHT_PROCESS_REQUEST_HEADERS=None'"
        " instead.",
        category=ScrapyDeprecationWarning,
        stacklevel=1,
    )
    return await playwright_request.all_headers()
