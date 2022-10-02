import logging
import platform
import warnings

import pytest
from scrapy import Spider, Request
from scrapy.http.response.html import HtmlResponse

from scrapy_playwright.page import PageMethod

from tests import make_handler
from tests.mockserver import StaticMockServer


@pytest.mark.asyncio
async def test_page_methods():
    screenshot = PageMethod("screenshot", "foo", 123, path="/tmp/file", type="png")
    assert screenshot.method == "screenshot"
    assert screenshot.args == ("foo", 123)
    assert screenshot.kwargs == {"path": "/tmp/file", "type": "png"}
    assert screenshot.result is None
    assert str(screenshot) == "<PageMethod for method 'screenshot'>"


def assert_correct_response(response: HtmlResponse, request: Request) -> None:
    assert isinstance(response, HtmlResponse)
    assert response.request is request
    assert response.url == request.url
    assert response.status == 200
    assert "playwright" in response.flags


class MixinPageMethodTestCase:
    @pytest.mark.asyncio
    async def test_page_non_page_method(self, caplog):
        async with make_handler({"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}) as handler:
            with StaticMockServer() as server:
                req = Request(
                    url=server.urljoin("/index.html"),
                    meta={
                        "playwright": True,
                        "playwright_page_methods": [
                            "not-a-page-method",
                            5,
                            None,
                        ],
                    },
                )
                resp = await handler._download_request(req, Spider("foo"))

        assert_correct_response(resp, req)
        for obj in req.meta["playwright_page_methods"]:
            assert (
                "scrapy-playwright",
                logging.WARNING,
                f"Ignoring {repr(obj)}: expected PageMethod, got {repr(type(obj))}",
            ) in caplog.record_tuples

    @pytest.mark.asyncio
    async def test_page_mixed_page_methods(self, caplog):
        async with make_handler({"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}) as handler:
            with StaticMockServer() as server:
                req = Request(
                    url=server.urljoin("/index.html"),
                    meta={
                        "playwright": True,
                        "playwright_page_methods": {
                            "does_not_exist": PageMethod("does_not_exist"),
                            "is_closed": PageMethod("is_closed"),  # not awaitable
                            "title": PageMethod("title"),  # awaitable
                        },
                    },
                )
                resp = await handler._download_request(req, Spider("foo"))

        assert_correct_response(resp, req)
        does_not_exist = req.meta["playwright_page_methods"]["does_not_exist"]
        assert (
            "scrapy-playwright",
            logging.WARNING,
            f"Ignoring {repr(does_not_exist)}: could not find method",
        ) in caplog.record_tuples
        assert not req.meta["playwright_page_methods"]["is_closed"].result
        assert req.meta["playwright_page_methods"]["title"].result == "Awesome site"


class TestPageMethodChromium(MixinPageMethodTestCase):
    browser_type = "chromium"


class TestPageMethodFirefox(MixinPageMethodTestCase):
    browser_type = "firefox"


@pytest.mark.skipif(platform.system() != "Darwin", reason="Test WebKit only on Darwin")
class TestPageMethodWebkit(MixinPageMethodTestCase):
    browser_type = "webkit"
