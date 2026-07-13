from unittest.mock import MagicMock

from tallymind.diagnostics import run_doctor
from tallymind.gateway import TallyGateway


def test_doctor_reports_unreachable_gateway() -> None:
    gateway = MagicMock(spec=TallyGateway)
    gateway.endpoint = "http://localhost:9000"
    gateway.export_collection.side_effect = RuntimeError("TallyPrime XML gateway unavailable at http://localhost:9000")

    result = run_doctor(gateway)

    assert result["gateway_reachable"] is False
    assert result["company_loaded"] is False
    assert "unavailable" in result["error"]
    assert any("Educational edition" in item for item in result["checklist"])


def test_doctor_reports_reachable_gateway_with_companies() -> None:
    gateway = MagicMock(spec=TallyGateway)
    gateway.endpoint = "http://localhost:9000"
    gateway.export_collection.return_value = {
        "xml": "<ENVELOPE><BODY><COMPANY NAME=\"ACME\"/></BODY></ENVELOPE>",
        "summary": {"parse_ok": True, "tag_counts": {"COMPANY": 1}},
    }

    result = run_doctor(gateway)

    assert result["gateway_reachable"] is True
    assert result["error"] is None
    assert any("Educational edition" in item for item in result["checklist"])


def test_doctor_reports_no_company_loaded() -> None:
    gateway = MagicMock(spec=TallyGateway)
    gateway.endpoint = "http://localhost:9000"
    gateway.export_collection.return_value = {
        "xml": "<ENVELOPE><BODY></BODY></ENVELOPE>",
        "summary": {"parse_ok": True, "tag_counts": {}},
    }

    result = run_doctor(gateway)

    assert result["gateway_reachable"] is True
    assert result["company_loaded"] is False
    assert any("no company" in item.lower() for item in result["checklist"])
