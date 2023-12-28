import logging
import platform
from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock, patch

import pytest
from scrapy.exceptions import NotConfigured

from scrapy_playwright.extensions import ScrapyPlaywrightMemoryUsageExtension
from scrapy_playwright.handler import ScrapyPlaywrightDownloadHandler


SCHEMA_PID_MAP = {"http": 123, "https": 456}


def mock_crawler_with_handlers() -> dict:
    handlers = {}
    for schema, pid in SCHEMA_PID_MAP.items():
        process = MagicMock()
        process.pid = pid
        handlers[schema] = MagicMock(spec=ScrapyPlaywrightDownloadHandler)
        handlers[schema].playwright_context_manager._connection._transport._proc = process
    crawler = MagicMock()
    crawler.engine.downloader.handlers._handlers = handlers
    return crawler


def raise_import_error(*args, **kwargs):
    raise ImportError


@patch("scrapy.extensions.memusage.MailSender")
class MixinTestMemoryUsageExtension:
    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        caplog.set_level(logging.DEBUG)
        self._caplog = caplog

    @patch("scrapy_playwright.extensions.import_module")
    async def test_psutil_not_available(self, import_module, _MailSender):
        import_module.side_effect = raise_import_error
        crawler = MagicMock()
        with pytest.raises(NotConfigured):
            ScrapyPlaywrightMemoryUsageExtension(crawler)

    async def test_get_process_ids_ok(self, _MailSender):
        crawler = mock_crawler_with_handlers()
        extension = ScrapyPlaywrightMemoryUsageExtension(crawler)
        assert extension._get_main_process_ids() == list(SCHEMA_PID_MAP.values())

    async def test_get_process_ids_error(self, _MailSender):
        crawler = mock_crawler_with_handlers()
        crawler.engine.downloader.handlers._handlers = MagicMock()
        crawler.engine.downloader.handlers._handlers.values.side_effect = raise_import_error
        extension = ScrapyPlaywrightMemoryUsageExtension(crawler)
        assert extension._get_main_process_ids() == []


class TestCaseChromium(IsolatedAsyncioTestCase, MixinTestMemoryUsageExtension):
    browser_type = "chromium"


class TestCaseFirefox(IsolatedAsyncioTestCase, MixinTestMemoryUsageExtension):
    browser_type = "firefox"


@pytest.mark.skipif(platform.system() != "Darwin", reason="Test WebKit only on Darwin")
class TestCaseWebkit(IsolatedAsyncioTestCase, MixinTestMemoryUsageExtension):
    browser_type = "webkit"
