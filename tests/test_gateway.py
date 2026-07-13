from __future__ import annotations

import threading
import http.server
import socketserver
from contextlib import contextmanager
from typing import Iterator

import pytest

from tallymind.gateway import TallyGateway


class _EchoHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 (stdlib method name)
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        self.server.last_request_body = body  # type: ignore[attr-defined]
        response = b"<ENVELOPE><BODY><DATA>ok</DATA></BODY></ENVELOPE>"
        self.send_response(200)
        self.send_header("Content-Type", "text/xml")
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, *_args) -> None:  # silence test output
        pass


@contextmanager
def _running_server() -> Iterator[int]:
    httpd = socketserver.TCPServer(("127.0.0.1", 0), _EchoHandler)
    httpd.last_request_body = ""  # type: ignore[attr-defined]
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield port, httpd
    finally:
        httpd.shutdown()
        thread.join(timeout=2)


def test_endpoint_uses_configured_host_and_port() -> None:
    gateway = TallyGateway(host="example.internal", port=1234)
    assert gateway.endpoint == "http://example.internal:1234"


def test_post_xml_returns_parsed_response() -> None:
    with _running_server() as (port, _httpd):
        gateway = TallyGateway(host="127.0.0.1", port=port, timeout=2.0)
        result = gateway.post_xml("<ENVELOPE/>")
    assert result["status_code"] == 200
    assert "ok" in result["xml"]
    assert result["summary"]["parse_ok"] is True


def test_post_xml_unreachable_host_raises_runtime_error() -> None:
    gateway = TallyGateway(host="127.0.0.1", port=1, timeout=1.0)
    with pytest.raises(RuntimeError, match="TallyPrime XML gateway unavailable"):
        gateway.post_xml("<ENVELOPE/>")


def test_export_collection_sends_expected_envelope() -> None:
    with _running_server() as (port, httpd):
        gateway = TallyGateway(host="127.0.0.1", port=port, timeout=2.0)
        gateway.export_collection("List of Companies")
    assert "<ID>List of Companies</ID>" in httpd.last_request_body  # type: ignore[attr-defined]


def test_sql_sends_expected_envelope() -> None:
    with _running_server() as (port, httpd):
        gateway = TallyGateway(host="127.0.0.1", port=port, timeout=2.0)
        gateway.sql("Select $Name from Ledger")
    assert "SQLExecute" in httpd.last_request_body  # type: ignore[attr-defined]


def test_ping_calls_list_of_companies() -> None:
    with _running_server() as (port, httpd):
        gateway = TallyGateway(host="127.0.0.1", port=port, timeout=2.0)
        gateway.ping()
    assert "List of Companies" in httpd.last_request_body  # type: ignore[attr-defined]
