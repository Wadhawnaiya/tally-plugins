"""TallyMind MCP server — FastMCP tool registration.

Mirrors the itr-mcp plugin's pattern: one file, `@mcp.tool()` on `async def`
functions, every tool returns a JSON string via `json.dumps`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from tallymind import diagnostics, reports, writes
from tallymind.gateway import TallyGateway
from tallymind.state import DEFAULT_STATE_PATH, TallyMindState, TallyMindStateStore

_STATE_PATH: Path = DEFAULT_STATE_PATH

mcp = FastMCP(
    "TallyMind",
    instructions=(
        "Connect to a local TallyPrime instance over its HTTP/XML gateway. "
        "Call tally_doctor first if unsure whether Tally is reachable. All "
        "writes require preview_* then confirm_import with the returned preview_id."
    ),
)


def _store() -> TallyMindStateStore:
    return TallyMindStateStore(_STATE_PATH)


def _gateway_from_state() -> tuple[TallyGateway, TallyMindState]:
    store = _store()
    state = store.load()
    return TallyGateway(host=state.host, port=state.port), state


@mcp.tool()
async def tally_doctor() -> str:
    """Check whether TallyPrime's gateway is reachable and a company is loaded."""
    gateway, _state = _gateway_from_state()
    return json.dumps(diagnostics.run_doctor(gateway), indent=2, ensure_ascii=False)


@mcp.tool()
async def set_connection(host: str, port: int = 9000) -> str:
    """Point TallyMind at a specific Tally host:port (not hardcoded to localhost)."""
    store = _store()
    state = store.load()
    state.host = host
    state.port = port
    store.save(state)
    return json.dumps({"host": host, "port": port}, indent=2)


@mcp.tool()
async def set_company(name: str) -> str:
    """Set the active company name used as the default for subsequent tool calls."""
    store = _store()
    state = store.load()
    state.company = name
    store.save(state)
    return json.dumps({"company": name}, indent=2)


@mcp.tool()
async def list_companies() -> str:
    """List companies known to the connected TallyPrime instance."""
    gateway, _state = _gateway_from_state()
    return json.dumps(reports.list_companies(gateway), indent=2, ensure_ascii=False)


@mcp.tool()
async def list_ledgers(query: str = "") -> str:
    """List ledgers, optionally fuzzy-filtered by a name query (e.g. 'VRO' matches 'VRO Technology')."""
    gateway, state = _gateway_from_state()
    result = reports.list_ledgers(gateway, query=query or None, company=state.company)
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def list_vouchers() -> str:
    """List vouchers for the active company."""
    gateway, state = _gateway_from_state()
    return json.dumps(reports.list_vouchers(gateway, company=state.company), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_balance_sheet() -> str:
    """Export the Balance Sheet for the active company."""
    gateway, state = _gateway_from_state()
    return json.dumps(reports.get_balance_sheet(gateway, company=state.company), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_profit_and_loss() -> str:
    """Export the Profit & Loss A/c for the active company."""
    gateway, state = _gateway_from_state()
    return json.dumps(reports.get_profit_and_loss(gateway, company=state.company), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_trial_balance() -> str:
    """Export the Trial Balance for the active company."""
    gateway, state = _gateway_from_state()
    return json.dumps(reports.get_trial_balance(gateway, company=state.company), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_day_book() -> str:
    """Export the Day Book for the active company."""
    gateway, state = _gateway_from_state()
    return json.dumps(reports.get_day_book(gateway, company=state.company), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_stock_summary() -> str:
    """Export the Stock Summary for the active company."""
    gateway, state = _gateway_from_state()
    return json.dumps(reports.get_stock_summary(gateway, company=state.company), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_gstr1_summary(period: str) -> str:
    """Best-effort GSTR-1 summary for a period (format YYYYMM). Validate against Tally's own screen."""
    gateway, state = _gateway_from_state()
    result = reports.get_gstr1_summary(gateway, period=period, company=state.company)
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def get_gstr3b_summary(period: str) -> str:
    """Best-effort GSTR-3B summary for a period (format YYYYMM). Validate against Tally's own screen."""
    gateway, state = _gateway_from_state()
    result = reports.get_gstr3b_summary(gateway, period=period, company=state.company)
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool(name="preview_ledger_change")
async def preview_ledger_change_tool(
    name: str, parent: str, opening_balance: float = 0.0, billwise: bool = False
) -> str:
    """Dry-run a ledger create/alter: builds the XML and returns a preview_id, mutates nothing."""
    store = _store()
    state = store.load()
    result = writes.preview_ledger_change(
        state, name, parent, opening_balance=opening_balance, billwise=billwise, company=state.company
    )
    store.save(state)
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool(name="preview_voucher")
async def preview_voucher_tool(
    date: str, voucher_type: str, number: str, narration: str, entries: list[list[Any]]
) -> str:
    """Dry-run a voucher post: entries is a list of [ledger_name, signed_amount] pairs, must sum to zero."""
    store = _store()
    state = store.load()
    typed_entries = [(str(ledger), float(amount)) for ledger, amount in entries]
    result = writes.preview_voucher(
        state, date, voucher_type, number, narration, entries=typed_entries, company=state.company
    )
    store.save(state)
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool(name="confirm_import")
async def confirm_import_tool(preview_id: str) -> str:
    """Apply a previously previewed change to TallyPrime. Fails closed if preview_id is unknown/expired.

    The preview is popped from state and persisted to disk *before* the network
    POST to Tally (via the `persist` callback below). This closes a crash-safety
    gap: if the process dies mid-request, the on-disk state already shows the
    preview as consumed, so a retry re-previews instead of risking a duplicate
    POST to Tally.
    """
    gateway, _state = _gateway_from_state()
    store = _store()
    state = store.load()
    try:
        result = writes.confirm_import(state, gateway, preview_id, persist=lambda: store.save(state))
    except KeyError:
        return json.dumps({"error": "unknown_or_expired_preview_id", "preview_id": preview_id}, indent=2)
    store.save(state)
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def raw_gateway_request(xml: str) -> str:
    """Escape hatch: POST a raw Tally XML envelope and return the response."""
    gateway, _state = _gateway_from_state()
    response = gateway.post_xml(xml)
    return json.dumps(response, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    print("=" * 72)
    print("TallyMind MCP Server")
    print("=" * 72)
    print("Tools: tally_doctor, connection/company setup, reports, GST, guarded writes, raw gateway")
    mcp.run()
