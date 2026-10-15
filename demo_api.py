"""Synthetic, localhost-only API. No employer data and no external API calls."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from getpass import getpass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import re
import threading


TICKETS = {
    "T-101": {"id": "T-101", "title": "Webhook retries after timeout", "status": "open"},
    "T-102": {
        "id": "T-102", "title": "Delayed webhook delivery", "status": "pending",
        "body": "A synthetic customer report, omitted from the tool response.",
        "internal_note": "Synthetic internal context, also omitted.",
    },
}


class DemoServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, token: str, port: int = 0, tickets=None):
        self.token = token
        self.tickets = dict(TICKETS) if tickets is None else tickets
        self.authenticated_requests = 0
        super().__init__(("127.0.0.1", port), DemoHandler)

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server_port}"


class DemoHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # No request headers, URLs, ticket contents, or credentials in logs.

    def send_json(self, status, body):
        encoded = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        actual = self.headers.get("Authorization", "").encode()
        expected = f"Bearer {self.server.token}".encode()
        if not hmac.compare_digest(actual, expected):
            return self.send_json(401, {"error": "unauthorized"})
        self.server.authenticated_requests += 1
        ticket = self.server.tickets.get(self.path.removeprefix("/tickets/")) if self.path.startswith("/tickets/") else None
        if ticket is None:
            return self.send_json(404, {"error": "not found"})
        self.send_json(200, ticket)


@contextmanager
def running_api(token: str, tickets=None):
    server = DemoServer(token, tickets=tickets)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    token = getpass("Paste a DISPOSABLE demo-vault token (hidden, never your service-account token): ")
    if re.fullmatch(r"[A-Za-z0-9_-]{24,128}", token) is None:
        parser.error("Use 24–128 characters: letters, digits, underscore, or hyphen.")
    try:
        server = DemoServer(token, args.port)
    except OSError:
        parser.exit(2, "Local port unavailable. Choose another --port.\n")
    print(f"Synthetic API ready at {server.url}. Ctrl+C stops it. Token remains in memory.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
