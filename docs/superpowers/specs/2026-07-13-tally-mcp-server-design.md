# TallyMind MCP — Design Spec

Date: 2026-07-13
Author: Claude (Cowork), for CA Shailesh S Wadhawaniya
Status: Approved (see approval note at end)

## 1. Problem

Every existing Tally↔Claude MCP server (surveyed: `dhananjay1405/tally-mcp-server`, `taxor-ai/tally-mcp`,
`CDataSoftware/tally-mcp-server-by-cdata`, `santoshhr76-del/tallymcpserver`, plus the CData commercial
product) shares the same install experience: download a zip, hand-edit `claude_desktop_config.json`
(escaping backslashes by hand on Windows), fully restart Claude Desktop, and hope. Beyond install pain,
they share functional gaps:

1. Connection host is hardcoded to `localhost` (open bug in the most popular project) — breaks the
   moment Tally runs on a different office PC than the one running Claude.
2. No connection-diagnostics tool — failures surface as raw `ECONNREFUSED` or, worse, silently wrong
   data (Tally Educational edition truncates date ranges with no warning).
3. Write operations (create/alter ledgers, post vouchers) have no dry-run/preview/undo — safety is
   "the user remembers to back up Tally first."
4. No GST-specific reporting (GSTR-1/3B), despite GST reconciliation being one of the most common
   Indian CA workloads.
5. Session state (current company, current period) is lost on every server restart.
6. Ledger/party name matching is left to the LLM burning extra tool-calls on fuzzy guessing.

The user (a practicing CA already running a Cowork/Codex CA-tooling stack — see
`tally-cli/tallyprime/agent-harness`, `ca-tally-accounting-automation`, `itr-mcp`) wants a
Tally MCP server that: (a) fixes the above gaps, (b) installs via one pasted command with zero manual
JSON editing, and (c) ships with a polished Word install/usage guide and a jaw-dropping use-case demo,
for use in his own practice and in a course he is building to teach other Indian CAs.

## 2. Goals / Non-goals

**Goals**
- One MCP server, installable by pasting one PowerShell command, that talks to TallyPrime's HTTP/XML
  gateway with no manual config-file editing.
- Fix all six gaps above as concrete, demonstrable features (not just marketing claims).
- Reuse the already-proven XML gateway request/response logic from
  `tally-cli/tallyprime/agent-harness/cli_anything/tallyprime/core/` and
  `utils/tallyprime_backend.py` rather than re-deriving Tally's XML quirks from scratch.
- Follow the existing Cowork plugin convention established by `itr-mcp`
  (`plugin.json` + `skills/` + `mcp_config.json`/`.mcp.json` + Python `FastMCP` server) so it drops
  cleanly into the same course material format as the user's other plugins.
- Ship a stunning `.docx` install/usage guide and a jaw-dropping "instant financial Q&A" use-case demo.

**Non-goals (explicitly out of scope for this iteration)**
- Remote/cloud relay (ngrok/Cloudflare Tunnel/SSH tunnel/Nginx+PM2 setups) for Tally-on-one-machine,
  Claude-on-another scenarios. Documented as a future enhancement, not silently dropped.
- A `.mcpb` Claude Desktop Extension bundle. Python doesn't get Claude Desktop's bundled Node runtime,
  so a `.mcpb` would need to either bundle a Python interpreter or require one to be pre-installed —
  real added complexity for a second install path that duplicates the PowerShell installer's job.
- Simultaneous multi-company querying (Tally itself only exposes the active/open company at a time;
  switching is a first-class `set_company` tool call, not parallel access).
- Any change to Tally's own data model, TDL customizations shipped by the user's Tally installs, etc.

## 3. Architecture

- **Language/runtime**: Python 3.10+, `mcp.server.fastmcp.FastMCP` (same stack as `itr-mcp`, the user's
  existing Cowork MCP plugin convention).
- **Transport**: local stdio, spawned by Claude Desktop (and optionally Claude Code) as a subprocess —
  no long-running server process to manage or expose on the network.
