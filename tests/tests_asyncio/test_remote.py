import asyncio
import logging
import random
import re
import subprocess
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Tuple
from unittest import IsolatedAsyncioTestCase

import pytest
from playwright.async_api import async_playwright
from scrapy import Request, Spider

from tests import allow_windows, make_handler, assert_correct_response
from tests.mockserver import StaticMockServer


async def _run_chromium_devtools() -> Tuple[subprocess.Popen, str]:
    """Run a Chromium instance in a separate process, return the process
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


def _run_playwright_browser_server() -> Tuple[subprocess.Popen, str]:
    """Start a Playwright server in a separate process, return the process
    object and a string with its websocket endpoint.
    Pass fixed port and ws path via env variables instead of allowing Playwright
    to choose, for some reason I was unable to capture stdout/stderr :shrug:
    """
    port = str(random.randint(60_000, 63_000))
    ws_path = str(uuid.uuid4())
    launch_server_script_path = str(Path(__file__).parent.parent / "launch_browser_server.js")
    command = ["node", launch_server_script_path, port, ws_path]
    proc = subprocess.Popen(command)  # pylint: disable=consider-using-with
    return proc, f"ws:/localhost:{port}/{ws_path}"


@asynccontextmanager
async def remote_browser(is_chrome_devtools_protocol: bool = True):
    """Launch a remote browser that lasts while in the context."""
    proc = url = None
    try:
        if is_chrome_devtools_protocol:
            proc, url = await _run_chromium_devtools()
        else:
            proc, url = _run_playwright_browser_server()
            await asyncio.sleep(1)  # allow some time for the browser to start
    except Exception:
        pass
    else:
        print(f"Browser URL: {url}")
        yield url
    finally:
        if proc:
            proc.kill()
            proc.communicate()


class TestRemote(IsolatedAsyncioTestCase):
    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        caplog.set_level(logging.DEBUG)
        self._caplog = caplog

    @allow_windows
    async def test_connect_devtools(self):
        async with remote_browser(is_chrome_devtools_protocol=True) as devtools_url:
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

    async def test_connect(self):
        async with remote_browser(is_chrome_devtools_protocol=False) as browser_url:
            settings_dict = {
                "PLAYWRIGHT_CONNECT_URL": browser_url,
                "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True},
            }
            async with make_handler(settings_dict) as handler:
                with StaticMockServer() as server:
                    req = Request(server.urljoin("/index.html"), meta={"playwright": True})
                    resp = await handler._download_request(req, Spider("foo"))
                assert_correct_response(resp, req)
                assert (
                    "scrapy-playwright",
                    logging.INFO,
                    "Connecting to remote Playwright",
                ) in self._caplog.record_tuples
                assert (
                    "scrapy-playwright",
                    logging.INFO,
                    "Connected to remote Playwright",
                ) in self._caplog.record_tuples
                assert (
                    "scrapy-playwright",
                    logging.WARNING,
                    "Connecting to remote browser, ignoring PLAYWRIGHT_LAUNCH_OPTIONS",
                ) in self._caplog.record_tuples
