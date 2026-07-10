#!/usr/bin/env python
"""
Throughput / latency benchmark for the scrapy-playwright download handler.

Unlike the test suite (which checks correctness by downloading each URL once),
this script drives *hundreds* of requests through ``handler._download_request``
at a controlled concurrency level and reports steady-state performance:

    * throughput (requests / second)
    * per-request latency distribution (p50 / p90 / p95 / p99 / max)
    * peak concurrent pages and contexts (from the handler's own stats)
    * peak RSS of the Playwright process tree (if ``psutil`` is installed)

All traffic is served by the in-repo mock servers (no network variance), so the
numbers reflect the cost of the *handler* — page creation/teardown, request
routing, navigation and response building — rather than the cost of the remote
site.

Examples
--------
    # 500 requests, 16 in flight, against the static HTML site
    python benchmarks/benchmark.py --requests 500 --concurrency 16

    # Compare browsers
    python benchmarks/benchmark.py --browser firefox

    # Reuse a single page per request vs. create+destroy (the default)
    python benchmarks/benchmark.py --reuse-page

    # Exercise page methods (scroll an infinite-scroll page) to simulate
    # heavier, JS-driven pages
    python benchmarks/benchmark.py --page-methods scroll

    # Add a server-side delay to model network latency / slow backends
    python benchmarks/benchmark.py --server-delay 0.2 --concurrency 32
"""

import argparse
import asyncio
import statistics
import sys
import time
from contextlib import suppress
from pathlib import Path
from typing import List, Optional

# Allow running from the repo root without installing the package as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# The handler requires the asyncio Twisted reactor; install it before anything
# touches twisted.internet.reactor (mirrors tests/conftest.py).
from twisted.internet.asyncioreactor import install as _install_reactor  # noqa: E402
from twisted.internet.error import ReactorAlreadyInstalledError  # noqa: E402

with suppress(ReactorAlreadyInstalledError):
    _install_reactor()

from scrapy import Request, Spider  # noqa: E402

from tests import make_handler  # noqa: E402
from tests.mockserver import MockServer, StaticMockServer  # noqa: E402
from scrapy_playwright.page import PageMethod  # noqa: E402


