import json
import logging
import platform
import sys
from ipaddress import ip_address
from unittest.mock import MagicMock, patch

import pytest
from playwright.async_api import (
    Dialog,
    Error as PlaywrightError,
    Page as PlaywrightPage,
    TimeoutError as PlaywrightTimeoutError,
)
from scrapy import Spider, Request, FormRequest
from scrapy.http import Response

from scrapy_playwright.handler import DEFAULT_CONTEXT_NAME
from scrapy_playwright.page import PageMethod

from tests import make_handler, assert_correct_response
from tests.mockserver import MockServer, StaticMockServer


class DialogSpider(Spider):
    """A spider with a method to handle the "dialog" page event"""

    name = "dialog"

    def parse(self, response: Response, **kwargs) -> None:
        return None

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

            assert_correct_response(resp, req)
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

            assert_correct_response(resp, req)
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
                    f"Closing page due to failed request: {req}"
                    f" exc_type={type(excinfo.value)} exc_msg={str(excinfo.value)}",
                ) in caplog.record_tuples

    @pytest.mark.asyncio
    async def test_retry_page_content_still_navigating(self, caplog):
        if self.browser_type != "chromium":
            pytest.skip("Only Chromium seems to redirect meta tags within the same goto call")

        caplog.set_level(logging.DEBUG)
        async with make_handler({"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}) as handler:
            with StaticMockServer() as server:
                req = Request(server.urljoin("/redirect.html"), meta={"playwright": True})
                resp = await handler._download_request(req, Spider("foo"))

            assert resp.request is req
            assert resp.url == server.urljoin("/index.html")  # redirected
            assert resp.status == 200
            assert "playwright" in resp.flags
            assert (
                "scrapy-playwright",
                logging.DEBUG,
                f"Retrying to get content from page '{req.url}', error: 'Unable to retrieve"
                " content because the page is navigating and changing the content.'",
            ) in caplog.record_tuples

    @pytest.mark.skipif(sys.version_info < (3, 8), reason="AsyncMock was added on Python 3.8")
    @patch("scrapy_playwright.handler.logger")
    @pytest.mark.asyncio
    async def test_route_continue_exception(self, logger):
        from unittest.mock import AsyncMock

        async with make_handler({"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}) as handler:
            scrapy_request = Request(url="https://example.org", method="GET")
            spider = Spider("foo")
            req_handler = handler._make_request_handler(
                context_name=DEFAULT_CONTEXT_NAME,
                method=scrapy_request.method,
                url=scrapy_request.url,
                headers=scrapy_request.headers,
                body=None,
                encoding="utf-8",
                spider=spider,
            )
            route = MagicMock()
            playwright_request = AsyncMock()
            playwright_request.url = scrapy_request.url
            playwright_request.method = scrapy_request.method
            playwright_request.is_navigation_request = MagicMock(return_value=True)
            playwright_request.all_headers.return_value = {}

            # safe error, only warn
            ex = PlaywrightError("Target page, context or browser has been closed")
            route.continue_.side_effect = ex
            await req_handler(route, playwright_request)
            logger.warning.assert_called_with(
                "Failed processing Playwright request: <%s %s> exc_type=%s exc_msg=%s",
                playwright_request.method,
                playwright_request.url,
                type(ex),
                str(ex),
                extra={
                    "spider": spider,
                    "context_name": DEFAULT_CONTEXT_NAME,
                    "scrapy_request_url": scrapy_request.url,
                    "scrapy_request_method": scrapy_request.method,
                    "playwright_request_url": playwright_request.url,
                    "playwright_request_method": playwright_request.method,
                    "exception": ex,
                },
            )

            # unknown errors, re-raise
            route.continue_.side_effect = ZeroDivisionError("asdf")
            with pytest.raises(ZeroDivisionError):
                await req_handler(route, playwright_request)
            route.continue_.side_effect = PlaywrightError("qwerty")
            with pytest.raises(PlaywrightError):
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
    async def test_page_initialization_ok(self):
        async def init_page(page, _request):
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
        async def init_page(page, _request, _missing):
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
        assert "init_page() missing 1 required positional argument: '_missing'" in log_entry[2]

    @pytest.mark.asyncio
    async def test_redirect(self):
        async with make_handler({"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}) as handler:
            with MockServer() as server:
                req = Request(
                    url=server.urljoin("/redirect2"),
                    meta={"playwright": True},
                )
                response = await handler._download_request(req, Spider("spider_name"))

        assert response.url == server.urljoin("/headers")
        assert response.meta["redirect_times"] == 2
        assert response.meta["redirect_reasons"] == [302, 301]
        assert response.meta["redirect_urls"] == [
            server.urljoin("/redirect2"),
            server.urljoin("/redirect"),
        ]

    @pytest.mark.asyncio
    async def test_logging_record_spider(self, caplog):
        """Make sure at least one log record has the spider as an attribute
        (records sent before opening the spider will not have it).
        """
        caplog.set_level(logging.DEBUG)
        spider = Spider("spider_name")
        async with make_handler({"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}) as handler:
            with MockServer() as server:
                req = Request(url=server.urljoin("/index.html"), meta={"playwright": True})
                await handler._download_request(req, spider)

        assert any(getattr(rec, "spider", None) is spider for rec in caplog.records)


class TestCaseChromium(MixinTestCase):
    browser_type = "chromium"


class TestCaseFirefox(MixinTestCase):
    browser_type = "firefox"


@pytest.mark.skipif(platform.system() != "Darwin", reason="Test WebKit only on Darwin")
class TestCaseWebkit(MixinTestCase):
    browser_type = "webkit"
