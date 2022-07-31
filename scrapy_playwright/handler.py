import asyncio
import logging
import warnings
from contextlib import suppress
from dataclasses import dataclass
from ipaddress import ip_address
from time import time
from typing import Awaitable, Callable, Dict, Generator, Optional, Tuple, Type, TypeVar, Union

from playwright.async_api import (
    Browser,
    BrowserContext,
    BrowserType,
    Page,
    PlaywrightContextManager,
    Request as PlaywrightRequest,
    Response as PlaywrightResponse,
    Route,
)
from scrapy import Spider, signals
from scrapy.core.downloader.handlers.http import HTTPDownloadHandler
from scrapy.crawler import Crawler
from scrapy.exceptions import ScrapyDeprecationWarning
from scrapy.http import Request, Response
from scrapy.http.headers import Headers
from scrapy.responsetypes import responsetypes
from scrapy.utils.defer import deferred_from_coro
from scrapy.utils.misc import load_object
from scrapy.utils.python import to_unicode
from scrapy.utils.reactor import verify_installed_reactor
from twisted.internet.defer import Deferred, inlineCallbacks
from w3lib.encoding import html_body_declared_encoding, http_content_type_encoding

from scrapy_playwright.headers import use_scrapy_headers, use_playwright_headers
from scrapy_playwright.page import PageMethod


__all__ = ["ScrapyPlaywrightDownloadHandler"]


PlaywrightHandler = TypeVar("PlaywrightHandler", bound="ScrapyPlaywrightDownloadHandler")


logger = logging.getLogger("scrapy-playwright")


DEFAULT_BROWSER_TYPE = "chromium"
DEFAULT_CONTEXT_NAME = "default"
PERSISTENT_CONTEXT_PATH_KEY = "user_data_dir"


@dataclass
class BrowserContextWrapper:
    context: BrowserContext
    semaphore: asyncio.Semaphore
    persistent: bool


