"""Guarded write tools: every mutation goes through preview() then confirm_import()."""

from __future__ import annotations

from html import escape
from typing import Any, Callable

from tallymind.gateway import TallyGateway
from tallymind.state import TallyMindState


def _tag(name: str, value: Any = None) -> str:
    if value is None:
        return f"<{name}/>"
    return f"<{name}>{escape(str(value), quote=False)}</{name}>"


def _money(value: float) -> str:
    return f"{value:.2f}"


def _tally_date(iso_date: str) -> str:
    parts = iso_date.split("-")
    if len(parts) != 3:
        raise ValueError(f"Expected YYYY-MM-DD date, got {iso_date!r}")
    return "".join(parts)


def ledger_message(name: str, parent: str, opening_balance: float = 0.0, billwise: bool = False) -> str:
    opening_xml = _tag("OPENINGBALANCE", _money(opening_balance)) if opening_balance else ""
    return (
        '<TALLYMESSAGE xmlns:UDF="TallyUDF">'
        f'<LEDGER NAME="{escape(name, quote=True)}" RESERVEDNAME="" ACTION="Create">'
        f'{_tag("NAME", name)}{_tag("PARENT", parent)}'
        f'{_tag("ISBILLWISEON", "Yes" if billwise else "No")}'
        f'{_tag("AFFECTSSTOCK", "No")}{opening_xml}'
        "</LEDGER></TALLYMESSAGE>"
    )


def voucher_message(
    date: str,
    voucher_type: str,
    number: str,
    narration: str,
    entries: list[tuple[str, float]],
) -> str:
    total = round(sum(amount for _, amount in entries), 2)
    if total != 0.0:
        raise ValueError(f"Voucher {number} does not balance: {total}")
    entry_xml = []
    for ledger, amount in entries:
        is_debit = amount < 0
        entry_xml.append(
            "<ALLLEDGERENTRIES.LIST>"
            f'{_tag("LEDGERNAME", ledger)}'
            f'{_tag("ISDEEMEDPOSITIVE", "Yes" if is_debit else "No")}'
            f'{_tag("AMOUNT", _money(amount))}'
            "</ALLLEDGERENTRIES.LIST>"
        )
    return (
        '<TALLYMESSAGE xmlns:UDF="TallyUDF">'
        f'<VOUCHER VCHTYPE="{escape(voucher_type, quote=True)}" ACTION="Create" OBJVIEW="Accounting Voucher View">'
        f'{_tag("DATE", _tally_date(date))}{_tag("VOUCHERTYPENAME", voucher_type)}{_tag("VOUCHERNUMBER", number)}'
        f'{_tag("PERSISTEDVIEW", "Accounting Voucher View")}{_tag("NARRATION", narration)}'
        f'{"".join(entry_xml)}'
        "</VOUCHER></TALLYMESSAGE>"
    )


def preview_ledger_change(
    state: TallyMindState,
    name: str,
    parent: str,
    opening_balance: float = 0.0,
    billwise: bool = False,
    company: str | None = None,
) -> dict[str, Any]:
    xml = ledger_message(name, parent, opening_balance=opening_balance, billwise=billwise)
    description = f"Create/alter ledger '{name}' under '{parent}'" + (
        f" with opening balance {opening_balance:.2f}" if opening_balance else ""
    )
    preview_id = state.add_preview("ledger", description, xml, company)
    return {"preview_id": preview_id, "description": description, "xml": xml}


def preview_voucher(
    state: TallyMindState,
    date: str,
    voucher_type: str,
    number: str,
    narration: str,
    entries: list[tuple[str, float]],
    company: str | None = None,
) -> dict[str, Any]:
    xml = voucher_message(date, voucher_type, number, narration, entries)
    description = f"Post {voucher_type} voucher #{number} dated {date}: {narration}"
    preview_id = state.add_preview("voucher", description, xml, company)
    return {"preview_id": preview_id, "description": description, "xml": xml}


def confirm_import(
    state: TallyMindState,
    gateway: TallyGateway,
    preview_id: str,
    persist: Callable[[], None] | None = None,
) -> dict[str, Any]:
    entry = state.pop_preview(preview_id)  # raises KeyError if missing/already used — fails closed
    if persist is not None:
        persist()
    report_name = "Vouchers" if entry["kind"] == "voucher" else "All Masters"
    response = gateway.import_data(entry["xml"], company=entry["company"], report_name=report_name)
    return {
        "preview_id": preview_id,
        "kind": entry["kind"],
        "description": entry["description"],
        "raw_xml": response.get("xml", ""),
        "summary": response.get("summary", {}),
    }
