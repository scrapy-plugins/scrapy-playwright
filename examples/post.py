from pathlib import Path

from scrapy import Spider, FormRequest
from scrapy.crawler import CrawlerProcess
from scrapy_playwright.page import PageCoroutine


class PostSpider(Spider):
    """
    Send data using the POST verb
    """
    name = "post"

    def start_requests(self):
        yield FormRequest(
            url="https://httpbin.org/post",
            formdata={"foo": "bar"},
            meta={
                "playwright": True,
                "playwright_page_coroutines": [
                    PageCoroutine("screenshot", path=Path(__file__).parent / "post.png", full_page=True),
                ],
            },
        )

    def parse(self, response):
        yield {"url": response.url}


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
    process.crawl(PostSpider)
    process.start()
