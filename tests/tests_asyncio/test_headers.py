import json
import logging
import platform
import warnings
from unittest import IsolatedAsyncioTestCase

import pytest
from scrapy import Spider, Request

from tests import allow_windows, make_handler
from tests.mockserver import MockServer


class MixinProcessHeadersTestCase:
    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        caplog.set_level(logging.DEBUG)
        self._caplog = caplog

    @allow_windows
    async def test_user_agent(self):
        settings_dict = {
            "PLAYWRIGHT_BROWSER_TYPE": self.browser_type,
            "PLAYWRIGHT_CONTEXTS": {"default": {"user_agent": self.browser_type}},
            "USER_AGENT": None,
        }
        async with make_handler(settings_dict) as handler:
            with MockServer() as server:
                # if Scrapy's user agent is None, use the one from the Browser
                req = Request(
                    url=server.urljoin("/headers"),
                    meta={"playwright": True},
                )
                resp = await handler._download_request(req, Spider("foo"))
                headers = json.loads(resp.css("pre::text").get())
                headers = {key.lower(): value for key, value in headers.items()}
                assert headers["user-agent"] == self.browser_type

                # if Scrapy's user agent is set to some value, use it
                req = Request(
                    url=server.urljoin("/headers"),
                    meta={"playwright": True},
                    headers={"User-Agent": "foobar"},
                )
                resp = await handler._download_request(req, Spider("foo"))
                headers = json.loads(resp.css("pre::text").get())
                headers = {key.lower(): value for key, value in headers.items()}
                assert headers["user-agent"] == "foobar"

    @allow_windows
    async def test_playwright_headers(self):
        """Ignore Scrapy headers"""
        settings_dict = {
            "PLAYWRIGHT_BROWSER_TYPE": self.browser_type,
            "PLAYWRIGHT_CONTEXTS": {"default": {"user_agent": self.browser_type}},
            "PLAYWRIGHT_PROCESS_REQUEST_HEADERS": None,
            "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 2000,
        }
        async with make_handler(settings_dict) as handler:
            with MockServer() as server:
                req = Request(
                    url=server.urljoin("/headers"),
                    meta={"playwright": True},
                    headers={"User-Agent": "foobar", "Asdf": "qwerty"},
                )
                resp = await handler._download_request(req, Spider("foo"))
                headers = json.loads(resp.css("pre::text").get())
                headers = {key.lower(): value for key, value in headers.items()}
                assert headers["user-agent"] == self.browser_type
                assert req.headers["user-agent"].decode("utf-8") == self.browser_type
                assert "asdf" not in headers
                assert "asdf" not in req.headers
                assert b"asdf" not in req.headers

    @allow_windows
    async def test_use_custom_headers_ok(self):
        """Custom header processing function"""

        async def important_headers(
            browser_type_name,  # pylint: disable=unused-argument
            playwright_request,  # pylint: disable=unused-argument
            scrapy_request_data,  # pylint: disable=unused-argument
        ) -> dict:
            return {"foo": "bar"}

        settings_dict = {
            "PLAYWRIGHT_BROWSER_TYPE": self.browser_type,
            "PLAYWRIGHT_CONTEXTS": {"default": {"user_agent": self.browser_type}},
            "PLAYWRIGHT_PROCESS_REQUEST_HEADERS": important_headers,
        }
        async with make_handler(settings_dict) as handler:
            with MockServer() as server:
                req = Request(
                    url=server.urljoin("/headers"),
                    meta={"playwright": True},
                    headers={"User-Agent": "foobar", "Asdf": "qwerty"},
                )
                with warnings.catch_warnings(record=True) as warning_list:
                    resp = await handler._download_request(req, Spider("foo"))
                assert not warning_list
                headers = json.loads(resp.css("pre::text").get())
                headers = {key.lower(): value for key, value in headers.items()}
                assert headers["foo"] == "bar"
                assert headers.get("user-agent") not in (self.browser_type, "foobar")
                assert "asdf" not in headers


class TestProcessHeadersChromium(IsolatedAsyncioTestCase, MixinProcessHeadersTestCase):
    browser_type = "chromium"


class TestProcessHeadersFirefox(IsolatedAsyncioTestCase, MixinProcessHeadersTestCase):
    browser_type = "firefox"


@pytest.mark.skipif(platform.system() != "Darwin", reason="Test WebKit only on Darwin")
class TestProcessHeadersWebkit(IsolatedAsyncioTestCase, MixinProcessHeadersTestCase):
    browser_type = "webkit"
