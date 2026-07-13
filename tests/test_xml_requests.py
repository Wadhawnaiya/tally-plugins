from tallymind import xml_requests


def test_export_collection_envelope_contains_collection_and_company():
    xml = xml_requests.export_collection_envelope("List of Companies", company="ACME & Co")
    assert "<TALLYREQUEST>Export</TALLYREQUEST>" in xml
    assert "<TYPE>Collection</TYPE>" in xml
    assert "<ID>List of Companies</ID>" in xml
    assert "<SVCURRENTCOMPANY>ACME &amp; Co</SVCURRENTCOMPANY>" in xml


def test_sql_envelope_escapes_query():
    xml = xml_requests.sql_envelope("Select $Name from Ledger where $Name = 'A&B'")
    assert "A&amp;B" in xml
    assert "ODBC Report" in xml
    assert "SQLExecute" in xml


def test_report_export_envelope():
    xml = xml_requests.report_export_envelope("Balance Sheet", company="Demo")
    assert "<REPORTNAME>Balance Sheet</REPORTNAME>" in xml
    assert "<SVCURRENTCOMPANY>Demo</SVCURRENTCOMPANY>" in xml


def test_import_data_envelope_wraps_request_data():
    xml = xml_requests.import_data_envelope("<TALLYMESSAGE/>", company="Demo", report_name="Vouchers")
    assert "<TALLYREQUEST>Import Data</TALLYREQUEST>" in xml
    assert "<REPORTNAME>Vouchers</REPORTNAME>" in xml
    assert "<TALLYMESSAGE/>" in xml


def test_xml_to_dict_and_summary():
    xml = "<ENVELOPE><BODY><DATA>ok</DATA><DATA>again</DATA></BODY></ENVELOPE>"
    parsed = xml_requests.xml_to_dict(xml)
    assert parsed["ENVELOPE"]["BODY"]["DATA"] == ["ok", "again"]
    summary = xml_requests.response_summary(xml)
    assert summary["parse_ok"] is True
    assert summary["tag_counts"]["DATA"] == 2


def test_response_summary_handles_parse_error():
    summary = xml_requests.response_summary("<ENVELOPE><BODY>")
    assert summary["parse_ok"] is False
    assert "error" in summary
