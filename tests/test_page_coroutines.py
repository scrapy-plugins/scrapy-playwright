import pytest

from scrapy_playwright.page import PageCoroutine


@pytest.mark.asyncio
async def test_page_coroutines():
    screenshot = PageCoroutine("screenshot", options={"path": "/tmp/file", "type": "png"})
    assert screenshot.method == "screenshot"
    assert screenshot.args == ()
    assert screenshot.kwargs == {"options": {"path": "/tmp/file", "type": "png"}}
    assert screenshot.result is None
    assert str(screenshot) == "<PageCoroutine for method 'screenshot'>"