- **Tally connection**: HTTP POST of Tally's `<ENVELOPE>` XML request/response protocol to a
  **configurable** `host:port` (default `localhost:9000`), read from a local JSON config/state file
  (see below) rather than hardcoded — this is the direct fix for gap #1.
- **No dependency on the separately-installed `cli-anything-tallyprime` CLI package.** The proven XML
  construction/parsing logic is ported (copied and adapted) directly into this server's codebase so the
  whole thing is a single `pip install`, removing today's two-separate-installs problem.
- **State persistence**: a small JSON file (e.g. `~/.tallymind/state.json`) storing last-used
  host/port/company/period, so the server doesn't forget context on restart (fixes gap #5). Config
  precedence: explicit tool-call args > env vars > this state file > built-in defaults.

### Repository layout (public repo `Wadhawnaiya/tally-mcp`)
```
tally-mcp/
  install.ps1                  # the one-command installer (§5)
  pyproject.toml / setup.py
  src/tallymind/
    server.py                  # FastMCP app, tool definitions
    gateway.py                 # HTTP/XML request-response client (ported from tally-cli core)
    xml_requests.py            # request envelope builders (ported)
    xml_parse.py               # response parsers (ported)
    diagnostics.py             # tally_doctor implementation
    state.py                   # config/state persistence
    fuzzy.py                   # ledger/party fuzzy name resolution
  tests/
  cowork-plugin/                # Cowork/Codex plugin packaging, mirrors itr-mcp's shape
    plugin.json
    mcp_config.json
    .mcp.json
    skills/tally-mind/SKILL.md
  docs/
    README.md
    superpowers/specs/          # this file
  scripts/
    (any release helpers)
```

## 4. MCP tool surface

Grouped by purpose; every tool returns structured JSON (not raw XML) with a `raw_xml` field available
for debugging.

