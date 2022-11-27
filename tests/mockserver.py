import json
import re
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from subprocess import Popen, PIPE
from threading import Thread
from typing import Optional
from urllib.parse import urljoin


class StaticMockServer:
    """A web server that serves the contents of the sibling "site" directory.
    To be used as a context manager:

        with StaticMockServer() as server:
            url = server.urljoin("/index.html")
            ...
    """

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
        return urljoin(f"http://{self.address}:{self.port}", url)


class _RequestHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        """Echo back the request body"""
        content_length = int(self.headers["Content-Length"])
        body = self.rfile.read(content_length)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Request body: ")
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/headers":
            self._send_json(dict(self.headers))
        elif self.path == "/redirect2":
            self.send_response(302)
            self.send_header("Location", "/redirect")
            self.end_headers()
        elif self.path == "/redirect":
            self.send_response(301)
            self.send_header("Location", "/headers")
            self.end_headers()
        else:
            delay_match = re.match(r"^/delay/(\d+)$", self.path)
            if delay_match:
                delay = int(delay_match.group(1))
                print(f"Sleeping {delay} seconds...")
                time.sleep(delay)
                self._send_json({"delay": delay})
            else:
                self._send_json({"error": "unknown path"}, status=400)

    def _send_json(self, body: dict, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        body_bytes = json.dumps(body, indent=4).encode("utf8")
        self.wfile.write(body_bytes)


class MockServer:
    """A context manager web server using the _RequestHandler class to handle requests."""

    def __enter__(self):
        self.httpd = HTTPServer(("127.0.0.1", 0), _RequestHandler)
        self.address, self.port = self.httpd.server_address
        self.thread = Thread(target=self.httpd.serve_forever)
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.httpd.shutdown()
        self.thread.join()

    def urljoin(self, url: Optional[str] = None) -> str:
        return urljoin(f"http://{self.address}:{self.port}", url)


if __name__ == "__main__":
    with MockServer() as server:
        print(f"Listening at http://{server.address}:{server.port}")
        while True:
            pass