class ScrapyPlaywrightDownloadHandler(HTTPDownloadHandler):
    def __init__(self, crawler: Crawler) -> None:
        settings = crawler.settings
        super().__init__(settings=settings, crawler=crawler)
        verify_installed_reactor("twisted.internet.asyncioreactor.AsyncioSelectorReactor")
        crawler.signals.connect(self._engine_started, signals.engine_started)
        self.stats = crawler.stats

        # browser
        self.browser_type_name = settings.get("PLAYWRIGHT_BROWSER_TYPE") or DEFAULT_BROWSER_TYPE
        self.browser_launch_lock = asyncio.Lock()
        self.launch_options: dict = settings.getdict("PLAYWRIGHT_LAUNCH_OPTIONS") or {}

        # contexts
        self.max_pages_per_context: int = settings.getint(
            "PLAYWRIGHT_MAX_PAGES_PER_CONTEXT"
        ) or settings.getint("CONCURRENT_REQUESTS")
        self.context_launch_lock = asyncio.Lock()
        self.contexts: Dict[str, BrowserContextWrapper] = {}
        self.context_kwargs: dict = settings.getdict("PLAYWRIGHT_CONTEXTS")
        if settings.getint("PLAYWRIGHT_MAX_CONTEXTS"):
            self.context_semaphore = asyncio.Semaphore(
                value=settings.getint("PLAYWRIGHT_MAX_CONTEXTS")
            )

        self.default_navigation_timeout: Optional[float] = None
        if "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT" in settings:
            with suppress(TypeError, ValueError):
                self.default_navigation_timeout = float(
                    settings.get("PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT")
                )

        # headers
        if "PLAYWRIGHT_PROCESS_REQUEST_HEADERS" in settings:
            if settings["PLAYWRIGHT_PROCESS_REQUEST_HEADERS"] is None:
                self.process_request_headers = None
            else:
                self.process_request_headers = load_object(
                    settings["PLAYWRIGHT_PROCESS_REQUEST_HEADERS"]
                )
                if self.process_request_headers is use_playwright_headers:
                    warnings.warn(
                        "The 'scrapy_playwright.headers.use_playwright_headers' function is"
                        " deprecated, please set 'PLAYWRIGHT_PROCESS_REQUEST_HEADERS=None'"
                        " instead.",
                        category=ScrapyDeprecationWarning,
                        stacklevel=1,
                    )
                    self.process_request_headers = None
        else:
            self.process_request_headers = use_scrapy_headers

        self.abort_request: Optional[Callable[[PlaywrightRequest], Union[Awaitable, bool]]] = None
        if settings.get("PLAYWRIGHT_ABORT_REQUEST"):
            self.abort_request = load_object(settings["PLAYWRIGHT_ABORT_REQUEST"])

    @classmethod
    def from_crawler(cls: Type[PlaywrightHandler], crawler: Crawler) -> PlaywrightHandler:
        return cls(crawler)

    def _engine_started(self) -> Deferred:
        """Launch the browser. Use the engine_started signal as it supports returning deferreds."""
        return deferred_from_coro(self._launch())

    async def _launch(self) -> None:
        """Launch Playwright manager and configured startup context(s)."""
        logger.info("Starting download handler")
        self.playwright_context_manager = PlaywrightContextManager()
        self.playwright = await self.playwright_context_manager.start()
        self.browser_type: BrowserType = getattr(self.playwright, self.browser_type_name)
        if self.context_kwargs:
            logger.info(f"Launching {len(self.context_kwargs)} startup context(s)")
            await asyncio.gather(
                *[
                    self._create_browser_context(name=name, context_kwargs=kwargs)
                    for name, kwargs in self.context_kwargs.items()
                ]
            )
            self._set_max_concurrent_context_count()
            logger.info("Startup context(s) launched")
            self.stats.set_value("playwright/page_count", self._get_total_page_count())

    async def _maybe_launch_browser(self) -> None:
        async with self.browser_launch_lock:
            if not hasattr(self, "browser"):
                logger.info(f"Launching browser {self.browser_type.name}")
                self.browser: Browser = await self.browser_type.launch(**self.launch_options)
                logger.info(f"Browser {self.browser_type.name} launched")

    async def _create_browser_context(
        self, name: str, context_kwargs: Optional[dict]
    ) -> BrowserContextWrapper:
        """Create a new context, also launching a browser if necessary."""
        if hasattr(self, "context_semaphore"):
            await self.context_semaphore.acquire()
        context_kwargs = context_kwargs or {}
        if context_kwargs.get(PERSISTENT_CONTEXT_PATH_KEY):
            context = await self.browser_type.launch_persistent_context(**context_kwargs)
            persistent = True
            self.stats.inc_value("playwright/context_count/persistent")
        else:
            await self._maybe_launch_browser()
            context = await self.browser.new_context(**context_kwargs)
            persistent = False
            self.stats.inc_value("playwright/context_count/non-persistent")
        context.on("close", self._make_close_browser_context_callback(name, persistent))
        logger.debug(f"Browser context started: '{name}' (persistent={persistent})")
        self.stats.inc_value("playwright/context_count")
        if self.default_navigation_timeout is not None:
            context.set_default_navigation_timeout(self.default_navigation_timeout)
        self.contexts[name] = BrowserContextWrapper(
            context=context,
            semaphore=asyncio.Semaphore(value=self.max_pages_per_context),
            persistent=persistent,
        )
        self._set_max_concurrent_context_count()
        return self.contexts[name]

    async def _create_page(self, request: Request) -> Page:
        """Create a new page in a context, also creating a new context if necessary."""
        context_name = request.meta.setdefault("playwright_context", DEFAULT_CONTEXT_NAME)
        # this block needs to be locked because several attempts to launch a context
        # with the same name could happen at the same time from different requests
        async with self.context_launch_lock:
            context = self.contexts.get(context_name)
            if context is None:
                context = await self._create_browser_context(
                    name=context_name, context_kwargs=request.meta.get("playwright_context_kwargs")
                )

        await context.semaphore.acquire()
        page = await context.context.new_page()
        self.stats.inc_value("playwright/page_count")
        logger.debug(
            "[Context=%s] New page created, page count is %i (%i for all contexts)",
            context_name,
            len(context.context.pages),
            self._get_total_page_count(),
        )
        self._set_max_concurrent_page_count()
        if self.default_navigation_timeout is not None:
            page.set_default_navigation_timeout(self.default_navigation_timeout)

        page.on("close", self._make_close_page_callback(context_name))
        page.on("crash", self._make_close_page_callback(context_name))
        page.on("request", _make_request_logger(context_name))
        page.on("response", _make_response_logger(context_name))
        page.on("request", self._increment_request_stats)
        page.on("response", self._increment_response_stats)

        return page

    def _get_total_page_count(self):
        return sum([len(ctx.context.pages) for ctx in self.contexts.values()])

    def _set_max_concurrent_page_count(self):
        count = self._get_total_page_count()
        current_max_count = self.stats.get_value("playwright/page_count/max_concurrent")
        if current_max_count is None or count > current_max_count:
            self.stats.set_value("playwright/page_count/max_concurrent", count)

    def _set_max_concurrent_context_count(self):
        current_max_count = self.stats.get_value("playwright/context_count/max_concurrent")
        if current_max_count is None or len(self.contexts) > current_max_count:
            self.stats.set_value("playwright/context_count/max_concurrent", len(self.contexts))

    @inlineCallbacks
    def close(self) -> Deferred:
        logger.info("Closing download handler")
        yield super().close()
        yield deferred_from_coro(self._close())

    async def _close(self) -> None:
        await asyncio.gather(*[ctx.context.close() for ctx in self.contexts.values()])
        self.contexts.clear()
        if hasattr(self, "browser"):
            logger.info("Closing browser")
            await self.browser.close()
        await self.playwright_context_manager.__aexit__()

    def download_request(self, request: Request, spider: Spider) -> Deferred:
        if request.meta.get("playwright"):
            return deferred_from_coro(self._download_request(request, spider))
        return super().download_request(request, spider)

    async def _download_request(self, request: Request, spider: Spider) -> Response:
        page = request.meta.get("playwright_page")
        if not isinstance(page, Page):
            page = await self._create_page(request)

        # attach event handlers
        event_handlers = request.meta.get("playwright_page_event_handlers") or {}
        for event, handler in event_handlers.items():
            if callable(handler):
                page.on(event, handler)
            elif isinstance(handler, str):
                try:
                    page.on(event, getattr(spider, handler))
                except AttributeError:
                    logger.warning(
                        f"Spider '{spider.name}' does not have a '{handler}' attribute,"
                        f" ignoring handler for event '{event}'"
                    )

        await page.unroute("**")
        await page.route(
            "**",
            self._make_request_handler(
                method=request.method,
                scrapy_headers=request.headers,
                body=request.body,
                encoding=getattr(request, "encoding", None),
            ),
        )

        try:
            result = await self._download_request_with_page(request, page)
        except Exception as ex:
            if not request.meta.get("playwright_include_page") and not page.is_closed():
                logger.warning(f"Closing page due to failed request: {request} ({type(ex)})")
                await page.close()
                self.stats.inc_value("playwright/page_count/closed")
            raise
        else:
            return result

    async def _download_request_with_page(self, request: Request, page: Page) -> Response:
        # set this early to make it available in errbacks even if something fails
        if request.meta.get("playwright_include_page"):
            request.meta["playwright_page"] = page

        start_time = time()
        page_goto_kwargs = request.meta.get("playwright_page_goto_kwargs") or {}
        page_goto_kwargs.pop("url", None)
        response = await page.goto(url=request.url, **page_goto_kwargs)
        if response is None:
            logger.warning(
                f"Navigating to {request} returned None, the response"
                " will have empty headers and status 200"
            )
            headers = Headers()
        else:
            headers = Headers(await response.all_headers())
            headers.pop("Content-Encoding", None)
        await self._apply_page_methods(page, request)
        body_str = await page.content()
        request.meta["download_latency"] = time() - start_time

        if not request.meta.get("playwright_include_page"):
            await page.close()
            self.stats.inc_value("playwright/page_count/closed")

        server_ip_address = None
        with suppress(AttributeError, KeyError, ValueError):
            server_addr = await response.server_addr()
            server_ip_address = ip_address(server_addr["ipAddress"])

        with suppress(AttributeError):
            request.meta["playwright_security_details"] = await response.security_details()

        body, encoding = _encode_body(headers=headers, text=body_str)
        respcls = responsetypes.from_args(headers=headers, url=page.url, body=body)
        return respcls(
            url=page.url,
            status=response.status if response is not None else 200,
            headers=headers,
            body=body,
            request=request,
            flags=["playwright"],
            encoding=encoding,
            ip_address=server_ip_address,
        )

    async def _apply_page_methods(self, page: Page, request: Request) -> None:
        page_methods = request.meta.get("playwright_page_methods") or ()

        if not page_methods and "playwright_page_coroutines" in request.meta:
            page_methods = request.meta["playwright_page_coroutines"]
            warnings.warn(
                "The 'playwright_page_coroutines' request meta key is deprecated,"
                " please use 'playwright_page_methods' instead.",
                category=ScrapyDeprecationWarning,
                stacklevel=1,
            )

        if isinstance(page_methods, dict):
            page_methods = page_methods.values()
        for pm in page_methods:
            if isinstance(pm, PageMethod):
                try:
                    method = getattr(page, pm.method)
                except AttributeError:
                    logger.warning(f"Ignoring {repr(pm)}: could not find method")
                else:
                    pm.result = await _maybe_await(method(*pm.args, **pm.kwargs))
                    await page.wait_for_load_state(timeout=self.default_navigation_timeout)
            else:
                logger.warning(f"Ignoring {repr(pm)}: expected PageMethod, got {repr(type(pm))}")

    def _increment_request_stats(self, request: PlaywrightRequest) -> None:
        stats_prefix = "playwright/request_count"
        self.stats.inc_value(stats_prefix)
        self.stats.inc_value(f"{stats_prefix}/resource_type/{request.resource_type}")
        self.stats.inc_value(f"{stats_prefix}/method/{request.method}")
        if request.is_navigation_request():
            self.stats.inc_value(f"{stats_prefix}/navigation")

    def _increment_response_stats(self, response: PlaywrightResponse) -> None:
        stats_prefix = "playwright/response_count"
        self.stats.inc_value(stats_prefix)
        self.stats.inc_value(f"{stats_prefix}/resource_type/{response.request.resource_type}")
        self.stats.inc_value(f"{stats_prefix}/method/{response.request.method}")

    def _make_close_page_callback(self, context_name: str) -> Callable:
        def close_page_callback() -> None:
            if context_name in self.contexts:
                self.contexts[context_name].semaphore.release()

        return close_page_callback

    def _make_close_browser_context_callback(self, name: str, persistent: bool) -> Callable:
        def close_browser_context_callback() -> None:
            self.contexts.pop(name, None)
            if hasattr(self, "context_semaphore"):
                self.context_semaphore.release()
            logger.debug(f"Browser context closed: '{name}' (persistent={persistent})")

        return close_browser_context_callback

    def _make_request_handler(
        self, method: str, scrapy_headers: Headers, body: Optional[bytes], encoding: str = "utf8"
    ) -> Callable:
        async def _request_handler(route: Route, playwright_request: PlaywrightRequest) -> None:
            """Override request headers, method and body."""
            if self.abort_request:
                should_abort = await _maybe_await(self.abort_request(playwright_request))
                if should_abort:
                    await route.abort()
                    self.stats.inc_value("playwright/request_count/aborted")
                    return None

            overrides: dict = {}

            if self.process_request_headers is None:
                final_headers = await playwright_request.all_headers()
            else:
                overrides["headers"] = final_headers = await _maybe_await(
                    self.process_request_headers(
                        self.browser_type_name, playwright_request, scrapy_headers
                    )
                )
            # the request that reaches the callback should contain the final headers
            scrapy_headers.clear()
            scrapy_headers.update(final_headers)
            del final_headers

            if playwright_request.is_navigation_request():
                overrides["method"] = method
                if body is not None:
                    overrides["post_data"] = body.decode(encoding)

            try:
                await route.continue_(**overrides)
            except Exception as ex:  # pylint: disable=broad-except
                if _is_safe_close_error(ex):
                    logger.warning(
                        f"{playwright_request}: failed processing Playwright request ({ex})"
                    )
                else:
                    raise

        return _request_handler


async def _maybe_await(obj):
    if isinstance(obj, Awaitable):
        return await obj
    return obj


def _make_request_logger(context_name: str) -> Callable:
    async def _log_request(request: PlaywrightRequest) -> None:
        referrer = await request.header_value("referer")
        logger.debug(
            f"[Context={context_name}] Request: <{request.method.upper()} {request.url}> "
            f"(resource type: {request.resource_type}, referrer: {referrer})"
        )

    return _log_request


def _make_response_logger(context_name: str) -> Callable:
    async def _log_request(response: PlaywrightResponse) -> None:
        referrer = await response.header_value("referer")
        logger.debug(
            f"[Context={context_name}] Response: <{response.status} {response.url}> "
            f"(referrer: {referrer})"
        )

    return _log_request


def _possible_encodings(headers: Headers, text: str) -> Generator[str, None, None]:
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


def _is_safe_close_error(error: Exception) -> bool:
    """
    Taken verbatim from
    https://github.com/microsoft/playwright-python/blob/v1.20.0/playwright/_impl/_helper.py#L234-L238
    """
    message = str(error)
    return message.endswith("Browser has been closed") or message.endswith(
        "Target page, context or browser has been closed"
    )