**Diagnostics (new — fixes gap #2)**
- `tally_doctor()` — checks: is Tally reachable at the configured host:port, is the gateway enabled, is
  a company loaded, is the loaded license the Educational edition (warns explicitly about date-range
  truncation risk), returns a plain-English status plus raw findings.
- `set_connection(host, port)` — explicitly point at a non-default Tally instance (fixes gap #1).
- `set_company(name)` / `list_companies()`.

**Read / reporting**
- `list_ledgers(query=None)` — fuzzy name search built in (fixes gap #6): "VRO" resolves to
  "VRO Technology" without an extra round-trip.
- `get_ledger(name)`, `list_vouchers(...)`, `get_balance_sheet(...)`, `get_profit_and_loss(...)`,
  `get_trial_balance(...)`, `get_day_book(...)`, `get_stock_summary(...)`, `get_outstanding(...)`.

**GST (new — fixes gap #4)**
- `get_gstr1_summary(period)`, `get_gstr3b_summary(period)`, `find_gst_mismatches(period)` —
  reconciliation helper flagging likely mismatches between books and GST returns.

**Guarded write (fixes gap #3)**
- `preview_voucher(...)` / `preview_ledger_change(...)` — always dry-run first: builds the XML,
  returns a plain-English diff of what would change, mutates nothing.
- `confirm_import(preview_id)` — the only tool that actually POSTs an `Import` request to Tally,
  requires a valid `preview_id` from the matching preview call (can't skip straight to a write).
- Mirrors the existing CLI's `--apply --yes` two-step gate, but enforced structurally (no valid
  preview → no write) rather than by convention.

**Escape hatch**
- `raw_gateway_request(xml)` — for anything not covered above, same power as the existing CLI's
  `gateway request`.

## 5. One-command installer (`install.ps1`)

Published at `https://raw.githubusercontent.com/Wadhawnaiya/tally-mcp/main/install.ps1`, run via:
```powershell
irm https://raw.githubusercontent.com/Wadhawnaiya/tally-mcp/main/install.ps1 | iex
```
Steps performed, in order, each with clear console output:
1. Detect Python 3.10+; if missing, install via `winget` (or clearly instruct if winget itself is
   unavailable) rather than failing silently.
2. `pip install` the `tallymind` package (from the GitHub repo directly, e.g.
   `pip install git+https://github.com/Wadhawnaiya/tally-mcp.git`, until/unless it's later published to
   PyPI).
3. Probe `localhost:9000` for a live Tally gateway. If found, use it as the default. If not found,
   prompt once for host/port rather than failing.
4. Locate `claude_desktop_config.json` at the standard Windows path
   (`%APPDATA%\Claude\claude_desktop_config.json`), back up the existing file, and merge in the
   `tallymind` server entry (create the file/structure if absent) — valid JSON merge, not string
   templating, so it can't corrupt an existing config.
5. If the `claude` CLI (Claude Code) is also present, additionally register via `claude mcp add`.
6. Run `tally_doctor` equivalent as a final self-test and print a clear "you're ready" or itemized
   "here's what's still wrong" message.

This is the one visible/hard-to-reverse action in this project: publishing a **public** GitHub repo
under the user's already-authenticated `Wadhawnaiya` account. Implementation will prepare everything
locally first and get explicit confirmation immediately before the first `git push` to a public remote.

## 6. Safety model

- All read tools are unrestricted.
- All write tools require the preview → confirm two-step (§4); `confirm_import` fails closed if the
  preview token is missing, expired, or doesn't match the pending change.
- `tally_doctor` surfaces the Educational-edition warning proactively rather than letting bad data
  reach the model silently.
- README and the Word guide both state plainly: this produces review-ready changes, not a replacement
  for a qualified CA's review before anything is posted for compliance/reporting purposes — same
  professional guardrail already used in `ca-tally-accounting-automation`.

## 7. Deliverables

1. **`tally-mcp` public GitHub repo** (installer + server + tests + README), packaged per §3.
2. **Cowork plugin folder** (`cowork-plugin/`) mirroring the `itr-mcp` convention, for direct use in
   Cowork/Codex and for bundling into the CA course materials.
3. **Stunning Word guide (.docx)** — designed (headings, color, callouts), not a markdown-to-docx dump:
   one-command install → `tally_doctor` verification → a curated set of demo prompts, written for a
   non-technical CA audience, highest-impact content first.
4. **Jaw-dropping use-case demo** — "instant financial Q&A + analysis": a CA asks Claude plain-English
   questions (GST mismatches this quarter, overdue debtors past 90 days, unusual P&L trend) and gets in
   seconds what would take a junior articled clerk hours, including Claude building its own chart/dashboard
   on the fly. Delivered as both a written case study (feeding into the Word guide) and a live HTML
   artifact for presenting to a room.

## 8. Testing approach

- Unit tests for XML request-building and response-parsing (ported logic), independent of a live Tally
  instance — these already exist in `tally-cli`'s `tests/test_core.py` and can be adapted.
- `tests/test_full_e2e.py`-style live-gateway tests, gated behind an env var (mirrors the existing
  `TALLYPRIME_LIVE_E2E=1` convention) since Tally itself only runs on Windows and won't be available in
  this Linux build environment.
- `install.ps1` is Windows-only and cannot be executed in this Linux sandbox; verification here is
  limited to static review, a syntax/lint pass, and — if the user is willing — a manual run on his own
  Tally workstation before or shortly after publishing.

## 9. Open risk explicitly carried forward

Balance Sheet / P&L / Stock Summary / GSTR XML shapes are not publicly documented by Tally — the only
working versions found anywhere are inside the `dhananjay1405` project's source. Where the ported
`tally-cli` logic doesn't already cover a report, this project's XML for that report will be
best-effort, called out clearly in code comments and in the guide, and validated against live Tally
by the user rather than presented as guaranteed-correct on first release.

---

**Approval note**: Design presented to the user in sections (2026-07-13) covering architecture, tool
surface, installer mechanism, safety model, and deliverables; approved as-is ("yes, sounds good to me").
