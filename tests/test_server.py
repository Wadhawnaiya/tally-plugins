# tests/test_server.py
from __future__ import annotations

import asyncio
import json
import threading
import http.server
import socketserver
from contextlib import contextmanager
from typing import Iterator

import pytest

from tallymind import server


class _EchoHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        response = b"<ENVELOPE><BODY><COMPANY NAME=\"Demo Co\"/></BODY></ENVELOPE>"
        self.send_response(200)
        self.send_header("Content-Type", "text/xml")
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, *_args) -> None:
        pass


@contextmanager
def _running_server() -> Iterator[int]:
    httpd = socketserver.TCPServer(("127.0.0.1", 0), _EchoHandler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        httpd.shutdown()
        thread.join(timeout=2)


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "_STATE_PATH", tmp_path / "state.json")
    yield


def test_registered_tool_names_cover_the_full_surface() -> None:
    tool_names = {tool.name for tool in server.mcp._tool_manager.list_tools()}
    expected = {
        "tally_doctor",
        "set_connection",
        "set_company",
        "list_companies",
        "list_ledgers",
        "list_vouchers",
        "get_balance_sheet",
        "get_profit_and_loss",
        "get_trial_balance",
        "get_day_book",
        "get_stock_summary",
        "get_gstr1_summary",
        "get_gstr3b_summary",
        "preview_ledger_change",
        "preview_voucher",
        "confirm_import",
        "raw_gateway_request",
    }
    assert expected.issubset(tool_names)


def test_set_connection_then_tally_doctor_reports_reachable() -> None:
    with _running_server() as port:
        _run(server.set_connection("127.0.0.1", port))
        result = json.loads(_run(server.tally_doctor()))
    assert result["gateway_reachable"] is True
    assert "Demo Co" in result["companies"]


def test_preview_then_confirm_round_trip() -> None:
    with _running_server() as port:
        _run(server.set_connection("127.0.0.1", port))
        preview = json.loads(
            _run(server.preview_ledger_change_tool(name="VRO Technology", parent="Sundry Debtors"))
        )
        assert "preview_id" in preview
        confirmed = json.loads(_run(server.confirm_import_tool(preview_id=preview["preview_id"])))
    assert confirmed["preview_id"] == preview["preview_id"]


def test_confirm_import_unknown_id_returns_error_payload() -> None:
    result = json.loads(_run(server.confirm_import_tool(preview_id="nope")))
    assert result["error"] == "unknown_or_expired_preview_id"


def test_confirm_import_persists_state_before_network_post(monkeypatch) -> None:
    """Proves the `persist` hook is wired, not just present: it verifies the
    on-disk state file already shows the preview as consumed *while the
    network POST to Tally is still in flight* — not merely after
    confirm_import_tool returns. That ordering is the entire crash-safety
    point: if the process died during the POST, a restart must see the
    preview as already used, not as still pending (which could cause a
    retry to double-post the same voucher to Tally).
    """
    from tallymind.gateway import TallyGateway
    from tallymind.state import TallyMindStateStore

    observed: dict[str, set[str]] = {}
    original_import_data = TallyGateway.import_data

    def spy_import_data(self, *args, **kwargs):
        # Read the state file fresh from disk right as the network call is
        # about to happen. If persist() ran first (as required), the
        # preview_id must already be absent here.
        on_disk = TallyMindStateStore(server._STATE_PATH).load()
        observed["pending_ids_during_post"] = set(on_disk.pending_previews.keys())
        return original_import_data(self, *args, **kwargs)

    monkeypatch.setattr(TallyGateway, "import_data", spy_import_data)

    with _running_server() as port:
        _run(server.set_connection("127.0.0.1", port))
        preview = json.loads(
            _run(server.preview_ledger_change_tool(name="VRO Technology", parent="Sundry Debtors"))
        )
        preview_id = preview["preview_id"]

        before = TallyMindStateStore(server._STATE_PATH).load()
        assert preview_id in before.pending_previews

        _run(server.confirm_import_tool(preview_id=preview_id))

    assert "pending_ids_during_post" in observed, "import_data was never called"
    assert preview_id not in observed["pending_ids_during_post"]
