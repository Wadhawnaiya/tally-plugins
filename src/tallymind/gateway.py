from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from tallymind import xml_requests


@dataclass
class TallyGateway:
    host: str = "localhost"
    port: int = 9000
    timeout: float = 10.0

    @property
    def endpoint(self) -> str:
        return f"http://{self.host}:{self.port}"

    def post_xml(self, xml_text: str) -> dict[str, Any]:
        request = urllib.request.Request(
            self.endpoint,
            data=xml_text.encode("utf-8"),
            headers={"Content-Type": "text/xml; charset=utf-8"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
                status_code = getattr(response, "status", response.getcode())
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"TallyPrime XML gateway unavailable at {self.endpoint}. "
                f"Start TallyPrime, ensure Client/Server mode is enabled in "
                f"F1 > Settings > Connectivity, and verify the port. Details: {exc}"
            ) from exc
        return {
            "status_code": status_code,
            "endpoint": self.endpoint,
            "xml": body,
            "summary": xml_requests.response_summary(body),
        }

    def ping(self) -> dict[str, Any]:
        return self.export_collection("List of Companies")

    def export_collection(self, collection: str, company: str | None = None) -> dict[str, Any]:
        return self.post_xml(xml_requests.export_collection_envelope(collection, company=company))

    def sql(self, query: str, company: str | None = None) -> dict[str, Any]:
        return self.post_xml(xml_requests.sql_envelope(query, company=company))

    def export_report(self, report_name: str, company: str | None = None) -> dict[str, Any]:
        return self.post_xml(xml_requests.report_export_envelope(report_name, company=company))

    def import_data(
        self,
        request_data_xml: str,
        company: str | None = None,
        report_name: str = "All Masters",
    ) -> dict[str, Any]:
        return self.post_xml(
            xml_requests.import_data_envelope(request_data_xml, company=company, report_name=report_name)
        )
