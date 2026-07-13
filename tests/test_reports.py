# tests/test_reports.py
from unittest.mock import MagicMock

from tallymind import reports
from tallymind.gateway import TallyGateway

LEDGER_SQL_XML = (
    "<ENVELOPE><BODY><DATA>"
    "<ROW><FLD>VRO Technology</FLD><FLD>Sundry Debtors</FLD><FLD>94171.00</FLD></ROW>"
    "<ROW><FLD>ABC Traders</FLD><FLD>Sundry Creditors</FLD><FLD>-5000.00</FLD></ROW>"
    "</DATA></BODY></ENVELOPE>"
)


def _mock_gateway(xml: str) -> MagicMock:
    gateway = MagicMock(spec=TallyGateway)
    gateway.sql.return_value = {"xml": xml, "summary": {"parse_ok": True, "tag_counts": {}}}
    gateway.export_collection.return_value = {"xml": xml, "summary": {"parse_ok": True, "tag_counts": {}}}
    gateway.export_report.return_value = {"xml": xml, "summary": {"parse_ok": True, "tag_counts": {}}}
    return gateway


def test_list_ledgers_uses_proven_sql_query() -> None:
    gateway = _mock_gateway(LEDGER_SQL_XML)
    reports.list_ledgers(gateway, company="Demo")
    gateway.sql.assert_called_once()
    query_arg = gateway.sql.call_args.args[0]
    assert query_arg == "Select $Name, $Parent, $ClosingBalance from Ledger"
    assert gateway.sql.call_args.kwargs["company"] == "Demo"


def test_list_ledgers_returns_raw_xml_and_parsed() -> None:
    gateway = _mock_gateway(LEDGER_SQL_XML)
    result = reports.list_ledgers(gateway)
    assert result["raw_xml"] == LEDGER_SQL_XML
    assert "parsed" in result


def test_list_ledgers_fuzzy_filters_by_query() -> None:
    gateway = _mock_gateway(LEDGER_SQL_XML)
    result = reports.list_ledgers(gateway, query="VRO")
    names = [row["name"] for row in result["ledgers"]]
    assert "VRO Technology" in names
    assert "ABC Traders" not in names


def test_list_vouchers_uses_proven_sql_query() -> None:
    gateway = _mock_gateway("<ENVELOPE/>")
    reports.list_vouchers(gateway, company="Demo")
    query_arg = gateway.sql.call_args.args[0]
    assert query_arg == "Select $Date, $VoucherTypeName, $VoucherNumber, $PartyLedgerName, $Amount from Voucher"


def test_get_balance_sheet_uses_named_report_export() -> None:
    gateway = _mock_gateway("<ENVELOPE/>")
    reports.get_balance_sheet(gateway, company="Demo")
    gateway.export_report.assert_called_once_with("Balance Sheet", company="Demo")


def test_get_profit_and_loss_uses_named_report_export() -> None:
    gateway = _mock_gateway("<ENVELOPE/>")
    reports.get_profit_and_loss(gateway)
    gateway.export_report.assert_called_once_with("Profit & Loss A/c", company=None)


def test_get_trial_balance_uses_named_report_export() -> None:
    gateway = _mock_gateway("<ENVELOPE/>")
    reports.get_trial_balance(gateway)
    gateway.export_report.assert_called_once_with("Trial Balance", company=None)


def test_get_day_book_uses_named_report_export() -> None:
    gateway = _mock_gateway("<ENVELOPE/>")
    reports.get_day_book(gateway)
    gateway.export_report.assert_called_once_with("Day Book", company=None)


def test_get_stock_summary_uses_named_report_export() -> None:
    gateway = _mock_gateway("<ENVELOPE/>")
    reports.get_stock_summary(gateway)
    gateway.export_report.assert_called_once_with("Stock Summary", company=None)


def test_list_companies_uses_collection_export() -> None:
    gateway = _mock_gateway("<ENVELOPE/>")
    reports.list_companies(gateway)
    gateway.export_collection.assert_called_once_with("List of Companies", company=None)


def test_gstr1_summary_marked_best_effort() -> None:
    gateway = _mock_gateway("<ENVELOPE/>")
    result = reports.get_gstr1_summary(gateway, period="202604")
    gateway.export_report.assert_called_once_with("GSTR-1", company=None)
    assert result["best_effort"] is True
    assert "not officially documented" in result["note"]
