import subprocess
from tempfile import NamedTemporaryFile

import pytest
from scrapy import Spider, Request, FormRequest
from scrapy.http.response.html import HtmlResponse
from scrapy.utils.test import get_crawler

from scrapy_playwright.handler import ScrapyPlaywrightDownloadHandler
from scrapy_playwright.page import PageCoroutine

from tests.mockserver import PostMockServer, StaticMockServer


@pytest.mark.asyncio
async def test_basic_response():
    handler = ScrapyPlaywrightDownloadHandler(get_crawler())
    await handler._launch_browser()

    with StaticMockServer() as server:
        req = Request(server.urljoin("/index.html"), meta={"playwright": True})
        resp = await handler._download_request(req, Spider("foo"))

    assert isinstance(resp, HtmlResponse)
    assert resp.request is req
    assert resp.url == req.url
    assert resp.status == 200
    assert "playwright" in resp.flags
    assert resp.css("a::text").getall() == ["Lorem Ipsum", "Infinite Scroll"]

    await handler.browser.close()


@pytest.mark.asyncio
async def test_post_request():
    handler = ScrapyPlaywrightDownloadHandler(get_crawler())
    await handler._launch_browser()

    with PostMockServer() as server:
        req = FormRequest(server.urljoin("/"), meta={"playwright": True}, formdata={"foo": "bar"})
        resp = await handler._download_request(req, Spider("foo"))

    assert resp.request is req
    assert resp.url == req.url
    assert resp.status == 200
    assert "playwright" in resp.flags
    assert "Request body: foo=bar" in resp.text

    await handler.browser.close()


@pytest.mark.asyncio
async def test_page_coroutine_navigation():
    handler = ScrapyPlaywrightDownloadHandler(get_crawler())
    await handler._launch_browser()

    with StaticMockServer() as server:
        req = Request(
            url=server.urljoin("/index.html"),
            meta={
                "playwright": True,
                "playwright_page_coroutines": [PageCoroutine("click", "a.lorem_ipsum")],
            },
        )
        resp = await handler._download_request(req, Spider("foo"))

    assert isinstance(resp, HtmlResponse)
    assert resp.request is req
    assert resp.url == server.urljoin("/lorem_ipsum.html")
    assert resp.status == 200
    assert "playwright" in resp.flags
    assert resp.css("title::text").get() == "Lorem Ipsum"
    text = resp.css("p::text").get()
    assert text == "Lorem ipsum dolor sit amet, consectetur adipiscing elit."

    await handler.browser.close()


@pytest.mark.asyncio
async def test_page_coroutine_infinite_scroll():
    handler = ScrapyPlaywrightDownloadHandler(get_crawler())
    await handler._launch_browser()

    with StaticMockServer() as server:
        req = Request(
            url=server.urljoin("/scroll.html"),
            meta={
                "playwright": True,
                "playwright_page_coroutines": [
                    PageCoroutine("waitForSelector", "div.quote"),  # first 10 quotes
                    PageCoroutine("evaluate", "window.scrollBy(0, 2000)"),
                    PageCoroutine("waitForSelector", "div.quote:nth-child(11)"),  # 2nd request
                    PageCoroutine("evaluate", "window.scrollBy(0, 2000)"),
                    PageCoroutine("waitForSelector", "div.quote:nth-child(21)"),  # 3rd request
                ],
            },
        )
        resp = await handler._download_request(req, Spider("foo"))

    assert isinstance(resp, HtmlResponse)
    assert resp.request is req
    assert resp.url == server.urljoin("/scroll.html")
    assert resp.status == 200
    assert "playwright" in resp.flags
    assert len(resp.css("div.quote")) == 30

    await handler.browser.close()


@pytest.mark.asyncio
async def test_page_coroutine_screenshot_pdf():
    def get_mimetype(file):
        return subprocess.run(
            ["file", "--mime-type", "--brief", file.name],
            stdout=subprocess.PIPE,
            universal_newlines=True,
        ).stdout.strip()

    png_file = NamedTemporaryFile(mode="w+b")
    pdf_file = NamedTemporaryFile(mode="w+b")
    handler = ScrapyPlaywrightDownloadHandler(get_crawler())
    await handler._launch_browser()

    with StaticMockServer() as server:
        req = Request(
            url=server.urljoin("/index.html"),
            meta={
                "playwright": True,
                "playwright_page_coroutines": {
                    "png": PageCoroutine("screenshot", path=png_file.name, type="png"),
                    "pdf": PageCoroutine("pdf", path=pdf_file.name),
                },
            },
        )
        await handler._download_request(req, Spider("foo"))

        assert get_mimetype(png_file) == "image/png"
        assert get_mimetype(pdf_file) == "application/pdf"

        png_file.file.seek(0)
        assert png_file.file.read() == req.meta["playwright_page_coroutines"]["png"].result
        pdf_file.file.seek(0)
        assert pdf_file.file.read() == req.meta["playwright_page_coroutines"]["pdf"].result

        png_file.close()
        pdf_file.close()

    await handler.browser.close()
