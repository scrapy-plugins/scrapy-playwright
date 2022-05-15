import asyncio
import logging
import warnings
from contextlib import suppress
from ipaddress import ip_address
from time import time
from typing import Awaitable, Callable, Dict, Generator, Optional, Tuple, Type, TypeVar, Union

from playwright.async_api import (
    BrowserContext,
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


DEFAULT_CONTEXT_NAME = "default"
PERSISTENT_CONTEXT_NAME = "persistent"


class ScrapyPlaywrightDownloadHandler(HTTPDownloadHandler):
    def __init__(self, crawler: Crawler) -> None:
        super().__init__(settings=crawler.settings, crawler=crawler)
        verify_installed_reactor("twisted.internet.asyncioreactor.AsyncioSelectorReactor")
        crawler.signals.connect(self._engine_started, signals.engine_started)
        self.stats = crawler.stats

        self.browser_type: str = crawler.settings.get("PLAYWRIGHT_BROWSER_TYPE") or "chromium"
        self.max_pages_per_context: int = crawler.settings.getint(
            "PLAYWRIGHT_MAX_PAGES_PER_CONTEXT"
        ) or crawler.settings.getint("CONCURRENT_REQUESTS")
        self.launch_options: dict = crawler.settings.getdict("PLAYWRIGHT_LAUNCH_OPTIONS") or {}

        self.default_navigation_timeout: Optional[float] = None
        if "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT" in crawler.settings:
            with suppress(TypeError, ValueError):
                self.default_navigation_timeout = float(
                    crawler.settings.get("PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT")
                )

        if "PLAYWRIGHT_PROCESS_REQUEST_HEADERS" in crawler.settings:
            if crawler.settings["PLAYWRIGHT_PROCESS_REQUEST_HEADERS"] is None:
                self.process_request_headers = None  # use headers from the Playwright request
            else:
                self.process_request_headers = load_object(
                    crawler.settings["PLAYWRIGHT_PROCESS_REQUEST_HEADERS"]
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

        # context-related settings
        self.contexts: Dict[str, BrowserContext] = {}
        self.persistent_context: bool = False
        self.context_semaphores: Dict[str, asyncio.Semaphore] = {}
        self.context_kwargs: dict = {}
        if crawler.settings.get("PLAYWRIGHT_PERSISTENT_CONTEXT_KWARGS"):
            self.persistent_context = True
            ctx_kwargs = crawler.settings.getdict("PLAYWRIGHT_PERSISTENT_CONTEXT_KWARGS")
            self.context_kwargs[PERSISTENT_CONTEXT_NAME] = ctx_kwargs
            if crawler.settings.get("PLAYWRIGHT_CONTEXTS"):
                logger.warning(
                    "Both PLAYWRIGHT_PERSISTENT_CONTEXT_KWARGS and PLAYWRIGHT_CONTEXTS"
                    " are set, ignoring PLAYWRIGHT_CONTEXTS"
                )
        else:
            self.context_kwargs = crawler.settings.getdict("PLAYWRIGHT_CONTEXTS")

        self.abort_request: Optional[Callable[[PlaywrightRequest], Union[Awaitable, bool]]] = None
        if crawler.settings.get("PLAYWRIGHT_ABORT_REQUEST"):
            self.abort_request = load_object(crawler.settings["PLAYWRIGHT_ABORT_REQUEST"])

    @classmethod
    def from_crawler(cls: Type[PlaywrightHandler], crawler: Crawler) -> PlaywrightHandler:
        return cls(crawler)

    def _engine_started(self) -> Deferred:
        """Launch the browser. Use the engine_started signal as it supports returning deferreds."""
        return deferred_from_coro(self._launch_browser())

    async def _launch_browser(self) -> None:
        """Start the browser instance and the configured contexts. Alternatively,
        start only one persistent context if PLAYWRIGHT_PERSISTENT_CONTEXT_KWARGS was set.
        """
        logger.info(f"Launching browser {self.browser_type}")
        self.playwright_context_manager = PlaywrightContextManager()
        self.playwright = await self.playwright_context_manager.start()
        browser_type = getattr(self.playwright, self.browser_type)
        if self.persistent_context:
            logger.info("Launching single persistent context")
            context = await browser_type.launch_persistent_context(
                **self.context_kwargs[PERSISTENT_CONTEXT_NAME]
            )
            self._init_browser_context(PERSISTENT_CONTEXT_NAME, context)
            self.contexts[PERSISTENT_CONTEXT_NAME] = context
            logger.info("Persistent context launched")
        else:
            self.browser = await browser_type.launch(**self.launch_options)
            logger.info("Launching startup context(s)")
            contexts = await asyncio.gather(
                *[
                    self._create_browser_context(name, kwargs)
                    for name, kwargs in self.context_kwargs.items()
                ]
            )
            self.contexts = dict(zip(self.context_kwargs.keys(), contexts))
        self.context_semaphores.update(
            {name: asyncio.Semaphore(value=self.max_pages_per_context) for name in self.contexts}
        )
        logger.info(f"Browser {self.browser_type} launched")
        self.stats.set_value("playwright/page_count", self._get_total_page_count())

    async def _create_browser_context(self, name: str, context_kwargs: dict) -> BrowserContext:
        context = await self.browser.new_context(**context_kwargs)
        self._init_browser_context(name, context)
        return context

    def _init_browser_context(self, name: str, context: BrowserContext) -> None:
        context.on("close", self._make_close_browser_context_callback(name))
        logger.debug("Browser context started: '%s'", name)
        self.stats.inc_value("playwright/context_count")
        if self.default_navigation_timeout is not None:
            context.set_default_navigation_timeout(self.default_navigation_timeout)

    async def _create_page(self, request: Request) -> Page:
        """Create a new page in a context, also creating a new context if necessary."""
        if self.persistent_context:
            context_name = request.meta["playwright_context"] = PERSISTENT_CONTEXT_NAME
        else:
            context_name = request.meta.setdefault("playwright_context", DEFAULT_CONTEXT_NAME)

        context = self.contexts.get(context_name)
        if context is None:
            context_kwargs = request.meta.get("playwright_context_kwargs") or {}
            context = await self._create_browser_context(context_name, context_kwargs)
            self.contexts[context_name] = context
            self.context_semaphores[context_name] = asyncio.Semaphore(
                value=self.max_pages_per_context
            )

        await self.context_semaphores[context_name].acquire()
        page = await context.new_page()
        self.stats.inc_value("playwright/page_count")
        logger.debug(
            "[Context=%s] New page created, page count is %i (%i for all contexts)",
            context_name,
            len(context.pages),
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
        return sum([len(context.pages) for context in self.contexts.values()])

    def _set_max_concurrent_page_count(self):
        count = self._get_total_page_count()
        current_max_count = self.stats.get_value("playwright/page_count/max_concurrent")
        if current_max_count is None or count > current_max_count:
            self.stats.set_value("playwright/page_count/max_concurrent", count)

    @inlineCallbacks
    def close(self) -> Deferred:
        yield super().close()
        yield deferred_from_coro(self._close())

    async def _close(self) -> None:
        await asyncio.gather(*[context.close() for context in self.contexts.values()])
        self.contexts.clear()
        self.context_semaphores.clear()
        if getattr(self, "browser", None):
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
        response = await page.goto(request.url)
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

        headers = Headers(await response.all_headers())
        headers.pop("Content-Encoding", None)
        body, encoding = _encode_body(headers=headers, text=body_str)
        respcls = responsetypes.from_args(headers=headers, url=page.url, body=body)
        return respcls(
            url=page.url,
            status=response.status,
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
                    pm.result = await _await_if_necessary(method(*pm.args, **pm.kwargs))
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
            if context_name in self.context_semaphores:
                self.context_semaphores[context_name].release()

        return close_page_callback

    def _make_close_browser_context_callback(self, name: str) -> Callable:
        def close_browser_context_callback() -> None:
            logger.debug("Browser context closed: '%s'", name)
            if name in self.contexts:
                self.contexts.pop(name)
            if name in self.context_semaphores:
                self.context_semaphores.pop(name)

        return close_browser_context_callback

    def _make_request_handler(
        self, method: str, scrapy_headers: Headers, body: Optional[bytes], encoding: str = "utf8"
    ) -> Callable:
        async def _request_handler(route: Route, playwright_request: PlaywrightRequest) -> None:
            """Override request headers, method and body."""
            if self.abort_request:
                should_abort = await _await_if_necessary(self.abort_request(playwright_request))
                if should_abort:
                    await route.abort()
                    self.stats.inc_value("playwright/request_count/aborted")
                    return None

            overrides: dict = {}

            if self.process_request_headers is not None:
                overrides["headers"] = await _await_if_necessary(
                    self.process_request_headers(
                        self.browser_type, playwright_request, scrapy_headers
                    )
                )
                # the request that reaches the callback should contain the final headers
                scrapy_headers.clear()
                scrapy_headers.update(overrides["headers"])

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


async def _await_if_necessary(obj):
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
