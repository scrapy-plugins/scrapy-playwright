import re
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from subprocess import Popen, PIPE
from threading import Thread
from urllib.parse import urljoin


class StaticMockServer:
    def __enter__(self):
        self.proc = Popen(
            [sys.executable, "-u", "-m", "http.server", "0", "--bind", "127.0.0.1"],
            stdout=PIPE,
            cwd=str(Path(__file__).absolute().parent / "site"),
        )
        self.address, self.port = re.search(
            r"^Serving HTTP on (\d+\.\d+\.\d+\.\d+) port (\d+)",
            self.proc.stdout.readline().strip().decode("ascii"),
        ).groups()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.proc.kill()
        self.proc.communicate()

    def urljoin(self, url):
        return urljoin("http://{}:{}".format(self.address, self.port), url)


class _RequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        """
        Echo back the request body
        """
        content_length = int(self.headers["Content-Length"])
        body = self.rfile.read(content_length)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Request body: ")
        self.wfile.write(body)

    def do_GET(self):
        """
        Take a long time to reply
        """
        time.sleep(3)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Hello world!")


class MockServer:
    def __enter__(self):
        self.httpd = HTTPServer(("127.0.0.1", 0), _RequestHandler)
        self.address, self.port = self.httpd.server_address
        self.thread = Thread(target=self.httpd.serve_forever)
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.httpd.shutdown()
        self.thread.join()

    def urljoin(self, url):
        return urljoin("http://{}:{}".format(self.address, self.port), url)
