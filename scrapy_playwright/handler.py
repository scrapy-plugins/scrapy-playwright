import asyncio
import logging
from collections import defaultdict
from time import time
from typing import Callable, Dict, Optional, Type, TypeVar
from urllib.parse import urlparse

from playwright.async_api import (
    BrowserContext,
    Page,
    PlaywrightContextManager,
    Request as PlaywrightRequest,
    Route,
)
from scrapy import Spider, signals
from scrapy.core.downloader.handlers.http import HTTPDownloadHandler
from scrapy.crawler import Crawler
from scrapy.http import Request, Response
from scrapy.http.headers import Headers
from scrapy.responsetypes import responsetypes
from scrapy.utils.defer import deferred_from_coro
from scrapy.utils.reactor import verify_installed_reactor
from twisted.internet.defer import Deferred, inlineCallbacks

from scrapy_playwright.page import PageCoroutine


__all__ = ["ScrapyPlaywrightDownloadHandler"]


PlaywrightHandler = TypeVar("PlaywrightHandler", bound="ScrapyPlaywrightDownloadHandler")


logger = logging.getLogger("scrapy-playwright")


class ScrapyPlaywrightDownloadHandler(HTTPDownloadHandler):

    browser_type: str = "chromium"  # default browser type
    default_navigation_timeout: Optional[int] = None
    launch_options: dict = dict()
    context_options: dict = dict()
    contexts: Dict[str, BrowserContext] = dict()

    def __init__(self, crawler: Crawler) -> None:
        settings = crawler.settings
        super().__init__(settings=settings, crawler=crawler)
        verify_installed_reactor("twisted.internet.asyncioreactor.AsyncioSelectorReactor")
        crawler.signals.connect(self._engine_started, signals.engine_started)
        self.stats = crawler.stats

        self.context_kwargs: defaultdict = defaultdict(dict)
        default_context_kwargs = settings.getdict("PLAYWRIGHT_CONTEXT_ARGS") or {}
        contexts = settings.getdict("PLAYWRIGHT_CONTEXTS") or {}
        for name, kwargs in contexts.items():
            self.context_kwargs[name].update(default_context_kwargs)
            self.context_kwargs[name].update(kwargs)
        if not self.context_kwargs:
            self.context_kwargs["default"].update(default_context_kwargs)

        self.launch_options = settings.getdict("PLAYWRIGHT_LAUNCH_OPTIONS") or {}
        self.default_navigation_timeout = (
            settings.getint("PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT") or None
        )
        if settings.get("PLAYWRIGHT_BROWSER_TYPE"):
            self.browser_type = settings["PLAYWRIGHT_BROWSER_TYPE"]

    @classmethod
    def from_crawler(cls: Type[PlaywrightHandler], crawler: Crawler) -> PlaywrightHandler:
        return cls(crawler)

    def _engine_started(self) -> Deferred:
        """Launch the browser. The engine_started signal is
        used because it supports returning deferreds.
        """
        return deferred_from_coro(self._launch_browser())

    async def _launch_browser(self) -> None:
        self.playwright_context_manager = PlaywrightContextManager()
        self.playwright = await self.playwright_context_manager.start()
        browser_launcher = getattr(self.playwright, self.browser_type).launch
        logger.info("Launching browser")
        self.browser = await browser_launcher(**self.launch_options)
        logger.info(f"Browser {self.browser_type} launched")
        for name, kwargs in self.context_kwargs.items():
            self.contexts[name] = await self._create_browser_context(name, kwargs)

    async def _create_browser_context(self, name: str, context_kwargs: dict) -> BrowserContext:
        context = await self.browser.new_context(**context_kwargs)
        logger.info("Browser context started: '%s'", name)
        self.stats.inc_value("playwright/context_count")
        if self.default_navigation_timeout:
            context.set_default_navigation_timeout(self.default_navigation_timeout)
        return context

    @inlineCallbacks
    def close(self) -> Deferred:
        yield super().close()
        for name, context in self.contexts.items():
            logger.info("Closing browser context: '%s'", name)
            yield deferred_from_coro(context.close())
        if getattr(self, "browser", None):
            logger.info("Closing browser")
            yield deferred_from_coro(self.browser.close())
        yield deferred_from_coro(self.playwright_context_manager.__aexit__())

    def download_request(self, request: Request, spider: Spider) -> Deferred:
        if request.meta.get("playwright"):
            return deferred_from_coro(self._download_request(request, spider))
        return super().download_request(request, spider)

    async def _download_request(self, request: Request, spider: Spider) -> Response:
        page = request.meta.get("playwright_page")
        if not isinstance(page, Page):
            page = await self._create_page(request)
        await page.unroute("**")
        await page.route("**", self._make_request_handler(scrapy_request=request))

        try:
            result = await self._download_request_with_page(request, page)
        except Exception:
            if not page.is_closed():
                await page.close()
                self.stats.inc_value("playwright/page_count/closed")
            raise
        else:
            return result

    async def _create_page(self, request: Request) -> Page:
        """Create a new page in a context, also creating a new context if necessary."""
        ctx_name = request.meta.get("playwright_context_name") or "default"
        request.meta["playwright_context_name"] = ctx_name
        if ctx_name not in self.contexts:
            ctx_kwargs = request.meta.get("playwright_context_kwargs") or {}
            self.contexts[ctx_name] = await self._create_browser_context(ctx_name, ctx_kwargs)
        page = await self.contexts[ctx_name].new_page()
        self.stats.inc_value("playwright/page_count")
        if self.default_navigation_timeout:
            page.set_default_navigation_timeout(self.default_navigation_timeout)
        return page

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

        body = (await page.content()).encode("utf8")
        request.meta["download_latency"] = time() - start_time

        if request.meta.get("playwright_include_page"):
            request.meta["playwright_page"] = page
        else:
            await page.close()
            self.stats.inc_value("playwright/page_count/closed")

        headers = Headers(response.headers)
        headers.pop("Content-Encoding", None)
        respcls = responsetypes.from_args(headers=headers, url=page.url, body=body)
        return respcls(
            url=page.url,
            status=response.status,
            headers=headers,
            body=body,
            request=request,
            flags=["playwright"],
        )

    def _make_request_handler(self, scrapy_request: Request) -> Callable:
        def request_handler(route: Route, pw_request: PlaywrightRequest) -> None:
            """Override request headers, method and body."""
            if pw_request.url == scrapy_request.url:
                overrides = {
                    "method": scrapy_request.method,
                    "headers": {
                        key.decode("utf-8").lower(): value[0].decode("utf-8")
                        for key, value in scrapy_request.headers.items()
                    },
                }
                if scrapy_request.body:
                    overrides["post_data"] = scrapy_request.body.decode(scrapy_request.encoding)
                # otherwise this fails with playwright.helper.Error: NS_ERROR_NET_RESET
                if self.browser_type == "firefox":
                    overrides["headers"]["host"] = urlparse(pw_request.url).netloc
            else:
                overrides = {"headers": pw_request.headers.copy()}
                # override user agent, for consistency with other requests
                if scrapy_request.headers.get("user-agent"):
                    user_agent = scrapy_request.headers["user-agent"].decode("utf-8")
                    overrides["headers"]["user-agent"] = user_agent
            asyncio.create_task(route.continue_(**overrides))
            # increment stats
            self.stats.inc_value("playwright/request_method_count/{}".format(pw_request.method))
            self.stats.inc_value("playwright/request_count")
            if pw_request.is_navigation_request():
                self.stats.inc_value("playwright/request_count/navigation")

        return request_handler
