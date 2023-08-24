import logging
from typing import Awaitable, Iterator, Optional, Tuple, Union

from playwright.async_api import Error, Page, Request, Response
from scrapy import Spider
from scrapy.http.headers import Headers
from scrapy.utils.python import to_unicode
from w3lib.encoding import html_body_declared_encoding, http_content_type_encoding


logger = logging.getLogger("scrapy-playwright")


async def _maybe_await(obj):
    if isinstance(obj, Awaitable):
        return await obj
    return obj


def _possible_encodings(headers: Headers, text: str) -> Iterator[str]:
    if headers.get("content-type"):
        content_type = to_unicode(headers["content-type"])
        yield http_content_type_encoding(content_type)
    yield html_body_declared_encoding(text)


def _encode_body(headers: Headers, text: str) -> Tuple[bytes, str]:
    for encoding in filter(None, _possible_encodings(headers, text)):
        try:
            body = text.encode(encoding)
        except UnicodeEncodeError:
            pass
        else:
            return body, encoding
    return text.encode("utf-8"), "utf-8"  # fallback


def _is_safe_close_error(error: Error) -> bool:
    """
    Taken almost verbatim from
    https://github.com/microsoft/playwright-python/blob/v1.20.0/playwright/_impl/_helper.py#L234-L238
    """
    message = str(error)
    return message.endswith("Browser has been closed") or message.endswith(
        "Target page, context or browser has been closed"
    )


_NAVIGATION_ERROR_MSG = (
    "Unable to retrieve content because the page is navigating and changing the content."
)


async def _get_page_content(
    page: Page,
    spider: Spider,
    context_name: str,
    scrapy_request_url: str,
    scrapy_request_method: str,
) -> str:
    """Wrapper around Page.content to retry if necessary.
    Arguments other than the page are only for logging.
    """
    try:
        return await page.content()
    except Error as err:
        if err.message == _NAVIGATION_ERROR_MSG:
            logger.debug(
                "Retrying to get content from page '%s', error: '%s'",
                page.url,
                _NAVIGATION_ERROR_MSG,
                extra={
                    "spider": spider,
                    "context_name": context_name,
                    "scrapy_request_url": scrapy_request_url,
                    "scrapy_request_method": scrapy_request_method,
                    "playwright_page_url": page.url,
                },
            )
            return await page.content()
        raise


async def _get_header_value(
    resource: Union[Request, Response],
    header_name: str,
) -> Optional[str]:
    try:
        return await resource.header_value(header_name)
    except Exception:
        return None
