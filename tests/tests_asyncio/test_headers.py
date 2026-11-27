import json
import platform
import warnings
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock

import pytest
from scrapy import Spider, Request
from scrapy.exceptions import ScrapyDeprecationWarning
from scrapy.http import Headers

from scrapy_playwright.headers import use_scrapy_headers
from tests import allow_windows, make_handler, BaseTestCase


class MixinProcessHeadersTestCase(BaseTestCase):
    @allow_windows
    async def test_user_agent(self):
        settings_dict = {
            "PLAYWRIGHT_BROWSER_TYPE": self.browser_type,
            "PLAYWRIGHT_CONTEXTS": {"default": {"user_agent": self.browser_type}},
            "USER_AGENT": None,
        }
        async with make_handler(settings_dict) as handler:
            # if Scrapy's user agent is None, use the one from the Browser
            req = Request(
                url=self.server.urljoin("/headers"),
                meta={"playwright": True},
            )
            resp = await handler._download_request(req, Spider("foo"))
            headers = json.loads(resp.css("pre::text").get())
            headers = {key.lower(): value for key, value in headers.items()}
            assert headers["user-agent"] == self.browser_type

            # if Scrapy's user agent is set to some value, use it
            req = Request(
                url=self.server.urljoin("/headers"),
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
            req = Request(
                url=self.server.urljoin("/headers"),
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
            req = Request(
                url=self.server.urljoin("/headers"),
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


def _lower_keys(headers: dict) -> dict:
    lowered = {key.lower(): value for key, value in headers.items()}
    assert len(lowered) == len(headers), f"duplicated header names: {headers}"
    return lowered


class TestUseScrapyHeaders(IsolatedAsyncioTestCase):
    """Call use_scrapy_headers directly, without a browser."""

    @staticmethod
    async def _process(
        scrapy_headers: dict,
        playwright_headers: dict,
        is_navigation: bool = True,
        browser_type_name: str = "chromium",
    ) -> dict:
        playwright_request = AsyncMock()
        playwright_request.url = "https://example.org/path"
        playwright_request.is_navigation_request = MagicMock(return_value=is_navigation)
        playwright_request.all_headers.return_value = playwright_headers
        return await use_scrapy_headers(
            browser_type_name=browser_type_name,
            playwright_request=playwright_request,
            scrapy_request_data={"headers": Headers(scrapy_headers)},
        )

    async def test_no_deprecation_warning(self):
        for is_navigation in (True, False):
            with warnings.catch_warnings():
                warnings.simplefilter("error", ScrapyDeprecationWarning)
                await self._process(
                    scrapy_headers={"User-Agent": "scrapy-ua"},
                    playwright_headers={"user-agent": "pw-ua"},
                    is_navigation=is_navigation,
                )

    async def test_repeated_headers_merged(self):
        headers = await self._process(
            scrapy_headers={"X-Multi": ["a", "b"]},
            playwright_headers={},
        )
        assert _lower_keys(headers)["x-multi"] == "a,b"

    async def test_headers_without_value_kept(self):
        headers = await self._process(
            scrapy_headers={"X-Empty": None, "User-Agent": None, "X-Set": "1"},
            playwright_headers={"user-agent": "pw-ua"},
        )
        assert list(_lower_keys(headers).items()) == [
            ("x-empty", ""),
            ("user-agent", ""),
            ("x-set", "1"),
        ]

    async def test_result_lookups_case_insensitive(self):
        headers = await self._process(
            scrapy_headers={"X-Multi": ["a", "b"]},
            playwright_headers={},
        )
        assert headers["X-MULTI"] == headers["x-multi"] == "a,b"
        assert "X-MULTI" in headers
        assert headers.get("x-multi") == "a,b"

    async def test_scrapy_headers_take_precedence(self):
        headers = await self._process(
            scrapy_headers={"User-Agent": "scrapy-ua", "Referer": "https://scrapy.example"},
            playwright_headers={"user-agent": "pw-ua", "referer": "https://pw.example"},
        )
        assert _lower_keys(headers) == {
            "user-agent": "scrapy-ua",
            "referer": "https://scrapy.example",
        }

    async def test_playwright_headers_as_fallback(self):
        headers = await self._process(
            scrapy_headers={},
            playwright_headers={"user-agent": "pw-ua", "referer": "https://pw.example"},
        )
        assert _lower_keys(headers) == {
            "user-agent": "pw-ua",
            "referer": "https://pw.example",
        }

    async def test_firefox_host_overridden(self):
        headers = await self._process(
            scrapy_headers={"Host": "scrapy.example"},
            playwright_headers={},
            browser_type_name="firefox",
        )
        assert _lower_keys(headers)["host"] == "example.org"

    async def test_non_navigation_user_agent(self):
        headers = await self._process(
            scrapy_headers={"User-Agent": "scrapy-ua", "X-Multi": ["a", "b"]},
            playwright_headers={"user-agent": "pw-ua", "accept": "*/*"},
            is_navigation=False,
        )
        assert headers == {"user-agent": "scrapy-ua", "accept": "*/*"}
