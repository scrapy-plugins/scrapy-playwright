import asyncio

from typing import Awaitable, Iterator, Optional, Tuple

from scrapy.http.headers import Headers
from scrapy.settings import Settings
from scrapy.utils.python import to_unicode
from w3lib.encoding import html_body_declared_encoding, http_content_type_encoding


async def _async_delay(coro: Awaitable, delay: float) -> None:
    await asyncio.sleep(delay)
    await coro


async def _maybe_await(obj):
    if isinstance(obj, Awaitable):
        return await obj
    return obj


def _possible_encodings(headers: Headers, text: str) -> Iterator[str]:
    if headers.get("content-type"):
        content_type = to_unicode(headers["content-type"])
        yield http_content_type_encoding(content_type)
    yield html_body_declared_encoding(text)


def _encode_body(headers: Headers, text: str) -> Tuple[bytes, str]:
    for encoding in filter(None, _possible_encodings(headers, text)):
        try:
            body = text.encode(encoding)
        except UnicodeEncodeError:
            pass
        else:
            return body, encoding
    return text.encode("utf-8"), "utf-8"  # fallback


def _is_safe_close_error(error: Exception) -> bool:
    """
    Taken verbatim from
    https://github.com/microsoft/playwright-python/blob/v1.20.0/playwright/_impl/_helper.py#L234-L238
    """
    message = str(error)
    return message.endswith("Browser has been closed") or message.endswith(
        "Target page, context or browser has been closed"
    )


def _read_float_setting(settings: Settings, key: str) -> Optional[float]:
    try:
        return float(settings[key])
    except (KeyError, TypeError, ValueError):
        pass
    return None
