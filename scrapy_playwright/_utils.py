import asyncio
import logging
import platform
import threading
from typing import Awaitable, Iterator, Optional, Tuple, Union

import scrapy
from playwright.async_api import Error, Page, Request, Response
from scrapy.http.headers import Headers
from scrapy.utils.python import to_unicode
from twisted.internet.defer import Deferred
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
    spider: scrapy.Spider,
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


async def _get_header_value(
    resource: Union[Request, Response],
    header_name: str,
) -> Optional[str]:
    try:
        return await resource.header_value(header_name)
    except Exception:
        return None


if platform.system() == "Windows":

    class _ThreadedLoopAdapter:
        """Utility class to start an asyncio event loop in a new thread and redirect coroutines.
        This allows to run Playwright in a different loop than the Scrapy crawler, allowing to
        use ProactorEventLoop which is supported by Playwright on Windows.
        """

        _loop: asyncio.AbstractEventLoop
        _thread: threading.Thread
        _coro_queue: asyncio.Queue = asyncio.Queue()
        _stop_event: asyncio.Event = asyncio.Event()

        @classmethod
        async def _handle_coro(cls, coro, future) -> None:
            try:
                future.set_result(await coro)
            except Exception as exc:
                future.set_exception(exc)

        @classmethod
        async def _process_queue(cls) -> None:
            while not cls._stop_event.is_set():
                coro, future = await cls._coro_queue.get()
                asyncio.create_task(cls._handle_coro(coro, future))
                cls._coro_queue.task_done()

        @classmethod
        def _deferred_from_coro(cls, coro) -> Deferred:
            future: asyncio.Future = asyncio.Future()
            asyncio.run_coroutine_threadsafe(cls._coro_queue.put((coro, future)), cls._loop)
            return scrapy.utils.defer.deferred_from_coro(future)

        @classmethod
        def start(cls) -> None:
            policy = asyncio.WindowsProactorEventLoopPolicy()  # type: ignore[attr-defined]
            cls._loop = policy.new_event_loop()
            asyncio.set_event_loop(cls._loop)

            cls._thread = threading.Thread(target=cls._loop.run_forever, daemon=True)
            cls._thread.start()
            logger.info("Started loop on separate thread: %s", cls._loop)

            asyncio.run_coroutine_threadsafe(cls._process_queue(), cls._loop)

        @classmethod
        def stop(cls) -> None:
            cls._stop_event.set()
            asyncio.run_coroutine_threadsafe(cls._coro_queue.join(), cls._loop)
            cls._loop.call_soon_threadsafe(cls._loop.stop)
            cls._thread.join()

    _deferred_from_coro = _ThreadedLoopAdapter._deferred_from_coro
else:

    class _ThreadedLoopAdapter:  # type: ignore[no-redef]
        @classmethod
        def start(cls) -> None:
            pass

        @classmethod
        def stop(cls) -> None:
            pass

    _deferred_from_coro = scrapy.utils.defer.deferred_from_coro
