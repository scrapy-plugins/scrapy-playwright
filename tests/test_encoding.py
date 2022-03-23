import pytest
from scrapy.http.headers import Headers

from scrapy_playwright.handler import _encode_body


def body_str(charset: str, content: str = "áéíóú") -> str:
    return f"""
        <!doctype html>
        <html>
        <head>
        <p>{content}</p>
        <meta charset="{charset}">
        </head>
        </html>
    """.strip()


@pytest.mark.asyncio
async def test_encode_from_headers():
    text = body_str("gb2312")
    body, encoding = _encode_body(
        headers=Headers({"content-type": "text/html; charset=ISO-8859-1"}),
        text=text,
    )
    assert encoding == "cp1252"
    assert body == text.encode(encoding)


@pytest.mark.asyncio
async def test_encode_from_body():
    text = body_str("gb2312")
    body, encoding = _encode_body(headers=Headers({}), text=text)
    assert encoding == "gb18030"
    assert body == body_str("gb2312").encode(encoding)


@pytest.mark.asyncio
async def test_encode_fallback():
    text = "<html>áéíóú</html>"
    body, encoding = _encode_body(headers=Headers(), text=text)
    assert encoding == "utf-8"
    assert body == "<html>áéíóú</html>".encode(encoding)


@pytest.mark.asyncio
async def test_encode_mismatch():
    text = body_str("gb2312", content="空手道")
    body, encoding = _encode_body(
        headers=Headers({"content-type": "text/html; charset=ISO-8859-1"}),
        text=text,
    )
    assert encoding == "gb18030"
    assert body == text.encode(encoding)
