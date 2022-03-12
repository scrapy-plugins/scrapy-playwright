import asyncio
import logging
import warnings
from collections import defaultdict
from contextlib import suppress
from ipaddress import ip_address
from time import time
from typing import Callable, Dict, Optional, Type, TypeVar

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
from scrapy.http import Request, Response
from scrapy.http.headers import Headers
from scrapy.responsetypes import responsetypes
from scrapy.utils.defer import deferred_from_coro
from scrapy.utils.misc import load_object
from scrapy.utils.python import to_unicode
from scrapy.utils.reactor import verify_installed_reactor
from twisted.internet.defer import Deferred, inlineCallbacks
from w3lib.encoding import html_body_declared_encoding, http_content_type_encoding

from scrapy_playwright.headers import use_scrapy_headers
from scrapy_playwright.page import PageCoroutine


__all__ = ["ScrapyPlaywrightDownloadHandler"]


PlaywrightHandler = TypeVar("PlaywrightHandler", bound="ScrapyPlaywrightDownloadHandler")


logger = logging.getLogger("scrapy-playwright")


def _make_request_logger(context_name: str) -> Callable:
    def _log_request(request: PlaywrightRequest) -> None:
        logger.debug(
            f"[Context={context_name}] Request: <{request.method.upper()} {request.url}> "
            f"(resource type: {request.resource_type}, referrer: {request.headers.get('referer')})"
        )

    return _log_request


