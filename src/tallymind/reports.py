"""Read/reporting tools over the Tally XML gateway.

Query sources, by confidence level:
  - list_ledgers / list_vouchers: ODBC-style `$Field` SQL queries, ported
    verbatim from the proven, tested queries in
    tally-cli/tallyprime/agent-harness's `ledger list` / `voucher list` commands.
  - list_companies / get_balance_sheet / get_profit_and_loss / get_trial_balance /
    get_day_book / get_stock_summary: named Tally report/collection exports,
    also ported from the proven `report export` / `company list` commands.
  - get_gstr1_summary / get_gstr3b_summary: BEST EFFORT. Tally does not
    publicly document an XML/HTTP report name for GSTR exports (see design
    spec section 9, "Open risk"). These call export_report with the report
    names Tally's own UI uses ("GSTR-1", "GSTR-3B") and must be validated
    against a live Tally instance before being trusted.
"""

from __future__ import annotations

from typing import Any

from tallymind import fuzzy
from tallymind.gateway import TallyGateway
from tallymind.xml_requests import xml_to_dict


def _envelope(response: dict[str, Any]) -> dict[str, Any]:
    xml_text = response.get("xml", "")
    try:
        parsed = xml_to_dict(xml_text)
    except Exception:
        parsed = {}
    return {"parsed": parsed, "raw_xml": xml_text, "summary": response.get("summary", {})}


def _sql_rows(xml_text: str) -> list[list[str]]:
    try:
        parsed = xml_to_dict(xml_text)
    except Exception:
        return []
    envelope = parsed.get("ENVELOPE", {})
    body = envelope.get("BODY", {}) if isinstance(envelope, dict) else {}
    data = body.get("DATA", {}) if isinstance(body, dict) else {}
    rows = data.get("ROW", []) if isinstance(data, dict) else []
    if isinstance(rows, dict):
        rows = [rows]
    parsed_rows: list[list[str]] = []
    for row in rows:
        fields = row.get("FLD", []) if isinstance(row, dict) else []
        if isinstance(fields, str):
            fields = [fields]
        parsed_rows.append([f if isinstance(f, str) else "" for f in fields])
    return parsed_rows


def list_companies(gateway: TallyGateway, company: str | None = None) -> dict[str, Any]:
    response = gateway.export_collection("List of Companies", company=company)
    return _envelope(response)


def list_ledgers(gateway: TallyGateway, query: str | None = None, company: str | None = None) -> dict[str, Any]:
    response = gateway.sql("Select $Name, $Parent, $ClosingBalance from Ledger", company=company)
    result = _envelope(response)
    ledgers = [
        {"name": row[0], "parent": row[1] if len(row) > 1 else "", "closing_balance": row[2] if len(row) > 2 else ""}
        for row in _sql_rows(response.get("xml", ""))
        if row and row[0]
    ]
    if query:
        matched_names = set(fuzzy.best_matches(query, [ledger["name"] for ledger in ledgers], limit=10))
        ledgers = [ledger for ledger in ledgers if ledger["name"] in matched_names]
    result["ledgers"] = ledgers
    return result


def list_vouchers(gateway: TallyGateway, company: str | None = None) -> dict[str, Any]:
    response = gateway.sql(
        "Select $Date, $VoucherTypeName, $VoucherNumber, $PartyLedgerName, $Amount from Voucher",
        company=company,
    )
    result = _envelope(response)
    result["vouchers"] = [
        {
            "date": row[0] if len(row) > 0 else "",
            "voucher_type": row[1] if len(row) > 1 else "",
            "voucher_number": row[2] if len(row) > 2 else "",
            "party_ledger": row[3] if len(row) > 3 else "",
            "amount": row[4] if len(row) > 4 else "",
        }
        for row in _sql_rows(response.get("xml", ""))
        if row
    ]
    return result


def _named_report(gateway: TallyGateway, report_name: str, company: str | None) -> dict[str, Any]:
    response = gateway.export_report(report_name, company=company)
    return _envelope(response)


def get_balance_sheet(gateway: TallyGateway, company: str | None = None) -> dict[str, Any]:
    return _named_report(gateway, "Balance Sheet", company)


def get_profit_and_loss(gateway: TallyGateway, company: str | None = None) -> dict[str, Any]:
    return _named_report(gateway, "Profit & Loss A/c", company)


def get_trial_balance(gateway: TallyGateway, company: str | None = None) -> dict[str, Any]:
    return _named_report(gateway, "Trial Balance", company)


def get_day_book(gateway: TallyGateway, company: str | None = None) -> dict[str, Any]:
    return _named_report(gateway, "Day Book", company)


def get_stock_summary(gateway: TallyGateway, company: str | None = None) -> dict[str, Any]:
    return _named_report(gateway, "Stock Summary", company)


def get_gstr1_summary(gateway: TallyGateway, period: str, company: str | None = None) -> dict[str, Any]:
    result = _named_report(gateway, "GSTR-1", company)
    result["best_effort"] = True
    result["note"] = (
        "GSTR-1 export via the XML gateway is not officially documented by Tally; "
        "validate this output against Tally's own GSTR-1 screen before relying on it."
    )
    result["period"] = period
    return result


def get_gstr3b_summary(gateway: TallyGateway, period: str, company: str | None = None) -> dict[str, Any]:
    result = _named_report(gateway, "GSTR-3B", company)
    result["best_effort"] = True
    result["note"] = (
        "GSTR-3B export via the XML gateway is not officially documented by Tally; "
        "validate this output against Tally's own GSTR-3B screen before relying on it."
    )
    result["period"] = period
    return result
