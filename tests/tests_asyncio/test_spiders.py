import platform
from unittest import TestCase

import pytest
import scrapy
from playwright.async_api import Page
from scrapy import signals
from scrapy.crawler import Crawler, CrawlerProcess
from scrapy_playwright.utils import use_threaded_loop

from tests.mockserver import StaticMockServer


class ThreadedLoopSpider(scrapy.Spider):
    name = "threaded_loop"
    start_url: str

    def start_requests(self):
        yield scrapy.Request(
            url=self.start_url,
            meta={"playwright": True, "playwright_include_page": True},
        )

    @use_threaded_loop
    async def parse(self, response, **kwargs):  # pylint: disable=invalid-overridden-method
        """async generator"""
        page: Page = response.meta["playwright_page"]
        title = await page.title()
        await page.close()
        yield {"url": response.url, "title": title}
        yield scrapy.Request(
            url=response.url + "?foo=bar",
            meta={"playwright": True, "playwright_include_page": True},
            callback=self.parse_2,
        )

    @use_threaded_loop
    async def parse_2(self, response):
        page: Page = response.meta["playwright_page"]
        title = await page.title()
        await page.close()
        return {"url": response.url, "title": title}


@pytest.mark.skipif(
    platform.system() != "Windows",
    reason="Test threaded loop implementation only on Windows",
)
class ThreadedLoopSpiderTestCase(TestCase):
    def test_threaded_loop_spider(self):
        items: list = []

        def collect_items(item):
            items.append(item)

        with StaticMockServer() as server:
            index_url = server.urljoin("/index.html")
            crawler = Crawler(
                spidercls=ThreadedLoopSpider,
                settings={
                    "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
                    "DOWNLOAD_HANDLERS": {
                        "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
                    },
                    "_PLAYWRIGHT_THREADED_LOOP": True,
                },
            )
            crawler.signals.connect(collect_items, signals.item_scraped)
            process = CrawlerProcess()
            process.crawl(crawler, start_url=index_url)
            process.start()

        self.assertCountEqual(
            items,
            [
                {"url": index_url, "title": "Awesome site"},
                {"url": index_url + "?foo=bar", "title": "Awesome site"},
            ],
        )

    def test_use_threaded_loop_non_coroutine_function(self):
        with pytest.raises(RuntimeError) as exc_info:

            @use_threaded_loop
            def not_a_coroutine():
                pass

        self.assertEqual(
            str(exc_info.value),
            "Cannot decorate callback 'not_a_coroutine' with 'use_threaded_loop':"
            " callback must be a coroutine function or an async generator",
        )
