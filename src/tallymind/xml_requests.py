from __future__ import annotations

import xml.etree.ElementTree as ET
from html import escape
from typing import Any

TALLY_XML_FORMAT = "$$SysName:XML"


def _tag(name: str, value: str | None = None) -> str:
    if value is None:
        return f"<{name}/>"
    return f"<{name}>{escape(str(value), quote=False)}</{name}>"


def _static_variables(company: str | None = None, extra: dict[str, str] | None = None) -> str:
    pairs = {"SVEXPORTFORMAT": TALLY_XML_FORMAT}
    if company:
        pairs["SVCURRENTCOMPANY"] = company
    if extra:
        pairs.update(extra)
    inner = "".join(_tag(key, value) for key, value in pairs.items())
    return f"<STATICVARIABLES>{inner}</STATICVARIABLES>"


def export_collection_envelope(collection: str, company: str | None = None) -> str:
    return (
        "<ENVELOPE>"
        "<HEADER>"
        "<VERSION>1</VERSION>"
        "<TALLYREQUEST>Export</TALLYREQUEST>"
        "<TYPE>Collection</TYPE>"
        f"<ID>{escape(collection, quote=False)}</ID>"
        "</HEADER>"
        "<BODY><DESC>"
        f"{_static_variables(company)}"
        "</DESC></BODY>"
        "</ENVELOPE>"
    )


def sql_envelope(query: str, company: str | None = None) -> str:
    return (
        "<ENVELOPE>"
        "<HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>"
        "<BODY><EXPORTDATA><REQUESTDESC>"
        "<REPORTNAME>ODBC Report</REPORTNAME>"
        f"<SQLREQUEST TYPE=\"General\" METHOD=\"SQLExecute\">{escape(query, quote=False)}</SQLREQUEST>"
        f"{_static_variables(company)}"
        "</REQUESTDESC><REQUESTDATA></REQUESTDATA></EXPORTDATA></BODY>"
        "</ENVELOPE>"
    )


def report_export_envelope(report_name: str, company: str | None = None) -> str:
    return (
        "<ENVELOPE>"
        "<HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>"
        "<BODY><EXPORTDATA><REQUESTDESC>"
        f"<REPORTNAME>{escape(report_name, quote=False)}</REPORTNAME>"
        f"{_static_variables(company)}"
        "</REQUESTDESC><REQUESTDATA></REQUESTDATA></EXPORTDATA></BODY>"
        "</ENVELOPE>"
    )


def import_data_envelope(
    request_data_xml: str,
    company: str | None = None,
    report_name: str = "All Masters",
) -> str:
    return (
        "<ENVELOPE>"
        "<HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>"
        "<BODY><IMPORTDATA><REQUESTDESC>"
        f"<REPORTNAME>{escape(report_name, quote=False)}</REPORTNAME>"
        f"{_static_variables(company)}"
        "</REQUESTDESC><REQUESTDATA>"
        f"{request_data_xml}"
        "</REQUESTDATA></IMPORTDATA></BODY>"
        "</ENVELOPE>"
    )


def xml_to_dict(xml_text: str) -> dict[str, Any]:
    root = ET.fromstring(xml_text)
    return {root.tag: _node_to_value(root)}


def _node_to_value(node: ET.Element) -> Any:
    children = list(node)
    text = (node.text or "").strip()
    attrs = {f"@{key}": value for key, value in node.attrib.items()}
    if not children:
        if attrs:
            attrs["#text"] = text
            return attrs
        return text
    result: dict[str, Any] = dict(attrs)
    for child in children:
        value = _node_to_value(child)
        if child.tag in result:
            existing = result[child.tag]
            if not isinstance(existing, list):
                result[child.tag] = [existing]
            result[child.tag].append(value)
        else:
            result[child.tag] = value
    if text:
        result["#text"] = text
    return result


def response_summary(xml_text: str) -> dict[str, Any]:
    try:
        parsed = xml_to_dict(xml_text)
    except ET.ParseError as exc:
        return {
            "parse_ok": False,
            "error": str(exc),
            "bytes": len(xml_text.encode("utf-8", errors="ignore")),
            "preview": xml_text[:500],
        }
    root = ET.fromstring(xml_text)
    counts: dict[str, int] = {}
    for elem in root.iter():
        counts[elem.tag] = counts.get(elem.tag, 0) + 1
    return {
        "parse_ok": True,
        "root": root.tag,
        "bytes": len(xml_text.encode("utf-8", errors="ignore")),
        "tag_counts": counts,
        "parsed": parsed,
    }
