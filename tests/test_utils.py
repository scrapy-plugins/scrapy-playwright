import logging
import sys

import pytest
from playwright.async_api import Error as PlaywrightError
from scrapy import Spider
from scrapy_playwright._utils import _get_page_content, _NAVIGATION_ERROR_MSG


@pytest.mark.skipif(sys.version_info < (3, 8), reason="AsyncMock was added on Python 3.8")
@pytest.mark.asyncio
async def test_get_page_content_ok():
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


@pytest.mark.skipif(sys.version_info < (3, 8), reason="AsyncMock was added on Python 3.8")
@pytest.mark.asyncio
async def test_get_page_content_retry_known_exception(caplog):
    from unittest.mock import AsyncMock

    caplog.set_level(logging.DEBUG)
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
    ) in caplog.record_tuples


@pytest.mark.skipif(sys.version_info < (3, 8), reason="AsyncMock was added on Python 3.8")
@pytest.mark.asyncio
async def test_get_page_content_reraise_unknown_exception():
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
