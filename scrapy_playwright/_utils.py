import logging
from typing import Awaitable, Callable, Iterator, Optional, Tuple, Union

from playwright.async_api import (
    Error,
    Page,
    Request as PlaywrightRequest,
    Response as PlaywrightResponse,
)
from scrapy import Spider
from scrapy.http import Request as ScrapyRequest
from scrapy.http.headers import Headers
from scrapy.settings import Settings
from scrapy.utils.misc import load_object
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
        if _NAVIGATION_ERROR_MSG in err.message:
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


def _get_float_setting(settings: Settings, key: str) -> Optional[float]:
    try:
        return float(settings[key])
    except Exception:
        return None


async def _get_header_value(
    resource: Union[PlaywrightRequest, PlaywrightResponse],
    header_name: str,
) -> Optional[str]:
    try:
        return await resource.header_value(header_name)
    except Exception:
        return None


def _attach_page_event_handlers(
    page: Page, request: ScrapyRequest, spider: Spider, context_name: str
) -> None:
    event_handlers = request.meta.get("playwright_page_event_handlers") or {}
    for event, handler in event_handlers.items():
        if callable(handler):
            page.on(event, handler)
        elif isinstance(handler, str):
            try:
                page.on(event, getattr(spider, handler))
            except AttributeError as ex:
                logger.warning(
                    "Spider '%s' does not have a '%s' attribute,"
                    " ignoring handler for event '%s'",
                    spider.name,
                    handler,
                    event,
                    extra={
                        "spider": spider,
                        "context_name": context_name,
                        "scrapy_request_url": request.url,
                        "scrapy_request_method": request.method,
                        "exception": ex,
                    },
                    exc_info=True,
                )


async def _set_redirect_meta(request: ScrapyRequest, response: PlaywrightResponse) -> None:
    """Update a Scrapy request with metadata about redirects."""
    redirect_times: int = 0
    redirect_urls: list = []
    redirect_reasons: list = []
    redirected = response.request.redirected_from
    while redirected is not None:
        redirect_times += 1
        redirect_urls.append(redirected.url)
        redirected_response = await redirected.response()
        reason = None if redirected_response is None else redirected_response.status
        redirect_reasons.append(reason)
        redirected = redirected.redirected_from
    if redirect_times:
        request.meta["redirect_times"] = redirect_times
        request.meta["redirect_urls"] = list(reversed(redirect_urls))
        request.meta["redirect_reasons"] = list(reversed(redirect_reasons))


async def _maybe_execute_page_init_callback(
    page: Page,
    request: ScrapyRequest,
    context_name: str,
    spider: Spider,
) -> None:
    page_init_callback = request.meta.get("playwright_page_init_callback")
    if page_init_callback:
        try:
            page_init_callback = load_object(page_init_callback)
            await page_init_callback(page, request)
        except Exception as ex:
            logger.warning(
                "[Context=%s] Page init callback exception for %s exc_type=%s exc_msg=%s",
                context_name,
                repr(request),
                type(ex),
                str(ex),
                extra={
                    "spider": spider,
                    "context_name": context_name,
                    "scrapy_request_url": request.url,
                    "scrapy_request_method": request.method,
                    "exception": ex,
                },
                exc_info=True,
            )


def _make_request_logger(context_name: str, spider: Spider) -> Callable:
    async def _log_request(request: PlaywrightRequest) -> None:
        log_args = [context_name, request.method.upper(), request.url, request.resource_type]
        referrer = await _get_header_value(request, "referer")
        if referrer:
            log_args.append(referrer)
            log_msg = "[Context=%s] Request: <%s %s> (resource type: %s, referrer: %s)"
        else:
            log_msg = "[Context=%s] Request: <%s %s> (resource type: %s)"
        logger.debug(
            log_msg,
            *log_args,
            extra={
                "spider": spider,
                "context_name": context_name,
                "playwright_request_url": request.url,
                "playwright_request_method": request.method,
                "playwright_resource_type": request.resource_type,
            },
        )

    return _log_request


def _make_response_logger(context_name: str, spider: Spider) -> Callable:
    async def _log_response(response: PlaywrightResponse) -> None:
        log_args = [context_name, response.status, response.url]
        location = await _get_header_value(response, "location")
        if location:
            log_args.append(location)
            log_msg = "[Context=%s] Response: <%i %s> (location: %s)"
        else:
            log_msg = "[Context=%s] Response: <%i %s>"
        logger.debug(
            log_msg,
            *log_args,
            extra={
                "spider": spider,
                "context_name": context_name,
                "playwright_response_url": response.url,
                "playwright_response_status": response.status,
            },
        )

    return _log_response
