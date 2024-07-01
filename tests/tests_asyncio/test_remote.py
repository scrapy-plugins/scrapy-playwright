import logging
import re
import subprocess
import time
from contextlib import asynccontextmanager
from typing import Tuple
from unittest import IsolatedAsyncioTestCase

import pytest
from playwright.async_api import async_playwright
from scrapy import Request, Spider

from tests import allow_windows, make_handler, assert_correct_response
from tests.mockserver import StaticMockServer


async def _run_chromium() -> Tuple[subprocess.Popen, str]:
    """Run a Croumium instance in a separate process, return the process
    object and a string with its devtools endpoint.
    """
    async with async_playwright() as playwright:
        proc = subprocess.Popen(  # pylint: disable=consider-using-with
            [playwright.chromium.executable_path, "--headless", "--remote-debugging-port=0"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        devtools_url = None
        while devtools_url is None:
            line = proc.stderr.readline().strip()  # type: ignore
            if not line:
                time.sleep(0.2)
                continue
            print("browser output:", line)
            if match := re.match(r"^DevTools listening on (.+)$", line):
                devtools_url = match.group(1)
                print("devtools_url:", devtools_url)
        return proc, devtools_url


@asynccontextmanager
async def remote_chromium():
    """Launch a Chromium instance with remote debugging enabled."""
    proc = None
    devtools_url = None
    try:
        proc, devtools_url = await _run_chromium()
    except Exception:
        pass
    else:
        yield devtools_url
    finally:
        if proc:
            proc.kill()
            proc.communicate()


class TestRemoteDevtools(IsolatedAsyncioTestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        caplog.set_level(logging.DEBUG)
        self._caplog = caplog

    @allow_windows
    async def test_devtools(self):
        async with remote_chromium() as devtools_url:
            settings_dict = {
                "PLAYWRIGHT_CDP_URL": devtools_url,
                "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True},
            }
            async with make_handler(settings_dict) as handler:
                with StaticMockServer() as server:
                    req = Request(server.urljoin("/index.html"), meta={"playwright": True})
                    resp = await handler._download_request(req, Spider("foo"))
                assert_correct_response(resp, req)
                assert (
                    "scrapy-playwright",
                    logging.WARNING,
                    "Connecting to remote browser, ignoring PLAYWRIGHT_LAUNCH_OPTIONS",
                ) in self._caplog.record_tuples
