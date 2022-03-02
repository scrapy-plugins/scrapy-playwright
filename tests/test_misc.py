import pytest
from scrapy.http.headers import Headers

from scrapy_playwright.handler import _get_response_encoding


@pytest.mark.asyncio
async def test_get_response_encoding():
    assert (
        _get_response_encoding(
            headers=Headers({"content-type": "text/html; charset=UTF-8"}),
            body="",
        )
        == "utf-8"
    )
    assert (
        _get_response_encoding(
            headers=Headers(),
            body="""<!doctype html>
<html lang="cn">
<head>
  <meta charset="gb2312">
</head>
</html>
""",
        )
        == "gb18030"
    )
    assert _get_response_encoding(headers=Headers(), body="") is None
