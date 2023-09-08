import json
import re
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from subprocess import Popen, PIPE
from threading import Thread
from typing import Optional
from urllib.parse import urljoin, urlparse, parse_qs


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
        content_length = int(self.headers.get("Content-Length") or 0)
        body_bytes = b"Request body: " + self.rfile.read(content_length)
        self.send_response(200)
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def do_GET(self) -> None:
        parsed_path = urlparse(self.path)
        query_string = {key: values[0] for key, values in parse_qs(parsed_path.query).items()}

        if delay := int(query_string.get("delay") or 0):
            print(f"Sleeping {delay} seconds on path {parsed_path.path}...")
            time.sleep(delay)

        if parsed_path.path == "/headers":
            self._send_json(dict(self.headers))
        elif parsed_path.path == "/redirect2":
            self.send_response(302)
            self.send_header("Content-Length", "0")
            self.send_header("Location", "/redirect")
            self.end_headers()
        elif parsed_path.path == "/redirect":
            self.send_response(301)
            self.send_header("Content-Length", "0")
            self.send_header("Location", "/headers")
            self.end_headers()
        elif parsed_path.path == "/mancha.pdf":
            body_bytes = (Path(__file__).absolute().parent / "site/files/mancha.pdf").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", 'attachment; filename="mancha.pdf"')
            self.send_header("Content-Length", str(len(body_bytes)))
            self.end_headers()
            self.wfile.write(body_bytes)
        else:
            self._send_json({"error": "unknown path"}, status=404)

    def _send_json(self, body: dict, status: int = 200) -> None:
        body_bytes = json.dumps(body, indent=2).encode("utf8")
        self.send_response(status)
        self.send_header("Content-Length", str(len(body_bytes)))
        self.send_header("Content-Type", "application/json")
        self.end_headers()
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
