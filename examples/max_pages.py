from scrapy import Spider, Request
from scrapy.crawler import CrawlerProcess


class MaxPagesPerContextContextsSpider(Spider):
    """Limit pages by context"""

    name = "contexts"
    custom_settings = {
        "PLAYWRIGHT_MAX_PAGES_PER_CONTEXT": 2,
        "PLAYWRIGHT_CONTEXTS": {
            "a": {"java_script_enabled": True},
            "b": {"java_script_enabled": True},
        },
    }

    def start_requests(self):
        for _ in range(20):
            yield Request(
                url="https://httpbin.org/status?n=404",
                meta={
                    "playwright": True,
                    "playwright_context": "a",
                    "playwright_include_page": True,
                },
                dont_filter=True,
                errback=self.errback,
            )
        for i in range(20):
            yield Request(
                url=f"https://httpbin.org/get?a={i}",
                meta={"playwright": True, "playwright_context": "a"},
            )
        for i in range(20):
            yield Request(
                url=f"https://httpbin.org/get?b={i}",
                meta={"playwright": True, "playwright_context": "b"},
            )

    def parse(self, response):
        return {"url": response.url}

    async def errback(self, failure):
        page = failure.request.meta["playwright_page"]
        await page.close()


if __name__ == "__main__":
    process = CrawlerProcess(
        settings={
            "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
            "DOWNLOAD_HANDLERS": {
                "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
                # "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            },
        }
    )
    process.crawl(MaxPagesPerContextContextsSpider)
    process.start()
