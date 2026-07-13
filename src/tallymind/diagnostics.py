from __future__ import annotations

from typing import Any

from tallymind.gateway import TallyGateway

EDUCATIONAL_EDITION_REMINDER = (
    "Reminder: confirm this Tally installation is NOT the Educational edition. "
    "Tally has no documented API to detect license edition automatically; the "
    "Educational edition silently truncates date ranges, which can feed "
    "plausible-looking but wrong data to Claude. Check Tally's own "
    "Help > About screen if unsure."
)


def run_doctor(gateway: TallyGateway) -> dict[str, Any]:
    checklist = [EDUCATIONAL_EDITION_REMINDER]
    result: dict[str, Any] = {
        "endpoint": gateway.endpoint,
        "gateway_reachable": False,
        "company_loaded": False,
        "companies": [],
        "checklist": checklist,
        "error": None,
    }
    try:
        response = gateway.export_collection("List of Companies")
    except RuntimeError as exc:
        result["error"] = str(exc)
        checklist.insert(
            0,
            "Tally gateway is unreachable. Open TallyPrime, load a company, and enable "
            "F1 > Settings > Connectivity > Client/Server (Server or Both) with the configured port.",
        )
        return result

    result["gateway_reachable"] = True
    companies = [
        value.get("@NAME", "")
        for value in _iter_company_nodes(response.get("xml", ""))
    ]
    companies = [name for name in companies if name]
    result["companies"] = companies
    result["company_loaded"] = bool(companies)
    if not companies:
        checklist.insert(0, "Gateway is reachable but no company appears loaded — open and load a company in TallyPrime.")
    return result


def _iter_company_nodes(xml_text: str) -> list[dict[str, Any]]:
    from tallymind.xml_requests import xml_to_dict

    try:
        parsed = xml_to_dict(xml_text)
    except Exception:
        return []
    body = parsed.get("ENVELOPE", {}).get("BODY", {})
    if not isinstance(body, dict):
        return []
    node = body.get("COMPANY", [])
    if isinstance(node, dict):
        return [node]
    if isinstance(node, list):
        return [item for item in node if isinstance(item, dict)]
    return []
