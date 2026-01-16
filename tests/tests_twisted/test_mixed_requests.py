import pytest
from scrapy import Spider, version_info as scrapy_version_info
from scrapy.http import Request, Response
from scrapy.utils.test import get_crawler
from twisted.internet import defer
from twisted.trial.unittest import TestCase

from scrapy_playwright.handler import ScrapyPlaywrightDownloadHandler
from tests.mockserver import StaticMockServer


@pytest.mark.skipif(scrapy_version_info >= (2, 14, 0), reason="Does not apply to Scrapy >= 2.14.0")
class MixedRequestsTestCase(TestCase):
    """
    This test case ensures the handler's 'download_request' method works as expected and
    non-playwright requests are processed correctly. The rest of the tests directly call
    '_download_request', which is a coroutine ('download_request' returns a Deferred).

    Update: since Scrapy 2.14.0, the default download handler uses the async API, returning a
    coroutine from the 'download_request' method, making this test case obsolete.
    """

    timeout_ms = 500

    @defer.inlineCallbacks
    def setUp(self):
        self.server = StaticMockServer()
        self.server.__enter__()
        self.handler = ScrapyPlaywrightDownloadHandler.from_crawler(
            get_crawler(settings_dict={"PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": self.timeout_ms})
        )
        yield self.handler._engine_started()

    @defer.inlineCallbacks
    def tearDown(self):
        self.server.__exit__(None, None, None)
        yield self.handler.close()

    @defer.inlineCallbacks
    def test_download_request(self):
        def _check_regular(response, request):
            self.assertIsInstance(response, Response)
            self.assertEqual(response.css("a::text").getall(), ["Lorem Ipsum", "Infinite Scroll"])
            self.assertEqual(response.url, request.url)
            self.assertEqual(response.status, 200)
            self.assertNotIn("playwright", response.flags)

        def _check_playwright_ok(response, request):
            self.assertIsInstance(response, Response)
            self.assertEqual(response.css("a::text").getall(), ["Lorem Ipsum", "Infinite Scroll"])
            self.assertEqual(response.url, request.url)
            self.assertEqual(response.status, 200)
            self.assertIn("playwright", response.flags)

        def _check_playwright_error(failure, url):
            # different errors depending on the platform
            self.assertTrue(
                f"net::ERR_CONNECTION_REFUSED at {url}" in str(failure.value)
                or f"Page.goto: Timeout {self.timeout_ms}ms exceeded" in str(failure.value)
            )

        req1 = Request(self.server.urljoin("/index.html"))
        yield self.handler.download_request(req1, Spider("foo")).addCallback(
            _check_regular, request=req1
        )

        req2 = Request(self.server.urljoin("/index.html"), meta={"playwright": True})
        yield self.handler.download_request(req2, Spider("foo")).addCallback(
            _check_playwright_ok, request=req2
        )

        req3 = Request("http://localhost:12345/asdf", meta={"playwright": True})
        yield self.handler.download_request(req3, Spider("foo")).addErrback(
            _check_playwright_error, url=req3.url
        )
