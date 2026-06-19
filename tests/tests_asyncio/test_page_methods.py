import json
import logging
import platform
import subprocess
from tempfile import NamedTemporaryFile
from unittest import IsolatedAsyncioTestCase, TestCase

import pytest
from scrapy import Spider, Request
from scrapy.http.response.html import HtmlResponse

from playwright.async_api import Page
from scrapy_playwright.page import PageMethod

from tests import allow_windows, make_handler, assert_correct_response, BaseTestCase


def get_mimetype(file):
    return subprocess.run(
        ["file", "--mime-type", "--brief", file.name],
        stdout=subprocess.PIPE,
        universal_newlines=True,
        check=False,
    ).stdout.strip()


class TestPageMethods(TestCase):
    def test_page_methods(self):
        screenshot = PageMethod("screenshot", "foo", 123, path="/tmp/file", type="png")
        assert screenshot.method == "screenshot"
        assert screenshot.args == ("foo", 123)
        assert screenshot.kwargs == {"path": "/tmp/file", "type": "png"}
        assert screenshot.result is None
        assert str(screenshot) == "<PageMethod for method 'screenshot'>"


class MixinPageMethodTestCase(BaseTestCase):
    @allow_windows
    async def test_mixed(self):
        async with make_handler({"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}) as handler:
            # invalid page methods should be ignored with a warning
            req1 = Request(
                url=self.static_server.urljoin("/index.html"),
                meta={
                    "playwright": True,
                    "playwright_page_methods": ["not-a-page-method", 5, None],
                },
            )
            resp1 = await handler._download_request(req1, Spider("foo"))
            assert_correct_response(resp1, req1)
            for obj in req1.meta["playwright_page_methods"]:
                assert (
                    "scrapy-playwright",
                    logging.WARNING,
                    f"Ignoring {repr(obj)}: expected PageMethod, got {repr(type(obj))}",
                ) in self.caplog.record_tuples

            # valid page methods should still work
            req2 = Request(
                url=self.static_server.urljoin("/index.html"),
                meta={
                    "playwright": True,
                    "playwright_page_methods": {
                        "does_not_exist": PageMethod("does_not_exist"),
                        "is_closed": PageMethod("is_closed"),  # not awaitable
                        "title": PageMethod("title"),  # awaitable
                    },
                },
            )
            resp2 = await handler._download_request(req2, Spider("foo"))
            assert_correct_response(resp2, req2)
            does_not_exist = req2.meta["playwright_page_methods"]["does_not_exist"]
            assert (
                "scrapy-playwright",
                logging.WARNING,
                f"Ignoring {repr(does_not_exist)}: could not find method",
            ) in self.caplog.record_tuples
            assert not req2.meta["playwright_page_methods"]["is_closed"].result
            assert req2.meta["playwright_page_methods"]["title"].result == "Awesome site"

    @allow_windows
    async def test_page_method_navigation(self):
        async with make_handler({"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}) as handler:
            req = Request(
                url=self.static_server.urljoin("/index.html"),
                meta={
                    "playwright": True,
                    "playwright_page_methods": [PageMethod("click", "a.lorem_ipsum")],
                },
            )
            resp = await handler._download_request(req, Spider("foo"))

            assert isinstance(resp, HtmlResponse)
            assert resp.request is req
            assert resp.url == self.static_server.urljoin("/lorem_ipsum.html")
            assert resp.status == 200
            assert "playwright" in resp.flags
            assert resp.css("title::text").get() == "Lorem Ipsum"
            text = resp.css("p::text").get()
            assert text == "Lorem ipsum dolor sit amet, consectetur adipiscing elit."

    @allow_windows
    async def test_page_method_navigation_headers_match_body(self):
        """A PageMethod that navigates to a different page must produce a response
        whose headers and status match the final page's body, not the initial one.
        """
        async with make_handler({"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}) as handler:
            with StaticMockServer() as server:
                req = Request(
                    url=server.urljoin("/index.html"),
                    meta={
                        "playwright": True,
                        "playwright_page_methods": [PageMethod("click", "a.json")],
                    },
                )
                resp = await handler._download_request(req, Spider("foo"))

            assert resp.request is req
            assert resp.url == server.urljoin("/data/quotes1.json")
            assert resp.status == 200
            assert "playwright" in resp.flags
            # headers must match the final (JSON) page, not the initial HTML page
            assert resp.headers.get("Content-Type", b"").startswith(b"application/json")
            # parse body and verify it's JSON, not HTML
            body = json.loads(resp.css("pre::text").get())
            assert isinstance(body, dict)
            assert isinstance(body.get("quotes"), list)
            assert body.get("has_next") is True
            assert body.get("page") == 1

    @allow_windows
    async def test_page_method_infinite_scroll(self):
        async with make_handler({"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}) as handler:
            req = Request(
                url=self.static_server.urljoin("/scroll.html"),
                headers={"User-Agent": "scrapy-playwright"},
                meta={
                    "playwright": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_selector", selector="div.quote"),
                        PageMethod("evaluate", "window.scrollBy(0, document.body.scrollHeight)"),
                        PageMethod("wait_for_selector", selector="div.quote:nth-child(11)"),
                        PageMethod("evaluate", "window.scrollBy(0, document.body.scrollHeight)"),
                        PageMethod("wait_for_selector", selector="div.quote:nth-child(21)"),
                    ],
                },
            )
            resp = await handler._download_request(req, Spider("foo"))

            assert_correct_response(resp, req)
            assert len(resp.css("div.quote")) == 30

    @allow_windows
    async def test_page_method_screenshot(self):
        async with make_handler({"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}) as handler:
            with NamedTemporaryFile(mode="w+b", delete=False) as png_file:
                req = Request(
                    url=self.static_server.urljoin("/index.html"),
                    meta={
                        "playwright": True,
                        "playwright_page_methods": {
                            "png": PageMethod("screenshot", path=png_file.name, type="png"),
                        },
                    },
                )
                await handler._download_request(req, Spider("foo"))

                png_file.file.seek(0)
                assert png_file.file.read() == req.meta["playwright_page_methods"]["png"].result
                if platform.system() != "Windows":
                    assert get_mimetype(png_file) == "image/png"

    @allow_windows
    async def test_page_method_pdf(self):
        if self.browser_type != "chromium":
            pytest.skip("PDF generation is supported only in Chromium")

        async with make_handler({"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}) as handler:
            with NamedTemporaryFile(mode="w+b", delete=False) as pdf_file:
                req = Request(
                    url=self.static_server.urljoin("/index.html"),
                    meta={
                        "playwright": True,
                        "playwright_page_methods": {
                            "pdf": PageMethod("pdf", path=pdf_file.name),
                        },
                    },
                )
                await handler._download_request(req, Spider("foo"))

                pdf_file.file.seek(0)
                assert pdf_file.file.read() == req.meta["playwright_page_methods"]["pdf"].result
                if platform.system() != "Windows":
                    assert get_mimetype(pdf_file) == "application/pdf"

    @allow_windows
    async def test_page_method_callable(self):

        async def scroll_page(page: Page) -> str:
            await page.wait_for_selector(selector="div.quote")
            await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            await page.wait_for_selector(selector="div.quote:nth-child(11)")
            await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            await page.wait_for_selector(selector="div.quote:nth-child(21)")
            return page.url

        async with make_handler({"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}) as handler:
            req = Request(
                url=self.static_server.urljoin("/scroll.html"),
                meta={
                    "playwright": True,
                    "playwright_page_methods": {
                        "callable": PageMethod(scroll_page),
                    },
                },
            )
            resp = await handler._download_request(req, Spider("foo"))

            assert_correct_response(resp, req)
            assert len(resp.css("div.quote")) == 30
            assert resp.meta["playwright_page_methods"]["callable"].result == resp.url


class TestPageMethodChromium(IsolatedAsyncioTestCase, MixinPageMethodTestCase):
    browser_type = "chromium"


class TestPageMethodFirefox(IsolatedAsyncioTestCase, MixinPageMethodTestCase):
    browser_type = "firefox"


@pytest.mark.skipif(platform.system() != "Darwin", reason="Test WebKit only on Darwin")
class TestPageMethodWebkit(IsolatedAsyncioTestCase, MixinPageMethodTestCase):
    browser_type = "webkit"
