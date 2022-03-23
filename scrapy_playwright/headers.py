"""
This module includes functions to process request headers.
Refer to the PLAYWRIGHT_PROCESS_REQUEST_HEADERS setting for more information.
"""

from urllib.parse import urlparse

from playwright.async_api import Request as PlaywrightRequest
from scrapy.http.headers import Headers


async def use_scrapy_headers(
    browser_type: str,
    playwright_request: PlaywrightRequest,
    scrapy_headers: Headers,
) -> dict:
    """Scrapy headers take precedence over Playwright headers for navigation requests.
    For non-navigation requests, only User-Agent is taken from the Scrapy headers."""

    headers = scrapy_headers.to_unicode_dict()

    # Scrapy's user agent has priority over Playwright's
    headers.setdefault("user-agent", playwright_request.headers.get("user-agent"))

    if playwright_request.is_navigation_request():
        if browser_type == "firefox":
            # otherwise this fails with playwright.helper.Error: NS_ERROR_NET_RESET
            headers["host"] = urlparse(playwright_request.url).netloc
        return headers

    # override user agent, for consistency with other requests
    if headers.get("user-agent"):
        playwright_request.headers["user-agent"] = headers["user-agent"]
    return playwright_request.headers


async def use_playwright_headers(
    browser_type: str,
    playwright_request: PlaywrightRequest,
    scrapy_headers: Headers,
) -> dict:
    """Return headers from the Playwright request, unaltered"""
    return playwright_request.headers
