from asyncio.subprocess import Process as AsyncioProcess
from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock, patch

import pytest
from playwright.async_api import PlaywrightContextManager
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
class TestMemoryUsageExtension(IsolatedAsyncioTestCase):
    async def test_process_availability(self, _MailSender):
        """The main node process should be accessible from the context manager"""
        ctx_manager = PlaywrightContextManager()
        await ctx_manager.start()
        assert isinstance(ctx_manager._connection._transport._proc, AsyncioProcess)
        await ctx_manager.__aexit__()

    @patch("scrapy_playwright.extensions.import_module", side_effect=raise_import_error)
    async def test_psutil_not_available_extension_disabled(self, _import_module, _MailSender):
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

    async def test_get_descendant_processes(self, _MailSender):
        p1 = MagicMock()
        p2 = MagicMock()
        p3 = MagicMock()
        p4 = MagicMock()
        p2.children.return_value = [p3, p4]
        p1.children.return_value = [p2]
        crawler = MagicMock()
        extension = ScrapyPlaywrightMemoryUsageExtension(crawler)
        assert extension._get_descendant_processes(p1) == [p2, p3, p4]
