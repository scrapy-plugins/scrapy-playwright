import pytest

from scrapy_playwright.page import PageCoroutine


@pytest.mark.asyncio
async def test_page_coroutines():
    screenshot = PageCoroutine("screenshot", "foo", 123, path="/tmp/file", type="png")
    assert screenshot.method == "screenshot"
    assert screenshot.args == ("foo", 123)
    assert screenshot.kwargs == {"path": "/tmp/file", "type": "png"}
    assert screenshot.result is None
    assert str(screenshot) == "<PageCoroutine for method 'screenshot'>"
