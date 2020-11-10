import logging
from time import time
from typing import Type, TypeVar

from playwright import AsyncPlaywrightContextManager
from scrapy import Spider, signals
from scrapy.core.downloader.handlers.http import HTTPDownloadHandler
from scrapy.crawler import Crawler
from scrapy.http import Request, Response
from scrapy.http.headers import Headers
from scrapy.responsetypes import responsetypes
from scrapy.utils.defer import deferred_from_coro
from scrapy.utils.reactor import verify_installed_reactor
from twisted.internet.defer import Deferred, inlineCallbacks


logger = logging.getLogger("scrapy-playwright")
PlaywrightHandler = TypeVar("PlaywrightHandler", bound="ScrapyPlaywrightDownloadHandler")


class ScrapyPlaywrightDownloadHandler(HTTPDownloadHandler):
    def __init__(self, crawler: Crawler) -> None:
        super().__init__(settings=crawler.settings, crawler=crawler)
        verify_installed_reactor("twisted.internet.asyncioreactor.AsyncioSelectorReactor")
        crawler.signals.connect(self._engine_started, signals.engine_started)
        self.stats = crawler.stats

    @classmethod
    def from_crawler(cls: Type[PlaywrightHandler], crawler: Crawler) -> PlaywrightHandler:
        return cls(crawler)

    def _engine_started(self) -> Deferred:
        return deferred_from_coro(self._launch_browser())

    async def _launch_browser(self) -> None:
        self.playwright_context_manager = AsyncPlaywrightContextManager()
        self.playwright = await self.playwright_context_manager.start()
        # FIXME: chromium hard-coded during initial development
        self.browser = await self.playwright.chromium.launch()

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
