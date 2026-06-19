import asyncio
import platform
from dataclasses import dataclass
from threading import Thread
from typing import Awaitable, Dict

from twisted.internet.defer import Deferred
from twisted.python import failure

from scrapy_playwright._utils import logger


@dataclass
class _QueueItem:
    coro: Awaitable
    promise: Deferred | asyncio.Future
    loop: asyncio.AbstractEventLoop | None = None


class _ThreadedLoopAdapter:
    """Utility class to start an asyncio event loop in a new thread and redirect coroutines.
    This allows to run Playwright in a different loop than the Scrapy crawler, allowing to
    use ProactorEventLoop which is supported by Playwright on Windows.
    """

    _loop: asyncio.AbstractEventLoop
    _thread: Thread
    _coro_queue: asyncio.Queue = asyncio.Queue()
    _stop_events: Dict[int, asyncio.Event] = {}

    @classmethod
    async def _handle_coro_deferred(cls, queue_item: _QueueItem) -> None:
        from twisted.internet import reactor

        dfd: Deferred = queue_item.promise

        try:
            result = await queue_item.coro
        except Exception as exc:
            reactor.callFromThread(dfd.errback, failure.Failure(exc))
        else:
            reactor.callFromThread(dfd.callback, result)

    @classmethod
    async def _handle_coro_future(cls, queue_item: _QueueItem) -> None:
        future: asyncio.Future = queue_item.promise
        loop: asyncio.AbstractEventLoop = queue_item.loop  # type: ignore[assignment]
        try:
            result = await queue_item.coro
        except Exception as exc:
            loop.call_soon_threadsafe(future.set_exception, exc)
        else:
            loop.call_soon_threadsafe(future.set_result, result)

    @classmethod
    async def _process_queue(cls) -> None:
        while any(not ev.is_set() for ev in cls._stop_events.values()):
            queue_item = await cls._coro_queue.get()
            if isinstance(queue_item.promise, asyncio.Future):
                asyncio.create_task(cls._handle_coro_future(queue_item))
            elif isinstance(queue_item.promise, Deferred):
                asyncio.create_task(cls._handle_coro_deferred(queue_item))
            cls._coro_queue.task_done()

    @classmethod
    def _deferred_from_coro(cls, coro: Awaitable) -> Deferred:
        dfd: Deferred = Deferred()
        queue_item = _QueueItem(coro=coro, promise=dfd)
        asyncio.run_coroutine_threadsafe(cls._coro_queue.put(queue_item), cls._loop)
        return dfd

    @classmethod
    def _future_from_coro(cls, coro: Awaitable) -> asyncio.Future:
        target_loop = asyncio.get_running_loop()  # Scrapy thread loop
        future: asyncio.Future = asyncio.Future()
        queue_item = _QueueItem(coro=coro, promise=future, loop=target_loop)
        asyncio.run_coroutine_threadsafe(cls._coro_queue.put(queue_item), cls._loop)
        return future

    @classmethod
    def start(cls, download_handler_id: int) -> None:
        """Start the event loop in a new thread if not already started.
        Should be called from the Scrapy thread.
        """
        cls._stop_events[download_handler_id] = asyncio.Event()
        if not getattr(cls, "_loop", None):
            policy = asyncio.DefaultEventLoopPolicy()
            if platform.system() == "Windows":
                policy = asyncio.WindowsProactorEventLoopPolicy()  # type: ignore[attr-defined]
            cls._loop = policy.new_event_loop()

        if not getattr(cls, "_thread", None):
            cls._thread = Thread(target=cls._loop.run_forever, daemon=True)
            cls._thread.start()
            logger.info("Started loop on separate thread: %s", cls._loop)
            asyncio.run_coroutine_threadsafe(cls._process_queue(), cls._loop)

    @classmethod
    def stop(cls, download_handler_id: int) -> None:
        """Wait until all handlers are closed to stop the event loop and join the thread.
        Should be called from the Scrapy thread.
        """
        cls._stop_events[download_handler_id].set()
        if all(ev.is_set() for ev in cls._stop_events.values()):
            asyncio.run_coroutine_threadsafe(cls._coro_queue.join(), cls._loop)
            cls._loop.call_soon_threadsafe(cls._loop.stop)
            cls._thread.join()
