import platform
from asyncio.subprocess import Process as AsyncioProcess
from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock, patch

import pytest
from playwright.async_api import PlaywrightContextManager
from scrapy.exceptions import NotConfigured
from scrapy.extensions.memusage import MemoryUsage

from scrapy_playwright.memusage import ScrapyPlaywrightMemoryUsageExtension
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


class MockMemoryInfo:
    rss = 999


@pytest.mark.skipif(
    platform.system() == "Windows",
    reason="resource stdlib module is not available on Windows",
)
@patch("scrapy.extensions.memusage.MailSender")
class TestMemoryUsageExtension(IsolatedAsyncioTestCase):
    async def test_process_availability(self, _MailSender):
        """The main node process should be accessible from the context manager"""
        ctx_manager = PlaywrightContextManager()
        await ctx_manager.start()
        assert isinstance(ctx_manager._connection._transport._proc, AsyncioProcess)
        await ctx_manager.__aexit__()

    @patch("scrapy_playwright.memusage.import_module", side_effect=raise_import_error)
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

    async def test_get_total_process_size(self, _MailSender):
        crawler = MagicMock()
        extension = ScrapyPlaywrightMemoryUsageExtension(crawler)
        extension.psutil = MagicMock()
        extension.psutil.Process.return_value.memory_info.return_value = MockMemoryInfo()
        extension._get_main_process_ids = MagicMock(return_value=[1, 2, 3])
        expected_size = MockMemoryInfo().rss * len(extension._get_main_process_ids())
        assert extension._get_total_playwright_process_memory() == expected_size

    async def test_get_virtual_size_sum(self, _MailSender):
        crawler = MagicMock()
        extension = ScrapyPlaywrightMemoryUsageExtension(crawler)
        parent_cls_extension = MemoryUsage(crawler)
        extension._get_total_playwright_process_memory = MagicMock(return_value=123)
        assert extension.get_virtual_size() == parent_cls_extension.get_virtual_size() + 123
