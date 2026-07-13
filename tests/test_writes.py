from unittest.mock import MagicMock

import pytest

from tallymind.gateway import TallyGateway
from tallymind.state import TallyMindState
from tallymind.writes import (
    confirm_import,
    ledger_message,
    preview_ledger_change,
    preview_voucher,
    voucher_message,
)


def test_ledger_message_contains_name_and_parent() -> None:
    xml = ledger_message("VRO Technology", "Sundry Debtors", opening_balance=1000.0)
    assert 'NAME="VRO Technology"' in xml
    assert "<PARENT>Sundry Debtors</PARENT>" in xml
    assert "<OPENINGBALANCE>1000.00</OPENINGBALANCE>" in xml


def test_voucher_message_balances_entries() -> None:
    xml = voucher_message(
        "2026-04-01",
        "Sales",
        "S-001",
        "Sale to ABC",
        entries=[("ABC Traders", -1000.0), ("Sales Account", 1000.0)],
    )
    assert "<VOUCHERNUMBER>S-001</VOUCHERNUMBER>" in xml
    assert "<DATE>20260401</DATE>" in xml


def test_voucher_message_rejects_unbalanced_entries() -> None:
    with pytest.raises(ValueError, match="does not balance"):
        voucher_message("2026-04-01", "Sales", "S-002", "Bad entry", entries=[("A", -1000.0), ("B", 999.0)])


def test_preview_ledger_change_stores_pending_preview() -> None:
    state = TallyMindState()
    result = preview_ledger_change(state, "VRO Technology", "Sundry Debtors", opening_balance=500.0, company="Demo")
    assert result["preview_id"] in state.pending_previews
    assert "VRO Technology" in result["description"]
    assert "<LEDGER" in result["xml"]


def test_preview_voucher_stores_pending_preview() -> None:
    state = TallyMindState()
    result = preview_voucher(
        state,
        "2026-04-01",
        "Sales",
        "S-001",
        "Sale to ABC",
        entries=[("ABC Traders", -1000.0), ("Sales Account", 1000.0)],
        company="Demo",
    )
    assert result["preview_id"] in state.pending_previews
    assert state.pending_previews[result["preview_id"]]["kind"] == "voucher"


def test_confirm_import_posts_to_gateway_and_consumes_preview() -> None:
    state = TallyMindState()
    preview = preview_ledger_change(state, "VRO Technology", "Sundry Debtors", company="Demo")
    gateway = MagicMock(spec=TallyGateway)
    gateway.import_data.return_value = {"xml": "<ENVELOPE><BODY><CREATED>1</CREATED></BODY></ENVELOPE>", "summary": {}}

    result = confirm_import(state, gateway, preview["preview_id"])

    gateway.import_data.assert_called_once()
    assert preview["preview_id"] not in state.pending_previews
    assert result["preview_id"] == preview["preview_id"]


def test_confirm_import_fails_closed_on_unknown_preview_id() -> None:
    state = TallyMindState()
    gateway = MagicMock(spec=TallyGateway)
    with pytest.raises(KeyError):
        confirm_import(state, gateway, "not-a-real-id")
    gateway.import_data.assert_not_called()


def test_confirm_import_cannot_be_replayed() -> None:
    state = TallyMindState()
    preview = preview_ledger_change(state, "VRO Technology", "Sundry Debtors", company="Demo")
    gateway = MagicMock(spec=TallyGateway)
    gateway.import_data.return_value = {"xml": "<ENVELOPE/>", "summary": {}}

    confirm_import(state, gateway, preview["preview_id"])
    with pytest.raises(KeyError):
        confirm_import(state, gateway, preview["preview_id"])
