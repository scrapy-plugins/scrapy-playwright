import logging
import platform

import pytest
from scrapy import Spider, Request
from scrapy.http.response.html import HtmlResponse

from scrapy_playwright.page import PageCoroutine

from tests import make_handler
from tests.mockserver import StaticMockServer


@pytest.mark.asyncio
async def test_page_coroutines():
    screenshot = PageCoroutine("screenshot", "foo", 123, path="/tmp/file", type="png")
    assert screenshot.method == "screenshot"
    assert screenshot.args == ("foo", 123)
    assert screenshot.kwargs == {"path": "/tmp/file", "type": "png"}
    assert screenshot.result is None
    assert str(screenshot) == "<PageCoroutine for method 'screenshot'>"


class MixinPageCoroutineTestCase:
    @pytest.mark.asyncio
    async def test_page_non_page_coroutine(self, caplog):
        async with make_handler({"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}) as handler:
            with StaticMockServer() as server:
                req = Request(
                    url=server.urljoin("/index.html"),
                    meta={
                        "playwright": True,
                        "playwright_page_coroutines": [
                            "not-a-page-coroutine",
                            5,
                            None,
                        ],
                    },
                )
                resp = await handler._download_request(req, Spider("foo"))

            assert isinstance(resp, HtmlResponse)
            assert resp.request is req
            assert resp.url == server.urljoin("/index.html")
            assert resp.status == 200
            assert "playwright" in resp.flags

            for obj in req.meta["playwright_page_coroutines"]:
                assert (
                    "scrapy-playwright",
                    logging.WARNING,
                    f"Ignoring {repr(obj)}: expected PageCoroutine, got {repr(type(obj))}",
                ) in caplog.record_tuples

    @pytest.mark.asyncio
    async def test_page_mixed_page_coroutines(self, caplog):
        async with make_handler({"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}) as handler:
            with StaticMockServer() as server:
                req = Request(
                    url=server.urljoin("/index.html"),
                    meta={
                        "playwright": True,
                        "playwright_page_coroutines": {
                            "does_not_exist": PageCoroutine("does_not_exist"),
                            "is_closed": PageCoroutine("is_closed"),  # not awaitable
                            "title": PageCoroutine("title"),  # awaitable
                        },
                    },
                )
                resp = await handler._download_request(req, Spider("foo"))

            assert isinstance(resp, HtmlResponse)
            assert resp.request is req
            assert resp.url == server.urljoin("/index.html")
            assert resp.status == 200
            assert "playwright" in resp.flags

            does_not_exist = req.meta["playwright_page_coroutines"]["does_not_exist"]
            assert (
                "scrapy-playwright",
                logging.WARNING,
                f"Ignoring {repr(does_not_exist)}: could not find coroutine",
            ) in caplog.record_tuples
            assert not req.meta["playwright_page_coroutines"]["is_closed"].result
            assert req.meta["playwright_page_coroutines"]["title"].result == "Awesome site"


class TestPageCoroutineChromium(MixinPageCoroutineTestCase):
    browser_type = "chromium"


class TestPageCoroutineFirefox(MixinPageCoroutineTestCase):
    browser_type = "firefox"


@pytest.mark.skipif(platform.system() != "Darwin", reason="Test WebKit only on Darwin")
class TestPageCoroutineWebkit(MixinPageCoroutineTestCase):
    browser_type = "webkit"
