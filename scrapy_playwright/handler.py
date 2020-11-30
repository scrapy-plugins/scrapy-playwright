import asyncio
import logging
from time import time
from typing import Callable, Optional, Type, TypeVar

import playwright
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


logger = logging.getLogger("scrapy-playwright")
PlaywrightHandler = TypeVar("PlaywrightHandler", bound="ScrapyPlaywrightDownloadHandler")


def _make_request_handler(
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
        overrides = {}
        if request.url == scrapy_request.url:
            overrides = {
                "method": scrapy_request.method,
                "headers": {
                    key.decode("utf-8"): value[0].decode("utf-8")
                    for key, value in scrapy_request.headers.items()
                },
            }
            if scrapy_request.body:
                overrides["postData"] = scrapy_request.body.decode(scrapy_request.encoding)
        asyncio.create_task(route.continue_(**overrides))
        # increment stats
        stats.inc_value("pyppeteer/request_method_count/{}".format(request.method))
        stats.inc_value("pyppeteer/request_count")
        if request.isNavigationRequest():
            stats.inc_value("pyppeteer/request_count/navigation")

    return request_handler


class ScrapyPlaywrightDownloadHandler(HTTPDownloadHandler):

    browser_type: str = "chromium"  # default browser type
    default_navigation_timeout: Optional[int] = None

    def __init__(self, crawler: Crawler) -> None:
        settings = crawler.settings
        super().__init__(settings=settings, crawler=crawler)
        verify_installed_reactor("twisted.internet.asyncioreactor.AsyncioSelectorReactor")
        if settings.get("PLAYWRIGHT_BROWSER_TYPE"):
            self.browser_type = settings["PLAYWRIGHT_BROWSER_TYPE"]
        if settings.getint("PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT"):
            self.default_navigation_timeout = settings["PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT"]
        crawler.signals.connect(self._engine_started, signals.engine_started)
        self.stats = crawler.stats

    @classmethod
    def from_crawler(cls: Type[PlaywrightHandler], crawler: Crawler) -> PlaywrightHandler:
        return cls(crawler)

    def _engine_started(self) -> Deferred:
        return deferred_from_coro(self._launch_browser())

    async def _launch_browser(self) -> None:
        self.playwright_context_manager = playwright.AsyncPlaywrightContextManager()
        self.playwright = await self.playwright_context_manager.start()
        self.browser = await getattr(self.playwright, self.browser_type).launch()

    @inlineCallbacks
    def close(self) -> Deferred:
        yield super().close()
        if self.browser:
            yield deferred_from_coro(self.browser.close())
        yield deferred_from_coro(self.playwright_context_manager.__aexit__())

    def download_request(self, request: Request, spider: Spider) -> Deferred:
        if request.meta.get("playwright"):
            return deferred_from_coro(self._download_request_playwright(request, spider))
        return super().download_request(request, spider)

    async def _download_request_playwright(self, request: Request, spider: Spider) -> Response:
        page = await self.browser.newPage()  # type: ignore
        if self.default_navigation_timeout:
            page.setDefaultNavigationTimeout(self.default_navigation_timeout)
        await page.route("**", _make_request_handler(scrapy_request=request, stats=self.stats))
        self.stats.inc_value("playwright/page_count")

        start_time = time()
        response = await page.goto(request.url)

        body = (await page.content()).encode("utf8")
        request.meta["download_latency"] = time() - start_time

        await page.screenshot(path="page.png")  # FIXME: only for development
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
