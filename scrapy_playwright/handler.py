import asyncio
import logging
from time import time
from typing import Callable, Optional, Type, TypeVar
from urllib.parse import urlparse

import playwright
from playwright.async_api import Page
from scrapy import Spider, signals
from scrapy.core.downloader.handlers.http import HTTPDownloadHandler
from scrapy.crawler import Crawler
from scrapy.http import Request, Response
from scrapy.http.headers import Headers
from scrapy.responsetypes import responsetypes
from scrapy.statscollectors import StatsCollector
from scrapy.utils.defer import deferred_from_coro
from scrapy.utils.reactor import verify_installed_reactor
from twisted.internet.defer import Deferred, inlineCallbacks

from scrapy_playwright.page import PageCoroutine


__all__ = ["ScrapyPlaywrightDownloadHandler"]


PlaywrightHandler = TypeVar("PlaywrightHandler", bound="ScrapyPlaywrightDownloadHandler")


logger = logging.getLogger(__name__)


def _make_request_handler(
    browser_type: str,
    scrapy_request: Request,
    stats: StatsCollector,
) -> Callable:
    def request_handler(
        route: playwright.async_api.Route,
        request: playwright.async_api.Request,
    ) -> None:
        """
        Override request headers, method and body
        """
        if request.url == scrapy_request.url:
            overrides = {
                "method": scrapy_request.method,
                "headers": {
                    key.decode("utf-8").lower(): value[0].decode("utf-8")
                    for key, value in scrapy_request.headers.items()
                },
            }
            if scrapy_request.body:
                overrides["postData"] = scrapy_request.body.decode(scrapy_request.encoding)
            # otherwise this fails with playwright.helper.Error: NS_ERROR_NET_RESET
            if browser_type == "firefox":
                overrides["headers"]["host"] = urlparse(request.url).netloc
        else:
            overrides = {"headers": request.headers.copy()}
            # override user agent, for consistency with other requests
            if scrapy_request.headers.get("user-agent"):
                user_agent = scrapy_request.headers["user-agent"].decode("utf-8")
                overrides["headers"]["user-agent"] = user_agent
        asyncio.create_task(route.continue_(**overrides))
        # increment stats
        stats.inc_value("playwright/request_method_count/{}".format(request.method))
        stats.inc_value("playwright/request_count")
        if request.isNavigationRequest():
            stats.inc_value("playwright/request_count/navigation")

    return request_handler


class ScrapyPlaywrightDownloadHandler(HTTPDownloadHandler):

    browser_type: str = "chromium"  # default browser type
    default_navigation_timeout: Optional[int] = None
    launch_options: dict = dict()
    context_options: dict = dict()

    def __init__(self, crawler: Crawler) -> None:
        settings = crawler.settings
        super().__init__(settings=settings, crawler=crawler)
        verify_installed_reactor("twisted.internet.asyncioreactor.AsyncioSelectorReactor")
        crawler.signals.connect(self._engine_started, signals.engine_started)
        self.stats = crawler.stats

        # read settings
        self.launch_options = settings.getdict("PLAYWRIGHT_LAUNCH_OPTIONS") or {}
        self.context_args = settings.getdict("PLAYWRIGHT_CONTEXT_ARGS") or {}
        self.default_navigation_timeout = (
            settings.getint("PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT") or None
        )
        if settings.get("PLAYWRIGHT_BROWSER_TYPE"):
            self.browser_type = settings["PLAYWRIGHT_BROWSER_TYPE"]

    @classmethod
    def from_crawler(cls: Type[PlaywrightHandler], crawler: Crawler) -> PlaywrightHandler:
        return cls(crawler)

    def _engine_started(self) -> Deferred:
        logger.info("Launching browser")
        return deferred_from_coro(self._launch_browser())

    async def _launch_browser(self) -> None:
        self.playwright_context_manager = playwright.AsyncPlaywrightContextManager()
        self.playwright = await self.playwright_context_manager.start()
        browser_launcher = getattr(self.playwright, self.browser_type).launch
        self.browser = await browser_launcher(**self.launch_options)
        logger.info(f"Browser {self.browser_type} launched with options: {self.launch_options}")
        self.context = await self.browser.newContext(**self.context_args)
        logger.info(f"Browser context started with args: {self.context_args}")

    @inlineCallbacks
    def close(self) -> Deferred:
        yield super().close()
        if getattr(self, "context", None):
            logger.info("Closing browser context")
            yield deferred_from_coro(self.context.close())
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
            page = await self._create_page_for_request(request)
        await page.unroute("**")
        await page.route(
            "**",
            _make_request_handler(
                browser_type=self.browser_type, scrapy_request=request, stats=self.stats
            ),
        )

        try:
            result = await self._download_request_with_page(request, spider, page)
        except Exception:
            if not page.isClosed():
                await page.close()
                self.stats.inc_value("playwright/page_count/closed")
            raise
        else:
            return result

    async def _create_page_for_request(self, request: Request) -> Page:
        page = await self.context.newPage()  # type: ignore
        self.stats.inc_value("playwright/page_count")
        if self.default_navigation_timeout:
            page.setDefaultNavigationTimeout(self.default_navigation_timeout)
        return page

    async def _download_request_with_page(
        self, request: Request, spider: Spider, page: Page
    ) -> Response:
        start_time = time()
        response = await page.goto(request.url)

        page_coroutines = request.meta.get("playwright_page_coroutines") or ()
        if isinstance(page_coroutines, dict):
            page_coroutines = page_coroutines.values()
        for pc in page_coroutines:
            if isinstance(pc, PageCoroutine):
                method = getattr(page, pc.method)
                pc.result = await method(*pc.args, **pc.kwargs)
                await page.waitForLoadState(timeout=self.default_navigation_timeout)

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
