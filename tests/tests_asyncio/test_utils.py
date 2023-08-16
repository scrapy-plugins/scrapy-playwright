import logging
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

import pytest
from playwright.async_api import Error as PlaywrightError
from scrapy import Spider
from scrapy.http.headers import Headers
from scrapy_playwright._utils import _get_page_content, _NAVIGATION_ERROR_MSG, _encode_body


class TestPageContent(IsolatedAsyncioTestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        caplog.set_level(logging.DEBUG)
        self._caplog = caplog

    @pytest.mark.asyncio
    async def test_get_page_content_ok(self):
        from unittest.mock import AsyncMock

        expected_content = "lorem ipsum"
        page = AsyncMock()
        page.content.return_value = expected_content
        content = await _get_page_content(
            page=page,
            spider=Spider("foo"),
            context_name="context",
            scrapy_request_url="https://example.org",
            scrapy_request_method="GET",
        )
        assert content == expected_content

    @pytest.mark.asyncio
    async def test_get_page_content_retry_known_exception(self):
        expected_content = "lorem ipsum"
        page = AsyncMock()
        page.url = "FAKE URL"
        page.content.side_effect = [PlaywrightError(_NAVIGATION_ERROR_MSG), expected_content]
        content = await _get_page_content(
            page=page,
            spider=Spider("foo"),
            context_name="context",
            scrapy_request_url="https://example.org",
            scrapy_request_method="GET",
        )
        assert content == expected_content
        assert (
            "scrapy-playwright",
            logging.DEBUG,
            f"Retrying to get content from page '{page.url}', error: 'Unable to retrieve"
            " content because the page is navigating and changing the content.'",
        ) in self._caplog.record_tuples

    @pytest.mark.asyncio
    async def test_get_page_content_reraise_unknown_exception(self):
        from unittest.mock import AsyncMock

        expected_exception_message = "nope"
        page = AsyncMock()
        page.content.side_effect = PlaywrightError(expected_exception_message)
        with pytest.raises(PlaywrightError, match=expected_exception_message):
            await _get_page_content(
                page=page,
                spider=Spider("foo"),
                context_name="context",
                scrapy_request_url="https://example.org",
                scrapy_request_method="GET",
            )


class TestBodyEncoding(IsolatedAsyncioTestCase):
    @staticmethod
    def body_str(charset: str, content: str = "áéíóú") -> str:
        return f"""
            <!doctype html>
            <html>
            <head>
            <meta charset="{charset}">
            </head>
            <body>
            <p>{content}</p>
            </body>
            </html>
        """.strip()

    @pytest.mark.asyncio
    async def test_encode_from_headers(self):
        """Charset declared in headers takes precedence"""
        text = self.body_str(charset="gb2312")
        body, encoding = _encode_body(
            headers=Headers({"content-type": "text/html; charset=ISO-8859-1"}),
            text=text,
        )
        assert encoding == "cp1252"
        assert body == text.encode(encoding)

    @pytest.mark.asyncio
    async def test_encode_from_body(self):
        """No charset declared in headers, use the one declared in the body"""
        text = self.body_str(charset="gb2312")
        body, encoding = _encode_body(headers=Headers({}), text=text)
        assert encoding == "gb18030"
        assert body == text.encode(encoding)

    @pytest.mark.asyncio
    async def test_encode_fallback_utf8(self):
        """No charset declared, use utf-8 as fallback"""
        text = "<html>áéíóú</html>"
        body, encoding = _encode_body(headers=Headers(), text=text)
        assert encoding == "utf-8"
        assert body == text.encode(encoding)

    @pytest.mark.asyncio
    async def test_encode_mismatch(self):
        """Charset declared in headers and body do not match, and the headers
        one fails to encode: use the one in the body (first one that works)
        """
        text = self.body_str(charset="gb2312", content="空手道")
        body, encoding = _encode_body(
            headers=Headers({"content-type": "text/html; charset=ISO-8859-1"}),
            text=text,
        )
        assert encoding == "gb18030"
        assert body == text.encode(encoding)
