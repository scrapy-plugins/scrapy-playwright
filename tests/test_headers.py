import json
import platform
import warnings

import pytest
from scrapy import Spider, Request

from tests import make_handler
from tests.mockserver import MockServer

from scrapy_playwright.headers import use_playwright_headers


class MixinProcessHeadersTestCase:
    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
    async def test_use_playwright_headers(self):
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
                assert "asdf" not in headers

    @pytest.mark.asyncio
    async def test_use_playwright_headers_deprecated(self):
        """Ignore Scrapy headers"""
        settings_dict = {
            "PLAYWRIGHT_BROWSER_TYPE": self.browser_type,
            "PLAYWRIGHT_CONTEXTS": {"default": {"user_agent": self.browser_type}},
            "PLAYWRIGHT_PROCESS_REQUEST_HEADERS": use_playwright_headers,
            "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 2000,
        }
        with warnings.catch_warnings(record=True) as warning_list:
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
                    assert "asdf" not in headers

            assert str(warning_list[0].message) == (
                "The 'scrapy_playwright.headers.use_playwright_headers' function is"
                " deprecated, please set 'PLAYWRIGHT_PROCESS_REQUEST_HEADERS=None'"
                " instead."
            )

    @pytest.mark.asyncio
    async def test_use_custom_headers(self):
        """Custom header processing function"""

        async def important_headers(*args, **kwargs) -> dict:
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
                resp = await handler._download_request(req, Spider("foo"))
                headers = json.loads(resp.css("pre::text").get())
                headers = {key.lower(): value for key, value in headers.items()}
                assert headers["foo"] == "bar"
                assert headers.get("user-agent") not in (self.browser_type, "foobar")
                assert "asdf" not in headers


class TestProcessHeadersChromium(MixinProcessHeadersTestCase):
    browser_type = "chromium"


class TestProcessHeadersFirefox(MixinProcessHeadersTestCase):
    browser_type = "firefox"


@pytest.mark.skipif(platform.system() != "Darwin", reason="Test WebKit only on Darwin")
class TestProcessHeadersWebkit(MixinProcessHeadersTestCase):
    browser_type = "webkit"
