from contextlib import suppress
from importlib import import_module
from typing import List

from scrapy.exceptions import NotConfigured
from scrapy.extensions.memusage import MemoryUsage

from scrapy_playwright.handler import ScrapyPlaywrightDownloadHandler, logger


_MIB_FACTOR = 1024**2


class ScrapyPlaywrightMemoryUsageExtension(MemoryUsage):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        try:
            self.psutil = import_module("psutil")
        except ImportError as exc:
            raise NotConfigured("The psutil module is not available") from exc

    def _get_main_process_ids(self) -> List[int]:
        try:
            return [
                handler.playwright_context_manager._connection._transport._proc.pid
                for handler in self.crawler.engine.downloader.handlers._handlers.values()
                if isinstance(handler, ScrapyPlaywrightDownloadHandler)
                and handler.playwright_context_manager
            ]
        except Exception:
            return []

    def _get_descendant_processes(self, process) -> list:
        children = process.children()
        result = children.copy()
        for child in children:
            result.extend(self._get_descendant_processes(child))
        return result

    def _get_total_playwright_process_memory(self) -> int:
        process_list = [self.psutil.Process(pid) for pid in self._get_main_process_ids()]
        for proc in process_list.copy():
            process_list.extend(self._get_descendant_processes(proc))
        total_process_size = 0
        for proc in process_list:
            with suppress(Exception):  # might fail if the process exited in the meantime
                total_process_size += proc.memory_info().rss
        logger.debug(
            "Total Playwright process memory: %i Bytes (%i MiB)",
            total_process_size,
            total_process_size / _MIB_FACTOR,
        )
        return total_process_size

    def get_virtual_size(self) -> int:
        return super().get_virtual_size() + self._get_total_playwright_process_memory()
