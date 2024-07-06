import json
import logging
import platform
from ipaddress import ip_address
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

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

from tests import allow_windows, make_handler, assert_correct_response
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
    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        caplog.set_level(logging.DEBUG)
        self._caplog = caplog

    @allow_windows
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

    @allow_windows
    async def test_post_request(self):
        async with make_handler({"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}) as handler:
            with MockServer() as server:
                req = FormRequest(
                    server.urljoin("/"), meta={"playwright": True}, formdata={"foo": "bar"}
                )
                resp = await handler._download_request(req, Spider("foo"))

            assert_correct_response(resp, req)
            assert "Request body: foo=bar" in resp.text

    @allow_windows
    async def test_timeout_error(self):
        settings_dict = {
            "PLAYWRIGHT_BROWSER_TYPE": self.browser_type,
            "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 100,
        }
        async with make_handler(settings_dict) as handler:
            with MockServer() as server:
                req = Request(server.urljoin("/headers?delay=1"), meta={"playwright": True})
                with pytest.raises(PlaywrightTimeoutError) as excinfo:
                    await handler._download_request(req, Spider("foo"))
                assert (
                    "scrapy-playwright",
                    logging.WARNING,
                    f"Closing page due to failed request: {req}"
                    f" exc_type={type(excinfo.value)} exc_msg={str(excinfo.value)}",
                ) in self._caplog.record_tuples

    @allow_windows
    async def test_retry_page_content_still_navigating(self):
        if self.browser_type != "chromium":
            pytest.skip("Only Chromium seems to redirect meta tags within the same goto call")

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
            ) in self._caplog.record_tuples

    @patch("scrapy_playwright.handler.logger")
    @allow_windows
    async def test_route_continue_exception(self, logger):
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
                exc_info=True,
            )

            # unknown errors, re-raise
            route.continue_.side_effect = ZeroDivisionError("asdf")
            with pytest.raises(ZeroDivisionError):
                await req_handler(route, playwright_request)
            route.continue_.side_effect = PlaywrightError("qwerty")
            with pytest.raises(PlaywrightError):
                await req_handler(route, playwright_request)

    @allow_windows
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

    @allow_windows
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

    @allow_windows
    async def test_event_handler_dialog_missing(self):
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
        ) in self._caplog.record_tuples
        assert getattr(spider, "dialog_message", None) is None

    @allow_windows
    async def test_response_attributes(self):
        async with make_handler({"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}) as handler:
            with MockServer() as server:
                req = Request(
                    url=server.urljoin(),
                    meta={"playwright": True},
                )
                response = await handler._download_request(req, Spider("spider_name"))

        assert response.ip_address == ip_address(server.address)

    @allow_windows
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

    @allow_windows
    async def test_navigation_returns_none(self):
        async with make_handler({"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}) as handler:
            with MockServer():
                req = Request(url="about:blank", meta={"playwright": True})
                response = await handler._download_request(req, Spider("spider_name"))

        assert (
            "scrapy-playwright",
            logging.WARNING,
            f"Navigating to {req!r} returned None, the response"
            " will have empty headers and status 200",
        ) in self._caplog.record_tuples
        assert not response.headers
        assert response.status == 200

    @allow_windows
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

    @allow_windows
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

    @allow_windows
    async def test_page_initialization_fail(self):
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
        for entry in self._caplog.record_tuples:
            if "Page init callback exception for" in entry[2]:
                assert entry[0] == "scrapy-playwright"
                assert entry[1] == logging.WARNING
                assert f"[Context=default] Page init callback exception for {req!r}" in entry[2]
                assert "init_page() missing 1 required positional argument: '_missing'" in entry[2]

    @allow_windows
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

    @allow_windows
    async def test_logging_record_spider(self):
        """Make sure at least one log record has the spider as an attribute
        (records sent before opening the spider will not have it).
        """
        spider = Spider("spider_name")
        async with make_handler({"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}) as handler:
            with MockServer() as server:
                req = Request(url=server.urljoin("/index.html"), meta={"playwright": True})
                await handler._download_request(req, spider)

        assert any(getattr(rec, "spider", None) is spider for rec in self._caplog.records)

    @allow_windows
    async def test_download_file(self):
        settings_dict = {
            "PLAYWRIGHT_BROWSER_TYPE": self.browser_type,
        }
        async with make_handler(settings_dict) as handler:
            with MockServer() as server:
                request = Request(
                    url=server.urljoin("mancha.pdf"),
                    meta={"playwright": True},
                )
                response = await handler._download_request(request, Spider("foo"))
                assert response.meta["playwright_suggested_filename"] == "mancha.pdf"
                assert response.body.startswith(b"%PDF-1.5")
                assert handler.stats.get_value("playwright/download_count") == 1

    @allow_windows
    async def test_download_file_delay_ok(self):
        settings_dict = {
            "PLAYWRIGHT_BROWSER_TYPE": self.browser_type,
            "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 0,
        }
        async with make_handler(settings_dict) as handler:
            with MockServer() as server:
                request = Request(
                    url=server.urljoin("/mancha.pdf?delay=1"),
                    meta={"playwright": True},
                )
                response = await handler._download_request(request, Spider("foo"))
                assert response.meta["playwright_suggested_filename"] == "mancha.pdf"
                assert response.body.startswith(b"%PDF-1.5")
                assert handler.stats.get_value("playwright/download_count") == 1

    @allow_windows
    async def test_download_file_delay_error(self):
        settings_dict = {
            "PLAYWRIGHT_BROWSER_TYPE": self.browser_type,
            "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 10,
        }
        async with make_handler(settings_dict) as handler:
            with MockServer() as server:
                request = Request(
                    url=server.urljoin("/mancha.pdf?delay=1"),
                    meta={"playwright": True},
                )
                with pytest.raises(PlaywrightError) as excinfo:
                    await handler._download_request(request, Spider("foo"))
                assert (
                    "scrapy-playwright",
                    logging.WARNING,
                    f"Closing page due to failed request: {request}"
                    f" exc_type={type(excinfo.value)} exc_msg={str(excinfo.value)}",
                ) in self._caplog.record_tuples

    @allow_windows
    async def test_download_file_failure(self):
        if self.browser_type != "chromium":
            pytest.skip()

        async def cancel_download(download):
            await download.cancel()

        async with make_handler({"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}) as handler:
            with MockServer() as server:
                request = Request(
                    url=server.urljoin("/mancha.pdf?content_length_multiplier=1000"),
                    meta={
                        "playwright": True,
                        "playwright_event_handlers": {"download": cancel_download},
                    },
                )
                with pytest.raises(RuntimeError) as excinfo:
                    await handler._download_request(request, Spider("foo"))
                assert (
                    "scrapy-playwright",
                    logging.WARNING,
                    f"Closing page due to failed request: {request}"
                    f" exc_type={type(excinfo.value)} exc_msg={str(excinfo.value)}",
                ) in self._caplog.record_tuples

    @allow_windows
    async def test_fail_status_204(self):
        async with make_handler({"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}) as handler:
            with MockServer() as server:
                request = Request(
                    url=server.urljoin("/status/204"),
                    meta={"playwright": True},
                )
                with pytest.raises(PlaywrightError) as excinfo:
                    await handler._download_request(request, Spider("foo"))
                assert (
                    "scrapy-playwright",
                    logging.WARNING,
                    f"Closing page due to failed request: {request}"
                    f" exc_type={type(excinfo.value)} exc_msg={str(excinfo.value)}",
                ) in self._caplog.record_tuples


class TestCaseChromium(IsolatedAsyncioTestCase, MixinTestCase):
    browser_type = "chromium"


class TestCaseFirefox(IsolatedAsyncioTestCase, MixinTestCase):
    browser_type = "firefox"


@pytest.mark.skipif(platform.system() != "Darwin", reason="Test WebKit only on Darwin")
class TestCaseWebkit(IsolatedAsyncioTestCase, MixinTestCase):
    browser_type = "webkit"