def _make_response_logger(context_name: str) -> Callable:
    def _log_request(response: PlaywrightResponse) -> None:
        logger.debug(
            f"[Context={context_name}] Response: <{response.status} {response.url}> "
            f"(referrer: {response.headers.get('referer')})"
        )

    return _log_request


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

        if crawler.settings.get("PLAYWRIGHT_PROCESS_REQUEST_HEADERS"):
            self.process_request_headers = load_object(
                crawler.settings["PLAYWRIGHT_PROCESS_REQUEST_HEADERS"]
            )
        else:
            self.process_request_headers = use_scrapy_headers

        default_context_kwargs: dict = {}
        if "PLAYWRIGHT_CONTEXT_ARGS" in crawler.settings:
            default_context_kwargs = crawler.settings.getdict("PLAYWRIGHT_CONTEXT_ARGS")
            warnings.warn(
                "The PLAYWRIGHT_CONTEXT_ARGS setting is deprecated, please use"
                " PLAYWRIGHT_CONTEXTS instead. Keyword arguments defined in"
                " PLAYWRIGHT_CONTEXT_ARGS will be used when creating the 'default' context",
                category=DeprecationWarning,
                stacklevel=2,
            )
        self.context_kwargs: defaultdict = defaultdict(dict)
        for name, kwargs in (crawler.settings.getdict("PLAYWRIGHT_CONTEXTS") or {}).items():
            if name == "default":
                self.context_kwargs[name] = default_context_kwargs
            self.context_kwargs[name].update(kwargs)
        if "default" not in self.context_kwargs and default_context_kwargs:
            self.context_kwargs["default"] = default_context_kwargs

    @classmethod
    def from_crawler(cls: Type[PlaywrightHandler], crawler: Crawler) -> PlaywrightHandler:
        return cls(crawler)

    def _engine_started(self) -> Deferred:
        """Launch the browser. Use the engine_started signal as it supports returning deferreds."""
        return deferred_from_coro(self._launch_browser())

    async def _launch_browser(self) -> None:
        self.playwright_context_manager = PlaywrightContextManager()
        self.playwright = await self.playwright_context_manager.start()
        logger.info("Launching browser")
        browser_launcher = getattr(self.playwright, self.browser_type).launch
        self.browser = await browser_launcher(**self.launch_options)
        logger.info(f"Browser {self.browser_type} launched")
        contexts = await asyncio.gather(
            *[
                self._create_browser_context(name, kwargs)
                for name, kwargs in self.context_kwargs.items()
            ]
        )
        self.contexts: Dict[str, BrowserContext] = dict(zip(self.context_kwargs.keys(), contexts))
        self.context_semaphores: Dict[str, asyncio.Semaphore] = {
            name: asyncio.Semaphore(value=self.max_pages_per_context)
            for name in self.contexts.keys()
        }

    async def _create_browser_context(self, name: str, context_kwargs: dict) -> BrowserContext:
        context = await self.browser.new_context(**context_kwargs)
        context.on("close", self._make_close_browser_context_callback(name))
        logger.debug("Browser context started: '%s'", name)
        self.stats.inc_value("playwright/context_count")
        if self.default_navigation_timeout is not None:
            context.set_default_navigation_timeout(self.default_navigation_timeout)
        return context

    async def _create_page(self, request: Request) -> Page:
        """Create a new page in a context, also creating a new context if necessary."""
        context_name = request.meta.setdefault("playwright_context", "default")
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
        count = sum([len(context.pages) for context in self.contexts.values()])
        current_max_count = self.stats.get_value("playwright/page_count/max_concurrent")
        if current_max_count is None or count > current_max_count:
            self.stats.set_value("playwright/page_count/max_concurrent", count)
        return count

    @inlineCallbacks
    def close(self) -> Deferred:
        yield super().close()
        yield deferred_from_coro(self._close())

    async def _close(self) -> None:
        self.contexts.clear()
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
        except Exception:
            if not page.is_closed():
                await page.close()
                self.stats.inc_value("playwright/page_count/closed")
            raise
        else:
            return result

    async def _download_request_with_page(self, request: Request, page: Page) -> Response:
        start_time = time()
        response = await page.goto(request.url)

        page_coroutines = request.meta.get("playwright_page_coroutines") or ()
        if isinstance(page_coroutines, dict):
            page_coroutines = page_coroutines.values()
        for pc in page_coroutines:
            if isinstance(pc, PageCoroutine):
                method = getattr(page, pc.method)
                pc.result = await method(*pc.args, **pc.kwargs)
                await page.wait_for_load_state(timeout=self.default_navigation_timeout)

        body_str = await page.content()
        request.meta["download_latency"] = time() - start_time

        if request.meta.get("playwright_include_page"):
            request.meta["playwright_page"] = page
        else:
            await page.close()
            self.stats.inc_value("playwright/page_count/closed")

        server_ip_address = None
        with suppress(AttributeError, KeyError, ValueError):
            server_addr = await response.server_addr()
            server_ip_address = ip_address(server_addr["ipAddress"])

        with suppress(AttributeError):
            request.meta["playwright_security_details"] = await response.security_details()

        headers = Headers(response.headers)
        headers.pop("Content-Encoding", None)
        encoding = _get_response_encoding(headers, body_str) or "utf-8"
        body = body_str.encode(encoding)
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

    def _make_close_page_callback(self, context_name: str) -> Callable:
        def close_page_callback() -> None:
            if context_name in self.context_semaphores:
                self.context_semaphores[context_name].release()

        return close_page_callback

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
            processed_headers = await self.process_request_headers(
                self.browser_type, playwright_request, scrapy_headers
            )

            # the request that reaches the callback should contain the headers that were sent
            scrapy_headers.clear()
            scrapy_headers.update(processed_headers)

            overrides: dict = {"headers": processed_headers}
            if playwright_request.is_navigation_request():
                overrides["method"] = method
                if body is not None:
                    overrides["post_data"] = body.decode(encoding)

            await route.continue_(**overrides)

        return _request_handler


def _get_response_encoding(headers: Headers, body: str) -> Optional[str]:
    encoding = None
    if headers.get("content-type"):
        content_type = to_unicode(headers["content-type"])
        encoding = http_content_type_encoding(content_type)
    if not encoding:
        encoding = html_body_declared_encoding(body)
    return encoding
