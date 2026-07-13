"""Live-gateway tests. Require a running TallyPrime with the HTTP gateway
enabled. Skipped by default — this Linux build sandbox has no Tally to test
against. Run on a real Windows + TallyPrime machine with:

    $env:TALLYMIND_LIVE_E2E = "1"
    pytest tests/test_live_e2e.py -v
"""

from __future__ import annotations

import os

import pytest

from tallymind.diagnostics import run_doctor
from tallymind.gateway import TallyGateway
from tallymind.reports import list_companies, list_ledgers

pytestmark = pytest.mark.skipif(
    os.environ.get("TALLYMIND_LIVE_E2E") != "1",
    reason="Set TALLYMIND_LIVE_E2E=1 on a machine with TallyPrime running to exercise these.",
)


@pytest.fixture
def gateway() -> TallyGateway:
    host = os.environ.get("TALLYMIND_TEST_HOST", "localhost")
    port = int(os.environ.get("TALLYMIND_TEST_PORT", "9000"))
    return TallyGateway(host=host, port=port)


def test_doctor_reports_reachable_against_real_tally(gateway: TallyGateway) -> None:
    result = run_doctor(gateway)
    assert result["gateway_reachable"] is True


def test_list_companies_against_real_tally(gateway: TallyGateway) -> None:
    result = list_companies(gateway)
    assert result["summary"].get("parse_ok") is True


def test_list_ledgers_against_real_tally(gateway: TallyGateway) -> None:
    result = list_ledgers(gateway)
    assert isinstance(result["ledgers"], list)
