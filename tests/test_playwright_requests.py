import logging
import platform
import subprocess
from tempfile import NamedTemporaryFile

import pytest
from playwright.async_api import Dialog, Page as PlaywrightPage, TimeoutError
from scrapy import Spider, Request, FormRequest
from scrapy.http.response.html import HtmlResponse
from scrapy.utils.test import get_crawler

from scrapy_playwright.handler import ScrapyPlaywrightDownloadHandler
from scrapy_playwright.page import PageCoroutine as PageCoro

from tests.mockserver import MockServer, StaticMockServer


def get_mimetype(file):
    return subprocess.run(
        ["file", "--mime-type", "--brief", file.name],
        stdout=subprocess.PIPE,
        universal_newlines=True,
    ).stdout.strip()


class DialogSpider(Spider):
    """A spider with a method to handle the "dialog" page event"""

    name = "dialog"

    async def handle_dialog(self, dialog: Dialog) -> None:
        self.dialog_message = dialog.message
        await dialog.dismiss()


class MixinTestCase:
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

        with MockServer() as server:
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
                        PageCoro("wait_for_selector", selector="div.quote"),
                        PageCoro("evaluate", "window.scrollBy(0, document.body.scrollHeight)"),
                        PageCoro("wait_for_selector", selector="div.quote:nth-child(11)"),
                        PageCoro("evaluate", "window.scrollBy(0, document.body.scrollHeight)"),
                        PageCoro("wait_for_selector", selector="div.quote:nth-child(21)"),
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
    async def test_timeout(self):
        handler = ScrapyPlaywrightDownloadHandler(
            get_crawler(
                settings_dict={
                    "PLAYWRIGHT_BROWSER_TYPE": self.browser_type,
                    "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 1000,
                }
            )
        )
        await handler._launch_browser()

        with MockServer() as server:
            req = Request(server.urljoin("/index.html"), meta={"playwright": True})
            with pytest.raises(TimeoutError):
                await handler._download_request(req, Spider("foo"))

        await handler.browser.close()

    @pytest.mark.asyncio
    async def test_context_kwargs(self):
        handler = ScrapyPlaywrightDownloadHandler(
            get_crawler(
                settings_dict={
                    "PLAYWRIGHT_BROWSER_TYPE": self.browser_type,
                    "PLAYWRIGHT_CONTEXTS": {
                        "default": {"java_script_enabled": False},
                    },
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
                        PageCoro("wait_for_selector", selector="div.quote", timeout=1000),
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

    @pytest.mark.asyncio
    async def test_event_handler_dialog_callable(self):
        crawler = get_crawler(settings_dict={"PLAYWRIGHT_BROWSER_TYPE": self.browser_type})
        handler = ScrapyPlaywrightDownloadHandler(crawler)
        await handler._launch_browser()

        with StaticMockServer() as server:
            spider = DialogSpider()
            req = Request(
                url=server.urljoin("/index.html"),
                meta={
                    "playwright": True,
                    "playwright_page_coroutines": [
                        PageCoro("evaluate", "alert('foobar');"),
                    ],
                    "playwright_page_events": {
                        "dialog": spider.handle_dialog,
                    },
                },
            )
            await handler._download_request(req, spider)

        assert spider.dialog_message == "foobar"

        await handler.browser.close()

    @pytest.mark.asyncio
    async def test_event_handler_dialog_str(self):
        crawler = get_crawler(settings_dict={"PLAYWRIGHT_BROWSER_TYPE": self.browser_type})
        handler = ScrapyPlaywrightDownloadHandler(crawler)
        await handler._launch_browser()

        with StaticMockServer() as server:
            spider = DialogSpider()
            req = Request(
                url=server.urljoin("/index.html"),
                meta={
                    "playwright": True,
                    "playwright_page_coroutines": [
                        PageCoro("evaluate", "alert('foobar');"),
                    ],
                    "playwright_page_events": {
                        "dialog": "handle_dialog",
                    },
                },
            )
            await handler._download_request(req, spider)

        assert spider.dialog_message == "foobar"

        await handler.browser.close()

    @pytest.mark.asyncio
    async def test_event_handler_dialog_missing(self, caplog):
        crawler = get_crawler(settings_dict={"PLAYWRIGHT_BROWSER_TYPE": self.browser_type})
        handler = ScrapyPlaywrightDownloadHandler(crawler)
        await handler._launch_browser()

        with StaticMockServer() as server:
            spider = DialogSpider()
            req = Request(
                url=server.urljoin("/index.html"),
                meta={
                    "playwright": True,
                    "playwright_page_events": {
                        "dialog": "missing_method",
                    },
                },
            )
            await handler._download_request(req, spider)

        assert (
            "scrapy-playwright",
            logging.WARNING,
            "Spider 'dialog' does not have a 'missing_method' attribute,"
            " ignoring handler for event 'dialog'",
        ) in caplog.record_tuples
        assert getattr(spider, "dialog_message", None) is None

        await handler.browser.close()


class TestCaseChromium(MixinTestCase):
    browser_type = "chromium"


class TestCaseFirefox(MixinTestCase):
    browser_type = "firefox"


@pytest.mark.skipif(platform.system() != "Darwin", reason="Test WebKit only on Darwin")
class TestCaseWebkit(MixinTestCase):
    browser_type = "webkit"
