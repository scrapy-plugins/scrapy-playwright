import platform
import subprocess
from tempfile import NamedTemporaryFile

import pytest
from playwright import TimeoutError
from playwright.async_api import Page as PlaywrightPage
from scrapy import Spider, Request, FormRequest
from scrapy.http.response.html import HtmlResponse
from scrapy.utils.test import get_crawler

from scrapy_playwright.handler import ScrapyPlaywrightDownloadHandler
from scrapy_playwright.page import PageCoroutine as PageCoro

from tests.mockserver import PostMockServer, StaticMockServer


def get_mimetype(file):
    return subprocess.run(
        ["file", "--mime-type", "--brief", file.name],
        stdout=subprocess.PIPE,
        universal_newlines=True,
    ).stdout.strip()


class TestCaseDefaultBrowser:
    browser_type = "chromium"

    @pytest.mark.asyncio
    async def test_basic_response(self):
        handler = ScrapyPlaywrightDownloadHandler(
            get_crawler(settings_dict={"PLAYWRIGHT_BROWSER_TYPE": self.browser_type})
        )
        await handler._launch_browser()

        with StaticMockServer() as server:
            meta = {"playwright": True, "playwright_include_page": True}
            req = Request(server.urljoin("/index.html"), meta=meta)
            resp = await handler._download_request(req, Spider("foo"))

        assert isinstance(resp, HtmlResponse)
        assert resp.request is req
        assert resp.url == req.url
        assert resp.status == 200
        assert "playwright" in resp.flags
        assert resp.css("a::text").getall() == ["Lorem Ipsum", "Infinite Scroll"]
        assert isinstance(resp.meta["playwright_page"], PlaywrightPage)
        assert resp.meta["playwright_page"].url == resp.url

        await resp.meta["playwright_page"].close()
        await handler.browser.close()

    @pytest.mark.asyncio
    async def test_post_request(self):
        handler = ScrapyPlaywrightDownloadHandler(
            get_crawler(settings_dict={"PLAYWRIGHT_BROWSER_TYPE": self.browser_type})
        )
        await handler._launch_browser()

        with PostMockServer() as server:
            req = FormRequest(
                server.urljoin("/"), meta={"playwright": True}, formdata={"foo": "bar"}
            )
            resp = await handler._download_request(req, Spider("foo"))

        assert resp.request is req
        assert resp.url == req.url
        assert resp.status == 200
        assert "playwright" in resp.flags
        assert "Request body: foo=bar" in resp.text

        await handler.browser.close()

    @pytest.mark.asyncio
    async def test_page_coroutine_navigation(self):
        handler = ScrapyPlaywrightDownloadHandler(
            get_crawler(settings_dict={"PLAYWRIGHT_BROWSER_TYPE": self.browser_type})
        )
        await handler._launch_browser()

        with StaticMockServer() as server:
            req = Request(
                url=server.urljoin("/index.html"),
                meta={
                    "playwright": True,
                    "playwright_page_coroutines": [PageCoro("click", "a.lorem_ipsum")],
                },
            )
            resp = await handler._download_request(req, Spider("foo"))

        assert isinstance(resp, HtmlResponse)
        assert resp.request is req
        assert resp.url == server.urljoin("/lorem_ipsum.html")
        assert resp.status == 200
        assert "playwright" in resp.flags
        assert resp.css("title::text").get() == "Lorem Ipsum"
        text = resp.css("p::text").get()
        assert text == "Lorem ipsum dolor sit amet, consectetur adipiscing elit."

        await handler.browser.close()

    @pytest.mark.asyncio
    async def test_page_coroutine_infinite_scroll(self):
        handler = ScrapyPlaywrightDownloadHandler(
            get_crawler(settings_dict={"PLAYWRIGHT_BROWSER_TYPE": self.browser_type})
        )
        await handler._launch_browser()

        with StaticMockServer() as server:
            req = Request(
                url=server.urljoin("/scroll.html"),
                headers={"User-Agent": "scrapy-playwright"},
                meta={
                    "playwright": True,
                    "playwright_page_coroutines": [
                        PageCoro("waitForSelector", selector="div.quote"),
                        PageCoro("evaluate", "window.scrollBy(0, document.body.scrollHeight)"),
                        PageCoro("waitForSelector", selector="div.quote:nth-child(11)"),
                        PageCoro("evaluate", "window.scrollBy(0, document.body.scrollHeight)"),
                        PageCoro("waitForSelector", selector="div.quote:nth-child(21)"),
                    ],
                },
            )
            resp = await handler._download_request(req, Spider("foo"))

        assert isinstance(resp, HtmlResponse)
        assert resp.request is req
        assert resp.url == server.urljoin("/scroll.html")
        assert resp.status == 200
        assert "playwright" in resp.flags
        assert len(resp.css("div.quote")) == 30

        await handler.browser.close()

    @pytest.mark.asyncio
    async def test_context_args(self):
        handler = ScrapyPlaywrightDownloadHandler(
            get_crawler(
                settings_dict={
                    "PLAYWRIGHT_BROWSER_TYPE": self.browser_type,
                    "PLAYWRIGHT_CONTEXT_ARGS": {"javaScriptEnabled": False},
                }
            )
        )
        await handler._launch_browser()

        with StaticMockServer() as server:
            req = Request(
                url=server.urljoin("/scroll.html"),
                meta={
                    "playwright": True,
                    "playwright_page_coroutines": [
                        PageCoro("waitForSelector", selector="div.quote", timeout=1000),
                    ],
                },
            )
            with pytest.raises(TimeoutError):
                await handler._download_request(req, Spider("foo"))

        await handler.browser.close()

    @pytest.mark.asyncio
    async def test_page_coroutine_screenshot(self):
        png_file = NamedTemporaryFile(mode="w+b")
        handler = ScrapyPlaywrightDownloadHandler(
            get_crawler(settings_dict={"PLAYWRIGHT_BROWSER_TYPE": self.browser_type})
        )
        await handler._launch_browser()

        with StaticMockServer() as server:
            req = Request(
                url=server.urljoin("/index.html"),
                meta={
                    "playwright": True,
                    "playwright_page_coroutines": {
                        "png": PageCoro("screenshot", path=png_file.name, type="png"),
                    },
                },
            )
            await handler._download_request(req, Spider("foo"))

            assert get_mimetype(png_file) == "image/png"

            png_file.file.seek(0)
            assert png_file.file.read() == req.meta["playwright_page_coroutines"]["png"].result

            png_file.close()

        await handler.browser.close()

    @pytest.mark.asyncio
    async def test_page_coroutine_pdf(self):
        if self.browser_type != "chromium":
            pytest.skip("PDF generation is supported only in Chromium")

        pdf_file = NamedTemporaryFile(mode="w+b")
        handler = ScrapyPlaywrightDownloadHandler(
            get_crawler(settings_dict={"PLAYWRIGHT_BROWSER_TYPE": self.browser_type})
        )
        await handler._launch_browser()

        with StaticMockServer() as server:
            req = Request(
                url=server.urljoin("/index.html"),
                meta={
                    "playwright": True,
                    "playwright_page_coroutines": {
                        "pdf": PageCoro("pdf", path=pdf_file.name),
                    },
                },
            )
            await handler._download_request(req, Spider("foo"))

            assert get_mimetype(pdf_file) == "application/pdf"

            pdf_file.file.seek(0)
            assert pdf_file.file.read() == req.meta["playwright_page_coroutines"]["pdf"].result

            pdf_file.close()

        await handler.browser.close()


class TestCaseFirefox(TestCaseDefaultBrowser):
    browser_type = "firefox"


@pytest.mark.skipif(platform.system() != "Darwin", reason="Test WebKit only on Darwin")
class TestCaseWebkit(TestCaseDefaultBrowser):
    browser_type = "webkit"
