import json
import logging
import platform
import sys
from ipaddress import ip_address
from unittest.mock import MagicMock, patch

import pytest
from playwright.async_api import (
    Dialog,
    Page as PlaywrightPage,
    TimeoutError as PlaywrightTimeoutError,
)
from scrapy import Spider, Request, FormRequest
from scrapy.http.headers import Headers
from scrapy.http.response.html import HtmlResponse

from scrapy_playwright.page import PageMethod

from tests import make_handler
from tests.mockserver import MockServer, StaticMockServer


class DialogSpider(Spider):
    """A spider with a method to handle the "dialog" page event"""

    name = "dialog"

    async def handle_dialog(self, dialog: Dialog) -> None:
        self.dialog_message = dialog.message
        await dialog.dismiss()


class MixinTestCase:
    @pytest.mark.asyncio
    async def test_basic_response(self):
        async with make_handler({"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}) as handler:
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

    @pytest.mark.asyncio
    async def test_post_request(self):
        async with make_handler({"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}) as handler:
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

    @pytest.mark.asyncio
    async def test_timeout_value(self):
        settings_dict = {
            "PLAYWRIGHT_BROWSER_TYPE": self.browser_type,
        }
        async with make_handler(settings_dict) as handler:
            assert handler.default_navigation_timeout is None

        settings_dict = {
            "PLAYWRIGHT_BROWSER_TYPE": self.browser_type,
            "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": None,
        }
        async with make_handler(settings_dict) as handler:
            assert handler.default_navigation_timeout is None

        settings_dict = {
            "PLAYWRIGHT_BROWSER_TYPE": self.browser_type,
            "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 0,
        }
        async with make_handler(settings_dict) as handler:
            assert handler.default_navigation_timeout == 0

        settings_dict = {
            "PLAYWRIGHT_BROWSER_TYPE": self.browser_type,
            "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 123,
        }
        async with make_handler(settings_dict) as handler:
            assert handler.default_navigation_timeout == 123
        settings_dict = {
            "PLAYWRIGHT_BROWSER_TYPE": self.browser_type,
            "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 0.5,
        }
        async with make_handler(settings_dict) as handler:
            assert handler.default_navigation_timeout == 0.5

    @pytest.mark.asyncio
    async def test_timeout_error(self, caplog):
        settings_dict = {
            "PLAYWRIGHT_BROWSER_TYPE": self.browser_type,
            "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 100,
        }
        async with make_handler(settings_dict) as handler:
            with MockServer() as server:
                req = Request(server.urljoin("/delay/1"), meta={"playwright": True})
                with pytest.raises(PlaywrightTimeoutError) as excinfo:
                    await handler._download_request(req, Spider("foo"))
                assert (
                    "scrapy-playwright",
                    logging.WARNING,
                    f"Closing page due to failed request: {req} ({type(excinfo.value)})",
                ) in caplog.record_tuples

    @pytest.mark.skipif(sys.version_info < (3, 8), reason="AsyncMock was added on Python 3.8")
    @patch("scrapy_playwright.handler.logger")
    @pytest.mark.asyncio
    async def test_route_continue_exception(self, logger):
        from unittest.mock import AsyncMock

        async with make_handler({"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}) as handler:
            req_handler = handler._make_request_handler("GET", Headers({}), body=None)
            route = MagicMock()
            playwright_request = AsyncMock()
            playwright_request.url = "https//example.org"
            playwright_request.is_navigation_request = MagicMock(return_value=True)
            playwright_request.all_headers.return_value = {}

            # safe error, only warn
            exc = Exception("Target page, context or browser has been closed")
            route.continue_.side_effect = exc
            await req_handler(route, playwright_request)
            logger.warning.assert_called_with(
                "%s: failed processing Playwright request (%s)", playwright_request, exc
            )

            # unknown error, re-raise
            route.continue_.side_effect = ZeroDivisionError("asdf")
            with pytest.raises(ZeroDivisionError):
                await req_handler(route, playwright_request)

    @pytest.mark.asyncio
    async def test_event_handler_dialog_callable(self):
        async with make_handler({"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}) as handler:
            with StaticMockServer() as server:
                spider = DialogSpider()
                req = Request(
                    url=server.urljoin("/index.html"),
                    meta={
                        "playwright": True,
                        "playwright_page_methods": [
                            # trigger an alert
                            PageMethod("evaluate", "alert('foobar');"),
                        ],
                        "playwright_page_event_handlers": {
                            "dialog": spider.handle_dialog,
                        },
                    },
                )
                await handler._download_request(req, spider)

            assert spider.dialog_message == "foobar"

    @pytest.mark.asyncio
    async def test_event_handler_dialog_str(self):
        async with make_handler({"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}) as handler:
            with StaticMockServer() as server:
                spider = DialogSpider()
                req = Request(
                    url=server.urljoin("/index.html"),
                    meta={
                        "playwright": True,
                        "playwright_page_methods": [
                            # trigger an alert
                            PageMethod("evaluate", "alert('foobar');"),
                        ],
                        "playwright_page_event_handlers": {
                            "dialog": "handle_dialog",
                        },
                    },
                )
                await handler._download_request(req, spider)

            assert spider.dialog_message == "foobar"

    @pytest.mark.asyncio
    async def test_event_handler_dialog_missing(self, caplog):
        async with make_handler({"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}) as handler:
            with StaticMockServer() as server:
                spider = DialogSpider()
                req = Request(
                    url=server.urljoin("/index.html"),
                    meta={
                        "playwright": True,
                        "playwright_page_event_handlers": {
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

    @pytest.mark.asyncio
    async def test_response_attributes(self):
        async with make_handler({"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}) as handler:
            with MockServer() as server:
                req = Request(
                    url=server.urljoin(),
                    meta={"playwright": True},
                )
                response = await handler._download_request(req, Spider("spider_name"))

        assert response.ip_address == ip_address(server.address)

    @pytest.mark.asyncio
    async def test_page_goto_kwargs_referer(self):
        if self.browser_type != "chromium":
            pytest.skip("referer as goto kwarg seems to work only with chromium :shrug:")
        async with make_handler({"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}) as handler:
            with MockServer() as server:
                fake_referer = server.urljoin("/fake/referer")
                req = Request(
                    url=server.urljoin("/headers"),
                    meta={
                        "playwright": True,
                        "playwright_page_goto_kwargs": {"referer": fake_referer},
                    },
                )
                response = await handler._download_request(req, Spider("spider_name"))

        headers = json.loads(response.css("pre::text").get())
        assert headers["Referer"] == fake_referer

    @pytest.mark.asyncio
    async def test_navigation_returns_none(self, caplog):
        async with make_handler({"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}) as handler:
            with MockServer():
                req = Request(url="about:blank", meta={"playwright": True})
                response = await handler._download_request(req, Spider("spider_name"))

        assert (
            "scrapy-playwright",
            logging.WARNING,
            f"Navigating to {req!r} returned None, the response"
            " will have empty headers and status 200",
        ) in caplog.record_tuples
        assert not response.headers
        assert response.status == 200

    @pytest.mark.asyncio
    async def test_abort_requests(self):
        async def should_abort_request_async(request):
            return request.resource_type == "image"

        def should_abort_request_sync(request):
            return request.resource_type == "image"

        for predicate in (
            lambda request: request.resource_type == "image",
            should_abort_request_async,
            should_abort_request_sync,
        ):
            settings_dict = {
                "PLAYWRIGHT_BROWSER_TYPE": self.browser_type,
                "PLAYWRIGHT_ABORT_REQUEST": predicate,
            }
            async with make_handler(settings_dict) as handler:
                with StaticMockServer() as server:
                    req = Request(
                        url=server.urljoin("/gallery.html"),
                        meta={"playwright": True},
                    )
                    await handler._download_request(req, Spider("foo"))

                    req_prefix = "playwright/request_count"
                    resp_prefix = "playwright/response_count"
                    assert handler.stats.get_value(f"{req_prefix}/resource_type/document") == 1
                    assert handler.stats.get_value(f"{req_prefix}/resource_type/image") == 3
                    assert handler.stats.get_value(f"{resp_prefix}/resource_type/document") == 1
                    assert handler.stats.get_value(f"{resp_prefix}/resource_type/image") is None
                    assert handler.stats.get_value(f"{req_prefix}/aborted") == 3

    @pytest.mark.asyncio
    async def test_page_initialization_ok(self, caplog):
        async def init_page(page, request):
            await page.set_extra_http_headers({"Extra-Header": "Qwerty"})

        settings_dict = {
            "PLAYWRIGHT_BROWSER_TYPE": self.browser_type,
            "PLAYWRIGHT_PROCESS_REQUEST_HEADERS": None,
        }
        async with make_handler(settings_dict) as handler:
            with MockServer() as server:
                req = Request(
                    url=server.urljoin("/headers"),
                    meta={"playwright": True, "playwright_page_init_callback": init_page},
                )
                response = await handler._download_request(req, Spider("spider_name"))
        assert response.status == 200
        headers = json.loads(response.css("pre::text").get())
        headers = {key.lower(): value for key, value in headers.items()}
        assert headers["extra-header"] == "Qwerty"

    @pytest.mark.asyncio
    async def test_page_initialization_fail(self, caplog):
        async def init_page(page, request, unused_arg):
            await page.set_extra_http_headers({"Extra-Header": "Qwerty"})

        settings_dict = {
            "PLAYWRIGHT_BROWSER_TYPE": self.browser_type,
            "PLAYWRIGHT_PROCESS_REQUEST_HEADERS": None,
        }
        async with make_handler(settings_dict) as handler:
            with MockServer() as server:
                req = Request(
                    url=server.urljoin("/headers"),
                    meta={"playwright": True, "playwright_page_init_callback": init_page},
                )
                response = await handler._download_request(req, Spider("spider_name"))
        assert response.status == 200
        headers = json.loads(response.css("pre::text").get())
        headers = {key.lower(): value for key, value in headers.items()}
        assert "extra-header" not in headers

        log_entry = caplog.record_tuples[0]
        assert log_entry[0] == "scrapy-playwright"
        assert log_entry[1] == logging.WARNING
        assert f"[Context=default] Page init callback exception for {req!r}" in log_entry[2]
        assert "init_page() missing 1 required positional argument: 'unused_arg'" in log_entry[2]


class TestCaseChromium(MixinTestCase):
    browser_type = "chromium"


class TestCaseFirefox(MixinTestCase):
    browser_type = "firefox"


@pytest.mark.skipif(platform.system() != "Darwin", reason="Test WebKit only on Darwin")
class TestCaseWebkit(MixinTestCase):
    browser_type = "webkit"