def _percentile(values: List[float], pct: float) -> float:
    """Nearest-rank percentile (pct in [0, 100])."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, round(pct / 100 * len(ordered)) - 1))
    return ordered[rank]


class _MemorySampler:
    """Polls the RSS of the Playwright process tree and records the peak."""

    def __init__(self, handler, interval: float = 0.25) -> None:
        self._handler = handler
        self._interval = interval
        self._task: Optional[asyncio.Task] = None
        self.peak_bytes = 0
        try:
            import psutil  # noqa: F401

            self._psutil = psutil
        except ImportError:
            self._psutil = None

    def _proc(self):
        with suppress(Exception):
            pid = self._handler.playwright_context_manager._connection._transport._proc.pid
            return self._psutil.Process(pid)
        return None

    def _tree_rss(self, proc) -> int:
        procs = [proc, *proc.children(recursive=True)]
        total = 0
        for p in procs:
            with suppress(Exception):
                total += p.memory_info().rss
        return total

    async def _run(self) -> None:
        while True:
            proc = self._proc()
            if proc is not None:
                self.peak_bytes = max(self.peak_bytes, self._tree_rss(proc))
            await asyncio.sleep(self._interval)

    def start(self) -> None:
        if self._psutil is not None:
            self._task = asyncio.ensure_future(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task


def _build_request(url: str, args: argparse.Namespace, page=None) -> Request:
    meta: dict = {"playwright": True}
    if args.reuse_page:
        # Ask the handler to hand the page back instead of closing it...
        meta["playwright_include_page"] = True
        # ...and feed a previously-used page back in so the handler reuses it
        # (it only creates a new page when this key is missing or closed).
        if page is not None:
            meta["playwright_page"] = page
    if args.page_methods == "scroll":
        meta["playwright_page_methods"] = [
            PageMethod("evaluate", "window.scrollBy(0, document.body.scrollHeight)"),
            PageMethod("wait_for_timeout", 50),
        ]
    return Request(url, meta=meta, dont_filter=True)


async def _run(args: argparse.Namespace) -> None:
    settings = {
        "PLAYWRIGHT_BROWSER_TYPE": args.browser,
        # Allow the requested concurrency to actually run in parallel.
        "PLAYWRIGHT_MAX_PAGES_PER_CONTEXT": args.concurrency,
        "LOG_LEVEL": "WARNING",
    }

    server_cm = MockServer() if args.server_delay else StaticMockServer()
    with server_cm as server:
        if args.server_delay:
            url = server.urljoin(f"/asdf?delay={args.server_delay}")
        else:
            url = server.urljoin(f"/{args.path}")

        async with make_handler(settings) as handler:
            spider = Spider("benchmark")
            sem = asyncio.Semaphore(args.concurrency)
            latencies: List[float] = []
            # Pool of open pages to reuse across requests (reuse mode only). It
            # holds at most ``concurrency`` pages: a task grabs one if free,
            # otherwise the handler creates a fresh page that then joins the pool.
            pool: "asyncio.Queue" = asyncio.Queue()
            progress = {"done": 0, "show": False}

            async def one_request() -> None:
                async with sem:
                    page = None
                    if args.reuse_page:
                        with suppress(asyncio.QueueEmpty):
                            page = pool.get_nowait()
                    req = _build_request(url, args, page)
                    start = time.perf_counter()
                    resp = await handler._download_request(req, spider)
                    latencies.append(time.perf_counter() - start)
                    if args.reuse_page:
                        returned = resp.meta.get("playwright_page")
                        if returned is not None and not returned.is_closed():
                            pool.put_nowait(returned)
                    if progress["show"]:
                        progress["done"] += 1
                        # Carriage-return a single updating line: "  123/300 ..."
                        print(f"\r  Making requests... {progress['done']}/{args.requests}", end="", flush=True)

            # Warmup (browser launch + first contexts) is excluded from results.
            if args.warmup:
                await asyncio.gather(*(one_request() for _ in range(args.warmup)))
                latencies.clear()

            mem = _MemorySampler(handler)
            mem.start()
            progress["show"] = True
            wall_start = time.perf_counter()
            await asyncio.gather(*(one_request() for _ in range(args.requests)))
            wall = time.perf_counter() - wall_start
            print()  # finish the progress line
            await mem.stop()

            while not pool.empty():
                with suppress(Exception):
                    await pool.get_nowait().close()

            stats = handler.stats.get_stats()

    _report(args, wall, latencies, stats, mem)


def _report(args, wall, latencies, stats, mem) -> None:
    n = len(latencies)
    print("\n=== scrapy-playwright benchmark ===")
    print(f"browser          : {args.browser}")
    print(f"requests         : {n}")
    print(f"target concurrency: {args.concurrency}")
    print(f"page reuse       : {args.reuse_page}")
    print(f"page methods     : {args.page_methods or 'none'}")
    print(f"server delay     : {args.server_delay}s")
    print("-" * 35)
    print(f"wall time        : {wall:.2f} s")
    print(f"throughput       : {n / wall:.1f} req/s")
    print(f"latency mean     : {statistics.mean(latencies) * 1000:.0f} ms")
    print(f"latency p50      : {_percentile(latencies, 50) * 1000:.0f} ms")
    print(f"latency p90      : {_percentile(latencies, 90) * 1000:.0f} ms")
    print(f"latency p95      : {_percentile(latencies, 95) * 1000:.0f} ms")
    print(f"latency p99      : {_percentile(latencies, 99) * 1000:.0f} ms")
    print(f"latency max      : {max(latencies) * 1000:.0f} ms")
    print("-" * 35)
    print(f"pages created    : {stats.get('playwright/page_count')}")
    print(f"peak pages       : {stats.get('playwright/page_count/max_concurrent')}")
    print(f"peak contexts    : {stats.get('playwright/context_count/max_concurrent')}")
    print(f"pw requests      : {stats.get('playwright/request_count')}")
    print(f"pw responses     : {stats.get('playwright/response_count')}")
    if mem.peak_bytes:
        print(f"peak RSS (pw)    : {mem.peak_bytes / 1024 ** 2:.0f} MiB")
    else:
        print("peak RSS (pw)    : n/a (install psutil)")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--requests", type=int, default=300, help="number of timed requests (default: 300)")
    p.add_argument("--concurrency", type=int, default=8, help="max in-flight requests (default: 8)")
    p.add_argument("--warmup", type=int, default=8, help="untimed warmup requests (default: 8)")
    p.add_argument("--browser", default="chromium", choices=["chromium", "firefox", "webkit"])
    p.add_argument("--path", default="index.html", help="static path to fetch (default: index.html)")
    p.add_argument("--reuse-page", action="store_true", help="keep+close a page per request")
    p.add_argument("--page-methods", choices=["scroll"], help="run page methods to simulate heavier pages")
    p.add_argument("--server-delay", type=float, default=0.0, help="server-side delay in seconds")
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(_run(_parse_args()))
