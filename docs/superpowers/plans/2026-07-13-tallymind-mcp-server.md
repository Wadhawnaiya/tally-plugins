# TallyMind MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-contained Python FastMCP server (`tallymind`) that talks directly to TallyPrime's HTTP/XML gateway, ports the proven request/response logic from `tally-cli`, adds diagnostics/GST/fuzzy-search/guarded-write features no existing Tally MCP server has, and packages it (plus a one-command Windows installer) per the approved design spec.

**Architecture:** A layered Python package (`src/tallymind/`): `xml_requests.py` (envelope builders/parsers, ported) → `config.py` (Tally install/ini detection, ported) → `gateway.py` (HTTP client to Tally, adapted) → `state.py` (persisted host/port/company/pending-write-previews) → `fuzzy.py` (ledger name resolution) → `diagnostics.py` (`tally_doctor`) → `reports.py` (read tools) → `writes.py` (guarded preview/confirm write tools) → `server.py` (FastMCP tool registration, mirrors `itr-mcp`'s pattern). Packaging (`cowork-plugin/`, `install.ps1`) sits on top and is added last.

**Tech Stack:** Python 3.10+, `mcp[cli]>=1.0` (`mcp.server.fastmcp.FastMCP`), stdlib only for all Tally logic (`urllib.request`, `xml.etree.ElementTree`, `difflib`, `dataclasses`, `json`), `pytest` for tests.

## Global Constraints

- Default Tally gateway port is `9000`; host/port must always be configurable, never hardcoded (spec §3, fixes the `dhananjay1405` open bug #25).
- No dependency on the separately-installed `cli-anything-tallyprime` CLI package — all Tally XML logic lives inside this package (spec §3).
- Every read/report tool returns structured JSON with a `raw_xml` field for debugging, not raw XML alone (spec §4).
- Every write tool is a two-step preview → confirm gate; `confirm_import` must fail closed without a valid, matching `preview_id` (spec §4, §6).
- Follow the `itr-mcp` Cowork plugin convention exactly: `plugin.json` + `skills/` + `mcp_config.json`/`.mcp.json` + a single-file `FastMCP` server using `@mcp.tool()` on `async def` functions returning JSON strings (spec §3, confirmed against `/home/shailesh/cowork/itr-mcp/itr-preparation-skill-plugin-pro/itr-preparation-skill-plugin/itr_preparation_skill_mcp.py`).
- This is a Linux build sandbox: no live Tally instance, no Windows. `install.ps1` and any live-gateway E2E test are written and statically reviewed only — never executed here. Say so in each relevant task rather than treating them as machine-verifiable.
- Publishing to the public GitHub repo `Wadhawnaiya/tally-mcp` requires the user's explicit go-ahead at that step (last task in this plan) — never bundle a `git push` to the public remote into an earlier task.
- Project root: `/home/shailesh/cowork/tally-mcp` (git already initialized; first commit is the design spec).

---

### Task 1: Project scaffolding + ported XML envelope/parsing layer

**Files:**
- Create: `/home/shailesh/cowork/tally-mcp/pyproject.toml`
- Create: `/home/shailesh/cowork/tally-mcp/.gitignore`
- Create: `/home/shailesh/cowork/tally-mcp/src/tallymind/__init__.py`
- Create: `/home/shailesh/cowork/tally-mcp/src/tallymind/xml_requests.py`
- Test: `/home/shailesh/cowork/tally-mcp/tests/test_xml_requests.py`

**Interfaces:**
- Produces: `export_collection_envelope(collection: str, company: str | None = None) -> str`, `sql_envelope(query: str, company: str | None = None) -> str`, `report_export_envelope(report_name: str, company: str | None = None) -> str`, `import_data_envelope(request_data_xml: str, company: str | None = None, report_name: str = "All Masters") -> str`, `xml_to_dict(xml_text: str) -> dict`, `response_summary(xml_text: str) -> dict` — all in `tallymind.xml_requests`, used by every later task.

- [ ] **Step 1: Create project scaffolding**

`pyproject.toml`:
```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "tallymind"
version = "0.1.0"
description = "MCP server connecting TallyPrime to Claude via its HTTP/XML gateway."
authors = [{ name = "CA Shailesh S Wadhawaniya" }]
requires-python = ">=3.10"
dependencies = ["mcp[cli]>=1.0"]

[project.optional-dependencies]
dev = ["pytest>=7.0.0"]

[tool.setuptools.packages.find]
where = ["src"]
```

`.gitignore`:
```
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/
build/
dist/
.venv/
```

`src/tallymind/__init__.py`:
```python
__version__ = "0.1.0"
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_xml_requests.py
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /home/shailesh/cowork/tally-mcp && python3 -m pytest tests/test_xml_requests.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tallymind'` (package not yet importable/installed).

- [ ] **Step 4: Install the package in editable mode**

Run: `cd /home/shailesh/cowork/tally-mcp && pip3 install -e ".[dev]"`
Expected: installs cleanly (this environment already has `mcp` 1.28.1 and `pytest` available; editable install just wires up `src/tallymind`).

- [ ] **Step 5: Implement `src/tallymind/xml_requests.py`**

Port from `/home/shailesh/cowork/tally-cli/tallyprime/agent-harness/cli_anything/tallyprime/core/xml_requests.py` verbatim (module already reviewed; the file is self-contained stdlib-only code with no adaptation needed beyond the package name):

```python
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
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /home/shailesh/cowork/tally-mcp && python3 -m pytest tests/test_xml_requests.py -v`
Expected: 6 passed.

- [ ] **Step 7: Commit**

```bash
cd /home/shailesh/cowork/tally-mcp
git add pyproject.toml .gitignore src/tallymind/__init__.py src/tallymind/xml_requests.py tests/test_xml_requests.py
git commit -m "Scaffold tallymind package; port Tally XML envelope/parsing layer"
```

---

### Task 2: Ported Tally config/ini detection layer

**Files:**
- Create: `/home/shailesh/cowork/tally-mcp/src/tallymind/config.py`
- Test: `/home/shailesh/cowork/tally-mcp/tests/test_config.py`

**Interfaces:**
- Consumes: nothing from Task 1 (pure stdlib module).
- Produces: `DEFAULT_INSTALL_DIR: Path`, `DEFAULT_PORT: int = 9000`, `normalize_install_dir(path=None) -> Path`, `parse_tally_ini(path) -> dict[str, str]`, `read_settings(install_dir=None) -> dict[str, str]`, `server_port(settings=None, default=9000) -> int` — used by `diagnostics.py` (Task 6) and `install.ps1` documentation (Task 11) to auto-detect the gateway port.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config.py
from pathlib import Path

from tallymind import config


def test_parse_tally_ini_preserves_keys_with_spaces(tmp_path: Path) -> None:
    ini = tmp_path / "tally.ini"
    ini.write_text(
        ";; comment\n[TALLY]\nServerPort=9000\nClient Server=Both\nExport Path=C:\\Exports\n",
        encoding="utf-8",
    )
    settings = config.parse_tally_ini(ini)
    assert settings["ServerPort"] == "9000"
    assert settings["Client Server"] == "Both"
    assert settings["Export Path"] == "C:\\Exports"


def test_parse_tally_ini_missing_file_returns_empty(tmp_path: Path) -> None:
    assert config.parse_tally_ini(tmp_path / "missing.ini") == {}


def test_server_port_validates_range() -> None:
    assert config.server_port({"ServerPort": "1234"}) == 1234
    assert config.server_port({"ServerPort": "abc"}) == config.DEFAULT_PORT
    assert config.server_port({"ServerPort": "70000"}) == config.DEFAULT_PORT
    assert config.server_port(None) == config.DEFAULT_PORT


def test_normalize_install_dir_prefers_explicit_path(tmp_path: Path) -> None:
    assert config.normalize_install_dir(str(tmp_path)) == tmp_path


def test_normalize_install_dir_falls_back_to_default(monkeypatch) -> None:
    monkeypatch.delenv("TALLYPRIME_HOME", raising=False)
    monkeypatch.delenv("TALLY_HOME", raising=False)
    monkeypatch.setattr("shutil.which", lambda _name: None)
    assert config.normalize_install_dir() == config.DEFAULT_INSTALL_DIR
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/shailesh/cowork/tally-mcp && python3 -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tallymind.config'`.

- [ ] **Step 3: Implement `src/tallymind/config.py`**

Port from `/home/shailesh/cowork/tally-cli/tallyprime/agent-harness/cli_anything/tallyprime/core/config.py`, trimmed to what `tallymind` actually needs (drop `executable_path`, `config_paths`, `tdl_files` — those are CLI-app-management concerns out of scope per the spec's non-goals; TallyMind only needs ini/port detection):

```python
from __future__ import annotations

import os
import shutil
from pathlib import Path

DEFAULT_INSTALL_DIR = Path(r"C:\Program Files\TallyPrime")
DEFAULT_PORT = 9000


def normalize_install_dir(path: str | os.PathLike[str] | None = None) -> Path:
    """Resolve a TallyPrime install directory without requiring it to exist."""
    candidate = path or os.environ.get("TALLYPRIME_HOME") or os.environ.get("TALLY_HOME")
    if candidate:
        return Path(candidate).expanduser()
    exe = shutil.which("tally.exe") or shutil.which("tally")
    if exe:
        return Path(exe).resolve().parent
    return DEFAULT_INSTALL_DIR


def parse_tally_ini(path: str | os.PathLike[str]) -> dict[str, str]:
    """Parse Tally's loose INI format while preserving keys containing spaces."""
    ini_path = Path(path)
    settings: dict[str, str] = {}
    if not ini_path.exists():
        return settings
    for raw_line in ini_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith(";") or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        settings[key.strip()] = value.strip()
    return settings


def read_settings(install_dir: str | os.PathLike[str] | None = None) -> dict[str, str]:
    return parse_tally_ini(normalize_install_dir(install_dir) / "tally.ini")


def server_port(settings: dict[str, str] | None = None, default: int = DEFAULT_PORT) -> int:
    value = (settings or {}).get("ServerPort", "").strip()
    if not value:
        return default
    try:
        port = int(value)
    except ValueError:
        return default
    if 1 <= port <= 65535:
        return port
    return default
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/shailesh/cowork/tally-mcp && python3 -m pytest tests/test_config.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/shailesh/cowork/tally-mcp
git add src/tallymind/config.py tests/test_config.py
git commit -m "Port trimmed Tally ini/port detection into tallymind.config"
```

---

### Task 3: TallyGateway HTTP client

**Files:**
- Create: `/home/shailesh/cowork/tally-mcp/src/tallymind/gateway.py`
- Test: `/home/shailesh/cowork/tally-mcp/tests/test_gateway.py`

**Interfaces:**
- Consumes: `tallymind.xml_requests.{export_collection_envelope, sql_envelope, report_export_envelope, import_data_envelope, response_summary}` (Task 1).
- Produces: `class TallyGateway` with `__init__(self, host: str = "localhost", port: int = 9000, timeout: float = 10.0)`, property `endpoint -> str`, `post_xml(xml_text: str) -> dict`, `ping() -> dict`, `export_collection(collection: str, company: str | None = None) -> dict`, `sql(query: str, company: str | None = None) -> dict`, `export_report(report_name: str, company: str | None = None) -> dict`, `import_data(request_data_xml: str, company: str | None = None, report_name: str = "All Masters") -> dict`. `post_xml` raises `RuntimeError` with a human-readable message on connection failure. Used by every tool in `diagnostics.py`, `reports.py`, `writes.py` (Tasks 6-8).

- [ ] **Step 1: Write the failing tests**

Use a real local `http.server` in a background thread so the test exercises the actual `urllib.request` HTTP path without needing Tally:

```python
# tests/test_gateway.py
from __future__ import annotations

import threading
import http.server
import socketserver
from contextlib import contextmanager
from typing import Iterator

import pytest

from tallymind.gateway import TallyGateway


class _EchoHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 (stdlib method name)
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        self.server.last_request_body = body  # type: ignore[attr-defined]
        response = b"<ENVELOPE><BODY><DATA>ok</DATA></BODY></ENVELOPE>"
        self.send_response(200)
        self.send_header("Content-Type", "text/xml")
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, *_args) -> None:  # silence test output
        pass


@contextmanager
def _running_server() -> Iterator[int]:
    httpd = socketserver.TCPServer(("127.0.0.1", 0), _EchoHandler)
    httpd.last_request_body = ""  # type: ignore[attr-defined]
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield port, httpd
    finally:
        httpd.shutdown()
        thread.join(timeout=2)


def test_endpoint_uses_configured_host_and_port() -> None:
    gateway = TallyGateway(host="example.internal", port=1234)
    assert gateway.endpoint == "http://example.internal:1234"


def test_post_xml_returns_parsed_response() -> None:
    with _running_server() as (port, _httpd):
        gateway = TallyGateway(host="127.0.0.1", port=port, timeout=2.0)
        result = gateway.post_xml("<ENVELOPE/>")
    assert result["status_code"] == 200
    assert "ok" in result["xml"]
    assert result["summary"]["parse_ok"] is True


def test_post_xml_unreachable_host_raises_runtime_error() -> None:
    gateway = TallyGateway(host="127.0.0.1", port=1, timeout=1.0)
    with pytest.raises(RuntimeError, match="TallyPrime XML gateway unavailable"):
        gateway.post_xml("<ENVELOPE/>")


def test_export_collection_sends_expected_envelope() -> None:
    with _running_server() as (port, httpd):
        gateway = TallyGateway(host="127.0.0.1", port=port, timeout=2.0)
        gateway.export_collection("List of Companies")
    assert "<ID>List of Companies</ID>" in httpd.last_request_body  # type: ignore[attr-defined]


def test_sql_sends_expected_envelope() -> None:
    with _running_server() as (port, httpd):
        gateway = TallyGateway(host="127.0.0.1", port=port, timeout=2.0)
        gateway.sql("Select $Name from Ledger")
    assert "SQLExecute" in httpd.last_request_body  # type: ignore[attr-defined]


def test_ping_calls_list_of_companies() -> None:
    with _running_server() as (port, httpd):
        gateway = TallyGateway(host="127.0.0.1", port=port, timeout=2.0)
        gateway.ping()
    assert "List of Companies" in httpd.last_request_body  # type: ignore[attr-defined]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/shailesh/cowork/tally-mcp && python3 -m pytest tests/test_gateway.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tallymind.gateway'`.

- [ ] **Step 3: Implement `src/tallymind/gateway.py`**

Adapted from `TallyPrimeBackend` in `/home/shailesh/cowork/tally-cli/tallyprime/agent-harness/cli_anything/tallyprime/utils/tallyprime_backend.py`: drop `install_dir`/`executable`/`launch`/`tail_log`/`is_running` (Windows-process-management concerns belong in `diagnostics.py`, Task 6, not the network client), keep the HTTP/XML core:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/shailesh/cowork/tally-mcp && python3 -m pytest tests/test_gateway.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/shailesh/cowork/tally-mcp
git add src/tallymind/gateway.py tests/test_gateway.py
git commit -m "Add TallyGateway HTTP/XML client with configurable host:port"
```

---

### Task 4: Persistent state (host/port/company + pending write previews)

**Files:**
- Create: `/home/shailesh/cowork/tally-mcp/src/tallymind/state.py`
- Test: `/home/shailesh/cowork/tally-mcp/tests/test_state.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (pure stdlib).
- Produces: `DEFAULT_STATE_PATH: Path` (`~/.tallymind/state.json`), `@dataclass TallyMindState` with fields `host: str = "localhost"`, `port: int = 9000`, `company: str | None = None`, `pending_previews: dict[str, dict] = field(default_factory=dict)`, methods `add_preview(self, kind: str, description: str, xml: str, company: str | None) -> str` (returns a new `preview_id`), `pop_preview(self, preview_id: str) -> dict` (raises `KeyError` if missing — consumed by `writes.py` in Task 8), `to_dict()`/`from_dict()`. `class TallyMindStateStore` with `__init__(self, path=None)`, `load() -> TallyMindState`, `save(state: TallyMindState) -> Path`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_state.py
from pathlib import Path

import pytest

from tallymind.state import TallyMindState, TallyMindStateStore


def test_default_state_has_default_host_port() -> None:
    state = TallyMindState()
    assert state.host == "localhost"
    assert state.port == 9000
    assert state.company is None
    assert state.pending_previews == {}


def test_add_preview_returns_unique_ids() -> None:
    state = TallyMindState()
    id1 = state.add_preview("voucher", "Post sales voucher #1", "<TALLYMESSAGE/>", company="Demo")
    id2 = state.add_preview("voucher", "Post sales voucher #2", "<TALLYMESSAGE/>", company="Demo")
    assert id1 != id2
    assert state.pending_previews[id1]["description"] == "Post sales voucher #1"
    assert state.pending_previews[id1]["kind"] == "voucher"


def test_pop_preview_removes_and_returns_entry() -> None:
    state = TallyMindState()
    preview_id = state.add_preview("ledger", "Create ledger X", "<TALLYMESSAGE/>", company=None)
    entry = state.pop_preview(preview_id)
    assert entry["kind"] == "ledger"
    assert preview_id not in state.pending_previews


def test_pop_preview_missing_id_raises_key_error() -> None:
    state = TallyMindState()
    with pytest.raises(KeyError):
        state.pop_preview("does-not-exist")


def test_store_round_trips_state(tmp_path: Path) -> None:
    store = TallyMindStateStore(tmp_path / "state.json")
    state = store.load()
    state.host = "192.168.1.50"
    state.company = "ACME & Co"
    state.add_preview("voucher", "Post sales voucher", "<TALLYMESSAGE/>", company="ACME & Co")
    store.save(state)

    reloaded = store.load()
    assert reloaded.host == "192.168.1.50"
    assert reloaded.company == "ACME & Co"
    assert len(reloaded.pending_previews) == 1


def test_store_load_missing_file_returns_defaults(tmp_path: Path) -> None:
    store = TallyMindStateStore(tmp_path / "missing.json")
    state = store.load()
    assert state.host == "localhost"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/shailesh/cowork/tally-mcp && python3 -m pytest tests/test_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tallymind.state'`.

- [ ] **Step 3: Implement `src/tallymind/state.py`**

Adapted from `SessionState`/`SessionStore` in `/home/shailesh/cowork/tally-cli/tallyprime/agent-harness/cli_anything/tallyprime/core/session.py`: drop `history`/`future`/undo-redo (spec's write-safety model is preview→confirm, not undo/redo — YAGNI), add `pending_previews`:

```python
from __future__ import annotations

import json
import os
import secrets
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

DEFAULT_STATE_PATH = Path.home() / ".tallymind" / "state.json"


@contextmanager
def _file_lock(handle) -> Iterator[None]:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TallyMindState:
    host: str = "localhost"
    port: int = 9000
    company: str | None = None
    pending_previews: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TallyMindState":
        return cls(
            host=data.get("host", "localhost"),
            port=int(data.get("port", 9000)),
            company=data.get("company"),
            pending_previews=dict(data.get("pending_previews", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "company": self.company,
            "pending_previews": self.pending_previews,
        }

    def add_preview(self, kind: str, description: str, xml: str, company: str | None) -> str:
        preview_id = secrets.token_hex(4)
        self.pending_previews[preview_id] = {
            "kind": kind,
            "description": description,
            "xml": xml,
            "company": company,
            "created_at": _now_iso(),
        }
        return preview_id

    def pop_preview(self, preview_id: str) -> dict[str, Any]:
        return self.pending_previews.pop(preview_id)


class TallyMindStateStore:
    def __init__(self, path: str | os.PathLike[str] | None = None):
        self.path = Path(path).expanduser() if path else DEFAULT_STATE_PATH

    def load(self) -> TallyMindState:
        if not self.path.exists():
            return TallyMindState()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return TallyMindState()
        return TallyMindState.from_dict(data)

    def save(self, state: TallyMindState) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(state.to_dict(), indent=2, sort_keys=True)
        with self.path.open("a+", encoding="utf-8") as handle:
            with _file_lock(handle):
                handle.seek(0)
                handle.truncate()
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        return self.path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/shailesh/cowork/tally-mcp && python3 -m pytest tests/test_state.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/shailesh/cowork/tally-mcp
git add src/tallymind/state.py tests/test_state.py
git commit -m "Add persisted TallyMind state with pending write-preview tracking"
```

---

### Task 5: Fuzzy ledger/party name resolution

**Files:**
- Create: `/home/shailesh/cowork/tally-mcp/src/tallymind/fuzzy.py`
- Test: `/home/shailesh/cowork/tally-mcp/tests/test_fuzzy.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (pure stdlib, `difflib`).
- Produces: `best_matches(query: str, candidates: list[str], limit: int = 5, cutoff: float = 0.45) -> list[str]`, `resolve_one(query: str, candidates: list[str]) -> str | None` (returns exact match if present, else the single best fuzzy match if any candidate scores >= cutoff, else `None`). Used by `reports.py` (Task 7) to fix gap #6 ("VRO" → "VRO Technology").

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_fuzzy.py
from tallymind.fuzzy import best_matches, resolve_one


CANDIDATES = ["VRO Technology", "ABC Traders", "XYZ Textiles Pvt Ltd", "Ramesh Patel"]


def test_best_matches_ranks_closest_first() -> None:
    matches = best_matches("VRO", CANDIDATES)
    assert matches[0] == "VRO Technology"


def test_best_matches_respects_limit() -> None:
    matches = best_matches("a", CANDIDATES, limit=2)
    assert len(matches) <= 2


def test_resolve_one_returns_exact_match_even_with_close_fuzzy_alternatives() -> None:
    assert resolve_one("ABC Traders", CANDIDATES) == "ABC Traders"


def test_resolve_one_returns_fuzzy_match_when_no_exact() -> None:
    assert resolve_one("VRO", CANDIDATES) == "VRO Technology"


def test_resolve_one_returns_none_when_nothing_close() -> None:
    assert resolve_one("Completely Unrelated Name Zzz", CANDIDATES) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/shailesh/cowork/tally-mcp && python3 -m pytest tests/test_fuzzy.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tallymind.fuzzy'`.

- [ ] **Step 3: Implement `src/tallymind/fuzzy.py`**

```python
from __future__ import annotations

import difflib


def best_matches(query: str, candidates: list[str], limit: int = 5, cutoff: float = 0.45) -> list[str]:
    return difflib.get_close_matches(query, candidates, n=limit, cutoff=cutoff)


def resolve_one(query: str, candidates: list[str]) -> str | None:
    if query in candidates:
        return query
    matches = best_matches(query, candidates, limit=1)
    return matches[0] if matches else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/shailesh/cowork/tally-mcp && python3 -m pytest tests/test_fuzzy.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/shailesh/cowork/tally-mcp
git add src/tallymind/fuzzy.py tests/test_fuzzy.py
git commit -m "Add fuzzy ledger/party name resolution"
```

---

### Task 6: Connection diagnostics (`tally_doctor`)

**Files:**
- Create: `/home/shailesh/cowork/tally-mcp/src/tallymind/diagnostics.py`
- Test: `/home/shailesh/cowork/tally-mcp/tests/test_diagnostics.py`

**Interfaces:**
- Consumes: `tallymind.gateway.TallyGateway` (Task 3).
- Produces: `run_doctor(gateway: TallyGateway) -> dict` returning `{"endpoint": str, "gateway_reachable": bool, "company_loaded": bool, "companies": list[str], "checklist": list[str], "error": str | None}`. `checklist` always includes the Educational-edition reminder (this cannot be auto-detected — no documented Tally API exposes license edition; see spec §9 — so `run_doctor` states this honestly as a manual-check reminder, not a false claim of automatic detection). Used by `server.py`'s `tally_doctor` tool (Task 9) and referenced by `install.ps1` (Task 11).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_diagnostics.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/shailesh/cowork/tally-mcp && python3 -m pytest tests/test_diagnostics.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tallymind.diagnostics'`.

- [ ] **Step 3: Implement `src/tallymind/diagnostics.py`**

```python
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
    node = body.get("COMPANY", [])
    if isinstance(node, dict):
        return [node]
    if isinstance(node, list):
        return [item for item in node if isinstance(item, dict)]
    return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/shailesh/cowork/tally-mcp && python3 -m pytest tests/test_diagnostics.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/shailesh/cowork/tally-mcp
git add src/tallymind/diagnostics.py tests/test_diagnostics.py
git commit -m "Add tally_doctor connection diagnostics (fixes gap: no diagnostics tool)"
```

---

### Task 7: Read/reporting tools (`reports.py`)

**Files:**
- Create: `/home/shailesh/cowork/tally-mcp/src/tallymind/reports.py`
- Test: `/home/shailesh/cowork/tally-mcp/tests/test_reports.py`

**Interfaces:**
- Consumes: `tallymind.gateway.TallyGateway` (Task 3), `tallymind.fuzzy.{best_matches, resolve_one}` (Task 5).
- Produces (all `(gateway: TallyGateway, company: str | None = None, **kwargs) -> dict` returning `{"parsed": dict, "raw_xml": str, "summary": dict}` plus tool-specific extra keys): `list_companies`, `list_ledgers(gateway, query: str | None = None, company=None)` (extra key `"ledgers": list[dict]`, fuzzy-filtered by `query` when given via `fuzzy.best_matches` against ledger names), `list_vouchers`, `get_balance_sheet`, `get_profit_and_loss`, `get_trial_balance`, `get_day_book`, `get_stock_summary`, `get_gstr1_summary`, `get_gstr3b_summary`. Every function documents in a module docstring which are ODBC-SQL-backed (proven, from the existing CLI) vs. report-name-backed (proven) vs. best-effort/unverified (GST tools — spec §9 open risk). Used by `server.py` (Task 9).

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/shailesh/cowork/tally-mcp && python3 -m pytest tests/test_reports.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tallymind.reports'`.

- [ ] **Step 3: Implement `src/tallymind/reports.py`**

```python
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
    data = parsed.get("ENVELOPE", {}).get("BODY", {}).get("DATA", {})
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/shailesh/cowork/tally-mcp && python3 -m pytest tests/test_reports.py -v`
Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/shailesh/cowork/tally-mcp
git add src/tallymind/reports.py tests/test_reports.py
git commit -m "Add read/reporting tools with fuzzy ledger search (fixes gap: no fuzzy resolution)"
```

---

### Task 8: Guarded write tools (`writes.py`) — preview → confirm

**Files:**
- Create: `/home/shailesh/cowork/tally-mcp/src/tallymind/writes.py`
- Test: `/home/shailesh/cowork/tally-mcp/tests/test_writes.py`

**Interfaces:**
- Consumes: `tallymind.gateway.TallyGateway` (Task 3), `tallymind.state.TallyMindState` (Task 4), `tallymind.xml_requests.import_data_envelope` (Task 1).
- Produces: `ledger_message(name: str, parent: str, opening_balance: float = 0.0, billwise: bool = False) -> str`, `voucher_message(date: str, voucher_type: str, number: str, narration: str, entries: list[tuple[str, float]]) -> str` (raises `ValueError` if entries don't sum to zero) — both ported from `ca_tally_accounting_pipeline.py`. `preview_ledger_change(state: TallyMindState, name: str, parent: str, opening_balance: float = 0.0, company: str | None = None) -> dict` (returns `{"preview_id": str, "description": str, "xml": str}`, stores it in `state.pending_previews` — caller must persist `state` afterward). `preview_voucher(state, date, voucher_type, number, narration, entries, company=None) -> dict` (same shape). `confirm_import(state: TallyMindState, gateway: TallyGateway, preview_id: str) -> dict` (pops the preview from state — raising `KeyError`, i.e. failing closed, if it's missing/already used — then POSTs the import and returns the gateway result plus `{"preview_id": ..., "kind": ...}`). Used by `server.py` (Task 9).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_writes.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/shailesh/cowork/tally-mcp && python3 -m pytest tests/test_writes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tallymind.writes'`.

- [ ] **Step 3: Implement `src/tallymind/writes.py`**

`ledger_message`/`voucher_message` ported from `/tmp/tally_zip_inspect/ca-tally-accounting-automation/scripts/ca_tally_accounting_pipeline.py` (already reviewed), adapted from `Decimal` to `float` since MCP tool arguments arrive as plain JSON numbers:

```python
"""Guarded write tools: every mutation goes through preview() then confirm_import()."""

from __future__ import annotations

from html import escape
from typing import Any

from tallymind.gateway import TallyGateway
from tallymind.state import TallyMindState
from tallymind.xml_requests import import_data_envelope


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


def confirm_import(state: TallyMindState, gateway: TallyGateway, preview_id: str) -> dict[str, Any]:
    entry = state.pop_preview(preview_id)  # raises KeyError if missing/already used — fails closed
    report_name = "Vouchers" if entry["kind"] == "voucher" else "All Masters"
    response = gateway.import_data(entry["xml"], company=entry["company"], report_name=report_name)
    return {
        "preview_id": preview_id,
        "kind": entry["kind"],
        "description": entry["description"],
        "raw_xml": response.get("xml", ""),
        "summary": response.get("summary", {}),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/shailesh/cowork/tally-mcp && python3 -m pytest tests/test_writes.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/shailesh/cowork/tally-mcp
git add src/tallymind/writes.py tests/test_writes.py
git commit -m "Add guarded preview/confirm write tools (fixes gap: no dry-run/undo safety)"
```

---

### Task 9: FastMCP server wiring (`server.py`)

**Files:**
- Create: `/home/shailesh/cowork/tally-mcp/src/tallymind/server.py`
- Test: `/home/shailesh/cowork/tally-mcp/tests/test_server.py`

**Interfaces:**
- Consumes: `tallymind.gateway.TallyGateway` (Task 3), `tallymind.state.TallyMindStateStore` (Task 4), `tallymind.diagnostics.run_doctor` (Task 6), all of `tallymind.reports` (Task 7), all of `tallymind.writes` (Task 8).
- Produces: module-level `mcp = FastMCP("TallyMind", instructions=...)` plus `@mcp.tool()`-decorated `async def` functions: `tally_doctor()`, `set_connection(host: str, port: int = 9000)`, `set_company(name: str)`, `list_companies_tool()` (registered as MCP tool name `list_companies`), `find_ledgers(query: str = "")` (registered as `list_ledgers`), `list_vouchers_tool()`, `get_balance_sheet_tool()`, `get_profit_and_loss_tool()`, `get_trial_balance_tool()`, `get_day_book_tool()`, `get_stock_summary_tool()`, `get_gstr1_summary_tool(period: str)`, `get_gstr3b_summary_tool(period: str)`, `preview_ledger_change_tool(...)`, `preview_voucher_tool(...)`, `confirm_import_tool(preview_id: str)`, `raw_gateway_request(xml: str)`. Every tool returns `json.dumps(..., indent=2, ensure_ascii=False)` matching the `itr-mcp` convention. A module-level `_gateway()`/`_state()` pair reads current host/port/company from the persisted `TallyMindStateStore`, mirroring how `itr_preparation_skill_mcp.py` keeps `current_output_dir` as mutable module state. `if __name__ == "__main__": mcp.run()`.

- [ ] **Step 1: Write the failing tests**

These test the underlying tool coroutines directly (not through the MCP stdio protocol — that would require a running client, out of scope for unit tests) by importing `server` and calling the decorated functions' `.fn` (FastMCP's `Tool.fn` attribute wraps the original coroutine — confirmed available on `mcp` 1.28.1, the version installed in this sandbox) with `TallyGateway`/`TallyMindState` monkeypatched to a local echo server, matching Task 3's pattern:

```python
# tests/test_server.py
from __future__ import annotations

import asyncio
import json
import threading
import http.server
import socketserver
from contextlib import contextmanager
from typing import Iterator

import pytest

from tallymind import server


class _EchoHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        response = b"<ENVELOPE><BODY><COMPANY NAME=\"Demo Co\"/></BODY></ENVELOPE>"
        self.send_response(200)
        self.send_header("Content-Type", "text/xml")
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, *_args) -> None:
        pass


@contextmanager
def _running_server() -> Iterator[int]:
    httpd = socketserver.TCPServer(("127.0.0.1", 0), _EchoHandler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        httpd.shutdown()
        thread.join(timeout=2)


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "_STATE_PATH", tmp_path / "state.json")
    yield


def test_registered_tool_names_cover_the_full_surface() -> None:
    tool_names = {tool.name for tool in server.mcp._tool_manager.list_tools()}
    expected = {
        "tally_doctor",
        "set_connection",
        "set_company",
        "list_companies",
        "list_ledgers",
        "list_vouchers",
        "get_balance_sheet",
        "get_profit_and_loss",
        "get_trial_balance",
        "get_day_book",
        "get_stock_summary",
        "get_gstr1_summary",
        "get_gstr3b_summary",
        "preview_ledger_change",
        "preview_voucher",
        "confirm_import",
        "raw_gateway_request",
    }
    assert expected.issubset(tool_names)


def test_set_connection_then_tally_doctor_reports_reachable() -> None:
    with _running_server() as port:
        _run(server.set_connection.fn("127.0.0.1", port))
        result = json.loads(_run(server.tally_doctor.fn()))
    assert result["gateway_reachable"] is True
    assert "Demo Co" in result["companies"]


def test_preview_then_confirm_round_trip() -> None:
    with _running_server() as port:
        _run(server.set_connection.fn("127.0.0.1", port))
        preview = json.loads(
            _run(server.preview_ledger_change_tool.fn(name="VRO Technology", parent="Sundry Debtors"))
        )
        assert "preview_id" in preview
        confirmed = json.loads(_run(server.confirm_import_tool.fn(preview_id=preview["preview_id"])))
    assert confirmed["preview_id"] == preview["preview_id"]


def test_confirm_import_unknown_id_returns_error_payload() -> None:
    result = json.loads(_run(server.confirm_import_tool.fn(preview_id="nope")))
    assert result["error"] == "unknown_or_expired_preview_id"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/shailesh/cowork/tally-mcp && python3 -m pytest tests/test_server.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tallymind.server'`.

- [ ] **Step 3: Implement `src/tallymind/server.py`**

```python
"""TallyMind MCP server — FastMCP tool registration.

Mirrors the itr-mcp plugin's pattern: one file, `@mcp.tool()` on `async def`
functions, every tool returns a JSON string via `json.dumps`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from tallymind import diagnostics, reports, writes
from tallymind.gateway import TallyGateway
from tallymind.state import DEFAULT_STATE_PATH, TallyMindStateStore

_STATE_PATH: Path = DEFAULT_STATE_PATH

mcp = FastMCP(
    "TallyMind",
    instructions=(
        "Connect to a local TallyPrime instance over its HTTP/XML gateway. "
        "Call tally_doctor first if unsure whether Tally is reachable. All "
        "writes require preview_* then confirm_import with the returned preview_id."
    ),
)


def _store() -> TallyMindStateStore:
    return TallyMindStateStore(_STATE_PATH)


def _gateway_from_state() -> tuple[TallyGateway, "object"]:
    store = _store()
    state = store.load()
    return TallyGateway(host=state.host, port=state.port), state


@mcp.tool()
async def tally_doctor() -> str:
    """Check whether TallyPrime's gateway is reachable and a company is loaded."""
    gateway, _state = _gateway_from_state()
    return json.dumps(diagnostics.run_doctor(gateway), indent=2, ensure_ascii=False)


@mcp.tool()
async def set_connection(host: str, port: int = 9000) -> str:
    """Point TallyMind at a specific Tally host:port (not hardcoded to localhost)."""
    store = _store()
    state = store.load()
    state.host = host
    state.port = port
    store.save(state)
    return json.dumps({"host": host, "port": port}, indent=2)


@mcp.tool()
async def set_company(name: str) -> str:
    """Set the active company name used as the default for subsequent tool calls."""
    store = _store()
    state = store.load()
    state.company = name
    store.save(state)
    return json.dumps({"company": name}, indent=2)


@mcp.tool()
async def list_companies() -> str:
    """List companies known to the connected TallyPrime instance."""
    gateway, _state = _gateway_from_state()
    return json.dumps(reports.list_companies(gateway), indent=2, ensure_ascii=False)


@mcp.tool()
async def list_ledgers(query: str = "") -> str:
    """List ledgers, optionally fuzzy-filtered by a name query (e.g. 'VRO' matches 'VRO Technology')."""
    gateway, state = _gateway_from_state()
    result = reports.list_ledgers(gateway, query=query or None, company=state.company)
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def list_vouchers() -> str:
    """List vouchers for the active company."""
    gateway, state = _gateway_from_state()
    return json.dumps(reports.list_vouchers(gateway, company=state.company), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_balance_sheet() -> str:
    """Export the Balance Sheet for the active company."""
    gateway, state = _gateway_from_state()
    return json.dumps(reports.get_balance_sheet(gateway, company=state.company), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_profit_and_loss() -> str:
    """Export the Profit & Loss A/c for the active company."""
    gateway, state = _gateway_from_state()
    return json.dumps(reports.get_profit_and_loss(gateway, company=state.company), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_trial_balance() -> str:
    """Export the Trial Balance for the active company."""
    gateway, state = _gateway_from_state()
    return json.dumps(reports.get_trial_balance(gateway, company=state.company), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_day_book() -> str:
    """Export the Day Book for the active company."""
    gateway, state = _gateway_from_state()
    return json.dumps(reports.get_day_book(gateway, company=state.company), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_stock_summary() -> str:
    """Export the Stock Summary for the active company."""
    gateway, state = _gateway_from_state()
    return json.dumps(reports.get_stock_summary(gateway, company=state.company), indent=2, ensure_ascii=False)


@mcp.tool()
async def get_gstr1_summary(period: str) -> str:
    """Best-effort GSTR-1 summary for a period (format YYYYMM). Validate against Tally's own screen."""
    gateway, state = _gateway_from_state()
    result = reports.get_gstr1_summary(gateway, period=period, company=state.company)
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def get_gstr3b_summary(period: str) -> str:
    """Best-effort GSTR-3B summary for a period (format YYYYMM). Validate against Tally's own screen."""
    gateway, state = _gateway_from_state()
    result = reports.get_gstr3b_summary(gateway, period=period, company=state.company)
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def preview_ledger_change_tool(
    name: str, parent: str, opening_balance: float = 0.0, billwise: bool = False
) -> str:
    """Dry-run a ledger create/alter: builds the XML and returns a preview_id, mutates nothing."""
    store = _store()
    state = store.load()
    result = writes.preview_ledger_change(
        state, name, parent, opening_balance=opening_balance, billwise=billwise, company=state.company
    )
    store.save(state)
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def preview_voucher_tool(
    date: str, voucher_type: str, number: str, narration: str, entries: list[list[Any]]
) -> str:
    """Dry-run a voucher post: entries is a list of [ledger_name, signed_amount] pairs, must sum to zero."""
    store = _store()
    state = store.load()
    typed_entries = [(str(ledger), float(amount)) for ledger, amount in entries]
    result = writes.preview_voucher(
        state, date, voucher_type, number, narration, entries=typed_entries, company=state.company
    )
    store.save(state)
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def confirm_import_tool(preview_id: str) -> str:
    """Apply a previously previewed change to TallyPrime. Fails closed if preview_id is unknown/expired."""
    gateway, _state = _gateway_from_state()
    store = _store()
    state = store.load()
    try:
        result = writes.confirm_import(state, gateway, preview_id)
    except KeyError:
        return json.dumps({"error": "unknown_or_expired_preview_id", "preview_id": preview_id}, indent=2)
    store.save(state)
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def raw_gateway_request(xml: str) -> str:
    """Escape hatch: POST a raw Tally XML envelope and return the response."""
    gateway, _state = _gateway_from_state()
    response = gateway.post_xml(xml)
    return json.dumps(response, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    print("=" * 72)
    print("TallyMind MCP Server")
    print("=" * 72)
    print("Tools: tally_doctor, connection/company setup, reports, GST, guarded writes, raw gateway")
    mcp.run()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/shailesh/cowork/tally-mcp && python3 -m pytest tests/test_server.py -v`
Expected: 4 passed. (`mcp._tool_manager.list_tools()` returning `Tool` objects with `.name` and an awaitable `.fn` is confirmed against the actual installed `mcp` 1.28.1 package in this sandbox, not assumed.)

- [ ] **Step 5: Run the full test suite**

Run: `cd /home/shailesh/cowork/tally-mcp && python3 -m pytest -v`
Expected: all tests from Tasks 1-9 pass (≈44 tests).

- [ ] **Step 6: Commit**

```bash
cd /home/shailesh/cowork/tally-mcp
git add src/tallymind/server.py tests/test_server.py
git commit -m "Wire TallyMind FastMCP server exposing the full tool surface"
```

---

### Task 10: Cowork plugin packaging

**Files:**
- Create: `/home/shailesh/cowork/tally-mcp/cowork-plugin/plugin.json`
- Create: `/home/shailesh/cowork/tally-mcp/cowork-plugin/mcp_config.json`
- Create: `/home/shailesh/cowork/tally-mcp/cowork-plugin/.mcp.json`
- Create: `/home/shailesh/cowork/tally-mcp/cowork-plugin/skills/tally-mind/SKILL.md`
- Test: `/home/shailesh/cowork/tally-mcp/tests/test_plugin_packaging.py`

**Interfaces:**
- Consumes: nothing (static packaging files), but must reference real paths/module names from Tasks 1-9 (`python3 -m tallymind.server`).
- Produces: a Cowork/Codex-loadable plugin folder mirroring `/home/shailesh/cowork/itr-mcp/itr-preparation-skill-plugin-pro/itr-preparation-skill-plugin/`'s shape, so it can drop into the user's CA course materials the same way `itr-preparation-skill-plugin` does.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_plugin_packaging.py
import json
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parents[1] / "cowork-plugin"


def test_plugin_json_is_valid_and_points_at_mcp_config() -> None:
    data = json.loads((PLUGIN_DIR / "plugin.json").read_text(encoding="utf-8"))
    assert data["name"] == "tallymind-mcp-plugin"
    assert data["mcpServers"] == "./mcp_config.json"
    assert data["skills"] == "./skills/"


def test_mcp_config_and_mcp_json_agree_on_command() -> None:
    mcp_config = json.loads((PLUGIN_DIR / "mcp_config.json").read_text(encoding="utf-8"))
    mcp_json = json.loads((PLUGIN_DIR / ".mcp.json").read_text(encoding="utf-8"))
    for data in (mcp_config, mcp_json):
        entry = data["mcpServers"]["tallymind"]
        assert entry["command"] == "python3"
        assert entry["args"] == ["-m", "tallymind.server"]


def test_skill_md_exists_and_names_the_plugin() -> None:
    content = (PLUGIN_DIR / "skills" / "tally-mind" / "SKILL.md").read_text(encoding="utf-8")
    assert "tally-mind" in content
    assert "tally_doctor" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/shailesh/cowork/tally-mcp && python3 -m pytest tests/test_plugin_packaging.py -v`
Expected: FAIL (files don't exist yet).

- [ ] **Step 3: Create `cowork-plugin/plugin.json`**

```json
{
  "name": "tallymind-mcp-plugin",
  "version": "0.1.0",
  "description": "MCP plugin connecting TallyPrime to Claude via its HTTP/XML gateway, with diagnostics, GST tools, and guarded writes.",
  "author": {
    "name": "CA Shailesh S Wadhawaniya",
    "email": "ca@tallymind.local"
  },
  "license": "Proprietary",
  "keywords": ["tally", "tallyprime", "accounting", "gst", "mcp", "india"],
  "skills": "./skills/",
  "mcpServers": "./mcp_config.json",
  "interface": {
    "displayName": "TallyMind MCP",
    "shortDescription": "Talk to TallyPrime in plain English from Claude.",
    "longDescription": "Connects Claude to a local TallyPrime instance over its HTTP/XML gateway: connection diagnostics, ledgers/vouchers/reports/GST summaries with fuzzy name search, and guarded preview-then-confirm writes.",
    "developerName": "CA Shailesh S Wadhawaniya",
    "category": "Finance",
    "capabilities": ["Interactive", "LocalFiles"],
    "brandColor": "#0F766E",
    "defaultPrompt": [
      "Using TallyMind, run tally_doctor and tell me if I'm connected.",
      "Which clients have GST mismatches this quarter?",
      "Show me overdue debtors past 90 days."
    ]
  }
}
```

- [ ] **Step 4: Create `cowork-plugin/mcp_config.json` and `cowork-plugin/.mcp.json`**

`mcp_config.json`:
```json
{
  "mcpServers": {
    "tallymind": {
      "command": "python3",
      "args": ["-m", "tallymind.server"],
      "cwd": "."
    }
  }
}
```

`.mcp.json`:
```json
{
  "mcpServers": {
    "tallymind": {
      "command": "python3",
      "args": ["-m", "tallymind.server"],
      "cwd": ".",
      "env": {
        "TALLYMIND_STATE_PATH": "${HOME}/.tallymind/state.json"
      }
    }
  }
}
```

- [ ] **Step 5: Create `cowork-plugin/skills/tally-mind/SKILL.md`**

```markdown
---
name: tally-mind
description: Use when the user wants to query or update a local TallyPrime company via Claude — checking connectivity, reading ledgers/vouchers/reports/GST summaries, or posting guarded voucher/ledger changes.
---

# TallyMind

Connects Claude to TallyPrime's HTTP/XML gateway. Requires TallyPrime open on
the same Windows machine, with a company loaded and F1 > Settings >
Connectivity > Client/Server enabled (default port 9000).

## First step, every session

Call `tally_doctor` before anything else. It reports whether the gateway is
reachable, whether a company is loaded, and reminds you to confirm this is not
the Educational edition (which silently truncates date ranges).

## Reading data

`list_companies`, `list_ledgers` (pass `query` for fuzzy name search, e.g.
"VRO" finds "VRO Technology"), `list_vouchers`, `get_balance_sheet`,
`get_profit_and_loss`, `get_trial_balance`, `get_day_book`,
`get_stock_summary`. GST tools (`get_gstr1_summary`, `get_gstr3b_summary`)
are best-effort — Tally does not publicly document these report names over
XML; cross-check against Tally's own GST screens.

## Writing data — always two steps

1. `preview_ledger_change` or `preview_voucher` — builds the XML, returns a
   `preview_id`. Nothing is sent to Tally yet.
2. `confirm_import` with that exact `preview_id` — only this call mutates
   Tally. A `preview_id` can only be confirmed once.

Never call `confirm_import` without first showing the user the preview's
`description` and getting their explicit go-ahead — this mirrors the
`--apply --yes` safety gate used elsewhere in this user's Tally tooling.

## Switching connection or company

`set_connection(host, port)` if Tally isn't on `localhost:9000`.
`set_company(name)` to set the default company for subsequent calls.

## Professional guardrail

Output from writes is a review-ready change, not a substitute for a
qualified Chartered Accountant's review before anything is posted for
compliance or client reporting purposes.
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd /home/shailesh/cowork/tally-mcp && python3 -m pytest tests/test_plugin_packaging.py -v`
Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
cd /home/shailesh/cowork/tally-mcp
git add cowork-plugin tests/test_plugin_packaging.py
git commit -m "Add Cowork plugin packaging mirroring the itr-mcp convention"
```

---

### Task 11: Repo README

**Files:**
- Create: `/home/shailesh/cowork/tally-mcp/README.md`

**Interfaces:**
- Consumes: nothing (documentation only); references the one-command install line that Task 12 will make real.

- [ ] **Step 1: Write `README.md`**

```markdown
# TallyMind MCP

A Tally MCP server that fixes the six gaps every other one has: hardcoded
`localhost`, no connection diagnostics, no dry-run/undo safety on writes, no
GST-specific tools, session state lost on restart, and manual
`claude_desktop_config.json` editing.

## Install (Windows, same PC as TallyPrime + Claude Desktop)

```powershell
irm https://raw.githubusercontent.com/Wadhawnaiya/tally-mcp/main/install.ps1 | iex
```

This installs Python if needed, installs TallyMind, detects your running
Tally gateway, registers the server with Claude Desktop (and Claude Code, if
present) without hand-editing any JSON, and runs a connectivity check.

## Requirements

- TallyPrime Silver/Gold (not Educational — it silently truncates date
  ranges), with the HTTP/XML gateway enabled: `F1 > Settings > Connectivity >
  Client/Server = Server (or Both)`, port `9000` by default.
- Windows, since TallyPrime itself is Windows-only.
- Claude Desktop and/or Claude Code.

## Development

```bash
pip install -e ".[dev]"
pytest
```

`install.ps1` is Windows-only and cannot be exercised in a Linux dev
environment; review it manually and test on a real Windows + TallyPrime
machine before relying on it.

## License

Proprietary — CA Shailesh S Wadhawaniya.
```

- [ ] **Step 2: Commit**

```bash
cd /home/shailesh/cowork/tally-mcp
git add README.md
git commit -m "Add repo README"
```

---

### Task 12: One-command Windows installer (`install.ps1`)

**Files:**
- Create: `/home/shailesh/cowork/tally-mcp/install.ps1`

**Interfaces:**
- Consumes: the published pip-installable `tallymind` package (Tasks 1-9) and `cowork-plugin/` layout (Task 10) conceptually — it installs `tallymind` from the same GitHub repo it lives in (`pip install git+https://github.com/Wadhawnaiya/tally-mcp.git`), so it only becomes fully live once Task 13 publishes the repo.
- Produces: a self-contained PowerShell script. **This cannot be executed or syntax-checked with a PowerShell interpreter in this Linux sandbox** (`pwsh` is not installed here — confirmed) — verification here is a careful manual read-through plus keeping every step's PowerShell simple/standard (`Get-Command`, `winget`, `Invoke-RestMethod`, `Test-Path`, `ConvertTo-Json`/`ConvertFrom-Json`) rather than exotic syntax. Flag this limitation explicitly to the user; a real test on a Windows + TallyPrime machine is needed before this is trusted.

- [ ] **Step 1: Write `install.ps1`**

```powershell
# TallyMind one-command installer
# Usage: irm https://raw.githubusercontent.com/Wadhawnaiya/tally-mcp/main/install.ps1 | iex

$ErrorActionPreference = "Stop"

function Write-Step($message) {
    Write-Host ""
    Write-Host "==> $message" -ForegroundColor Cyan
}

function Write-Ok($message) {
    Write-Host "    OK: $message" -ForegroundColor Green
}

function Write-Warn($message) {
    Write-Host "    WARNING: $message" -ForegroundColor Yellow
}

Write-Step "Checking for Python 3.10+"
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Warn "Python not found. Attempting install via winget."
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw "winget is not available. Install Python 3.10+ manually from https://python.org and re-run this script."
    }
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) {
        throw "Python install did not complete. Open a new PowerShell window and re-run this script."
    }
}
Write-Ok "Python found: $((python --version))"

Write-Step "Installing TallyMind"
python -m pip install --upgrade pip | Out-Null
python -m pip install "git+https://github.com/Wadhawnaiya/tally-mcp.git"
Write-Ok "tallymind package installed"

Write-Step "Looking for a running TallyPrime gateway"
$tallyHost = "localhost"
$tallyPort = 9000
$reachable = $false
try {
    $response = Invoke-WebRequest -Uri "http://${tallyHost}:${tallyPort}" -TimeoutSec 3 -UseBasicParsing
    $reachable = $true
    Write-Ok "Found a Tally gateway responding at ${tallyHost}:${tallyPort}"
} catch {
    Write-Warn "No Tally gateway found at ${tallyHost}:${tallyPort} yet."
    Write-Host "    Make sure TallyPrime is open, a company is loaded, and F1 > Settings >"
    Write-Host "    Connectivity > Client/Server is set to Server (or Both) with port 9000."
    $customPort = Read-Host "    Press Enter to keep port 9000, or type a different port"
    if ($customPort) { $tallyPort = [int]$customPort }
}

Write-Step "Registering TallyMind with Claude Desktop"
$claudeConfigPath = Join-Path $env:APPDATA "Claude\claude_desktop_config.json"
$claudeConfigDir = Split-Path $claudeConfigPath -Parent
if (-not (Test-Path $claudeConfigDir)) {
    New-Item -ItemType Directory -Path $claudeConfigDir -Force | Out-Null
}
if (Test-Path $claudeConfigPath) {
    Copy-Item $claudeConfigPath "$claudeConfigPath.bak" -Force
    Write-Ok "Backed up existing config to claude_desktop_config.json.bak"
    $config = Get-Content $claudeConfigPath -Raw | ConvertFrom-Json -AsHashtable
} else {
    $config = @{}
}
if (-not $config.ContainsKey("mcpServers")) {
    $config["mcpServers"] = @{}
}
$config["mcpServers"]["tallymind"] = @{
    "command" = "python"
    "args"    = @("-m", "tallymind.server")
    "env"     = @{ "TALLYMIND_STATE_PATH" = "$env:USERPROFILE\.tallymind\state.json" }
}
($config | ConvertTo-Json -Depth 10) | Set-Content -Path $claudeConfigPath -Encoding UTF8
Write-Ok "Wrote $claudeConfigPath"

Write-Step "Registering TallyMind with Claude Code (if installed)"
$claudeCli = Get-Command claude -ErrorAction SilentlyContinue
if ($claudeCli) {
    claude mcp add --transport stdio tallymind -- python -m tallymind.server
    Write-Ok "Registered with Claude Code via 'claude mcp add'"
} else {
    Write-Host "    Claude Code CLI not found — skipping (Claude Desktop registration above still applies)."
}

Write-Step "Running a connection self-test"
python -c "
from tallymind.gateway import TallyGateway
from tallymind.diagnostics import run_doctor
import json
gateway = TallyGateway(host='$tallyHost', port=$tallyPort)
print(json.dumps(run_doctor(gateway), indent=2))
"

Write-Step "Done"
Write-Host "Restart Claude Desktop completely (quit from the system tray, not just close the window)"
Write-Host "so it picks up the new tallymind server. Then ask Claude: 'Using TallyMind, run tally_doctor.'"
```

- [ ] **Step 2: Manual review checklist (record the outcome as a code comment at the top of the file once checked)**

Confirm by reading (cannot execute here): every external command used (`winget`, `python`, `pip`, `Invoke-WebRequest`, `ConvertFrom-Json -AsHashtable`, `claude`) is either checked for existence first or has a clear failure message; the script never silently swallows an error (`$ErrorActionPreference = "Stop"` plus explicit `try/catch` only around the two genuinely-optional steps: Tally gateway probe and Claude Code detection); the existing `claude_desktop_config.json` is always backed up before being overwritten; JSON is built via `ConvertTo-Json`/`ConvertFrom-Json`, never hand-templated strings, so it can't corrupt an existing config the way the manual instructions in the researched competitor projects do.

- [ ] **Step 3: Commit**

```bash
cd /home/shailesh/cowork/tally-mcp
git add install.ps1
git commit -m "Add one-command Windows installer (untested outside this sandbox — needs a real Windows+Tally run)"
```

---

### Task 13: Live-gateway end-to-end test stub (written, not run here)

**Files:**
- Create: `/home/shailesh/cowork/tally-mcp/tests/test_live_e2e.py`

**Interfaces:**
- Consumes: `tallymind.gateway.TallyGateway`, `tallymind.diagnostics.run_doctor`, `tallymind.reports.*` (Tasks 3, 6, 7). Gated behind `TALLYMIND_LIVE_E2E=1`, mirroring the existing `TALLYPRIME_LIVE_E2E` convention in `tally-cli/tallyprime/agent-harness/cli_anything/tallyprime/tests/test_full_e2e.py`.

- [ ] **Step 1: Write `tests/test_live_e2e.py`**

```python
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
```

- [ ] **Step 2: Confirm the stub is inert here**

Run: `cd /home/shailesh/cowork/tally-mcp && python3 -m pytest tests/test_live_e2e.py -v`
Expected: 3 skipped (not failed) — confirms the gate works without a live Tally instance.

- [ ] **Step 3: Commit**

```bash
cd /home/shailesh/cowork/tally-mcp
git add tests/test_live_e2e.py
git commit -m "Add gated live-gateway E2E test stub (run on real Windows+Tally, not here)"
```

---

### Task 14: Publish readiness — STOP for explicit user go-ahead before any public push

**Files:**
- Modify: none (verification + a version tag only, no code changes)

**Interfaces:**
- Consumes: the complete repo from Tasks 1-13.

- [ ] **Step 1: Run the complete local test suite one more time**

Run: `cd /home/shailesh/cowork/tally-mcp && python3 -m pytest -v`
Expected: all non-skipped tests pass; the 3 live-E2E tests show as skipped.

- [ ] **Step 2: Review `git log` and `git status` for a clean, reviewable history**

Run: `cd /home/shailesh/cowork/tally-mcp && git log --oneline && git status`
Expected: one commit per task above, nothing uncommitted.

- [ ] **Step 3: STOP — do not run this step without the user's explicit go-ahead in the conversation**

This is the one step in the whole plan that is visible to others and hard to
reverse: creating `Wadhawnaiya/tally-mcp` as a **public** GitHub repository
and pushing this code to it, which is required for the `install.ps1`
one-liner (`irm https://raw.githubusercontent.com/...`) to work per the
approved design spec (§5). Confirm with the user which of these they want
before running anything:
  - Create the repo as **public** now and push (required for the hosted
    one-liner to work as designed), or
  - Create it as **private** for now (installer link won't work for anyone
    but the user until it's later made public), or
  - Hold off entirely and revisit after a manual Windows/Tally test pass.

Only after the user chooses "public, push now" should the following run:

```bash
cd /home/shailesh/cowork/tally-mcp
gh repo create Wadhawnaiya/tally-mcp --public --source=. --remote=origin --push
```

Expected: repo created at `https://github.com/Wadhawnaiya/tally-mcp`, `main`
pushed, `install.ps1` now live at the URL referenced in the README and design
spec.

- [ ] **Step 4: Post-publish smoke check (read-only, safe to run automatically once published)**

Run: `curl -fsSL https://raw.githubusercontent.com/Wadhawnaiya/tally-mcp/main/install.ps1 | head -5`
Expected: the script's first lines print — confirms the URL the README and design spec promise is actually live.
