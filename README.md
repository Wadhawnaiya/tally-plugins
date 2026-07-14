# TallyMind MCP

**Talk to your TallyPrime books in plain English, from Claude.**

TallyMind is a free, open-source [MCP](https://modelcontextprotocol.io) server that connects
Claude to a local TallyPrime installation. Ask questions, pull reports, check GST returns, turn a
client's invoices and bank statements into vouchers, and (with your explicit confirmation, every
time) post entries — all in conversation, with nothing installed by hand and nothing sent
anywhere except your own computer and Tally.

```powershell
irm https://raw.githubusercontent.com/Wadhawnaiya/tally-mcp/main/install.ps1 | iex
```

That one line is the entire install. No zip files, no editing config JSON by hand, no guessing
paths. Paste it into PowerShell, press Enter, and follow along — details below.

---

## Contents

- [Why this exists](#why-this-exists)
- [What makes TallyMind different](#what-makes-tallymind-different)
- [What data it can see and touch inside Tally](#what-data-it-can-see-and-touch-inside-tally)
- [What you can ask it to do](#what-you-can-ask-it-to-do)
- [Importing a client's documents](#importing-a-clients-documents)
- [Requirements](#requirements)
- [Install](#install)
- [Check it's working](#check-its-working)
- [Example things to ask](#example-things-to-ask)
- [How the safety model works](#how-the-safety-model-works)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [License](#license)

---

## Why this exists

TallyPrime doesn't talk to AI assistants on its own. A handful of open-source "Tally MCP
servers" already exist to bridge the two, but every one we could find shares the same rough
edges: a Tally connection hardcoded to `localhost` (so it breaks the moment Tally runs on a
different office PC), no way to tell *why* a connection failed, no safety net before something
gets written into your books, nothing built for GST work specifically, session settings that
reset every time the server restarts, and — worst of all for a non-developer — an install
process that means downloading a zip file and hand-editing a JSON config file, backslash
escaping and all.

TallyMind fixes all of that, and is free for anyone to use, fork, or build on.

## What makes TallyMind different

| | Most existing Tally MCP servers | TallyMind |
|---|---|---|
| **Install** | Download a zip, manually edit `claude_desktop_config.json`, restart Claude | One PowerShell command does everything |
| **Connecting to Tally on another PC** | Hardcoded to `localhost` — breaks if Tally is on a different machine | Host and port are configurable (`set_connection`) |
| **When something's wrong** | A raw connection error, or silently wrong data | `tally_doctor` tells you plainly what's broken and how to fix it |
| **Posting entries** | Often "just does it," or leaves safety entirely up to you remembering to back up first | Every write is preview-first: nothing touches Tally until you explicitly confirm |
| **GST work** | Not covered | Dedicated GSTR-1/GSTR-3B and mismatch-review tools |
| **Restarting the server** | Forgets which company/connection you were using | Remembers your last connection and company automatically |
| **Finding a ledger by a rough name** | You have to know the exact spelling | Fuzzy search — "VRO" finds "VRO Technology" |

## What data it can see and touch inside Tally

This matters more than almost anything else in this document, so it gets its own section.

- **TallyMind only ever talks to the TallyPrime instance you point it at**, over TallyPrime's own
  built-in HTTP/XML interface (the same interface Tally's official developer tools use). By
  default that's `localhost:9000` — your own computer, nothing external.
- **Nothing about your Tally data is sent anywhere except to the Claude conversation you're
  having.** There is no cloud relay, no third-party server, no telemetry. TallyMind is a small
  program that runs entirely on your machine.
- **Read access**: whatever company is currently open/loaded in TallyPrime — its ledgers,
  vouchers, Balance Sheet, Profit & Loss, Trial Balance, Day Book, Stock Summary, outstanding
  bills, and (best-effort — see below) GST return data. It cannot see companies you haven't
  opened, and it cannot see anything Tally itself wouldn't show to whatever user account Tally is
  running as.
- **Write access is real but gated.** TallyMind *can* create/alter ledgers and post vouchers —
  but never in one step. Every write is a two-stage **preview, then confirm**: the preview builds
  the exact change and shows it to you first, and nothing is sent to Tally until you (or Claude,
  on your explicit instruction) call confirm with that specific preview. There is no tool that
  mutates Tally data in a single call.
- **GST reporting is honestly best-effort.** TallyPrime doesn't publicly document the exact data
  format its GST reports return over this interface, so TallyMind's GST tools are marked
  `best_effort` in their own output and come with a note to cross-check against Tally's own GST
  screens — TallyMind will not pretend to a level of certainty it doesn't have.
- **You control the scope.** `set_connection` and `set_company` let you point TallyMind at exactly
  the Tally instance and company you intend — nothing happens automatically in the background.

## What you can ask it to do

TallyMind exposes 20 tools to Claude, grouped here by what they're for. You don't need to know
these names — just ask in plain English and Claude picks the right one — but they're listed for
anyone who wants the full picture.

**Check the connection**
- `tally_doctor` — is Tally reachable, is a company loaded, plus an honest reminder to confirm
  you're not on the Educational edition (which silently truncates date ranges).
- `set_connection` — point at a specific Tally host/port instead of the default `localhost:9000`.
- `set_company` — set which company subsequent questions apply to.

**Read your books**
- `list_companies`, `list_ledgers` (with fuzzy name search), `get_ledger`, `list_vouchers`
- `get_balance_sheet`, `get_profit_and_loss`, `get_trial_balance`, `get_day_book`,
  `get_stock_summary`, `get_outstanding` (overdue receivables/payables)

**GST**
- `get_gstr1_summary`, `get_gstr3b_summary` — best-effort GSTR summaries for a period
- `find_gst_mismatches` — pulls the GST return summary and the Day Book for the same period side
  by side, so a CA can spot-check them together, rather than fabricating a false-confidence
  "mismatches found" count Tally's data doesn't reliably support yet

**Make changes (always preview first)**
- `preview_ledger_change` / `preview_voucher` — build the exact change, return a preview ID,
  touch nothing
- `confirm_import` — the only tool that actually writes to Tally, and only with a valid preview ID

**Escape hatch**
- `raw_gateway_request` — send a raw XML request directly, for anything the above doesn't cover

## Importing a client's documents

Alongside `tally-mind`, this plugin ships a second skill, `tally-doc-import`,
for turning a client's actual paperwork into vouchers instead of drafting
them by hand one at a time.

Point it at a folder of a client's documents for a period — invoices,
purchase bills, bank statements, expense receipts, credit/debit notes, in
whatever mix of PDF, scanned image, or Excel/CSV they happen to arrive in —
and ask Claude to process it. It reads every document, works out what kind
of transaction each one is, splits out GST correctly (CGST/SGST or IGST,
matched to the client's actual tax ledgers), and drafts any ledgers that
don't exist yet.

It uses exactly the same guarded write path as everything else in this
document: nothing is posted to Tally until every drafted voucher and ledger
has been shown to you in one consolidated batch and you've explicitly
approved it. Nothing new to trust here beyond `preview_*` → `confirm_import`
— this skill just does the drafting work that used to be manual.

See `cowork-plugin/skills/tally-doc-import/SKILL.md` for the full workflow,
and its `references/` for the voucher-type mapping and GST ledger
conventions it follows.

## Requirements

- **TallyPrime, Silver or Gold edition** — not the Educational edition, which silently truncates
  date ranges and will feed Claude plausible-looking but wrong numbers.
- Tally's HTTP/XML gateway enabled: in TallyPrime, go to **F1 (Help) → Settings → Connectivity →
  Client/Server configuration**, set "TallyPrime acts as" to **Server** (or **Both**), and note
  the port (default `9000`).
- **Windows**, since TallyPrime itself only runs on Windows.
- **Claude Desktop** and/or **Claude Code**, installed on the same PC as TallyPrime.

## Install

Open TallyPrime, load your company, and make sure the gateway setting above is on. Then open
**PowerShell** and run:

```powershell
irm https://raw.githubusercontent.com/Wadhawnaiya/tally-mcp/main/install.ps1 | iex
```

Here's exactly what that one line does, step by step, so nothing is a mystery:

1. **Checks for Python 3.10+.** If it's missing, installs it automatically via `winget`.
2. **Installs TallyMind itself** (`pip install`, straight from this repository).
3. **Looks for your running Tally gateway** at `localhost:9000`. If it doesn't find one, it asks
   you once for the right port rather than failing silently.
4. **Registers TallyMind with Claude Desktop** by safely reading and rewriting
   `claude_desktop_config.json` — your existing config is backed up first, and the file is only
   ever edited through proper JSON parsing, never by pasting text into it, so it can't get
   corrupted the way hand-editing sometimes does.
5. **Registers with Claude Code too**, if you have it installed.
6. **Runs a connection self-test** and tells you plainly whether everything is ready.

When it finishes, **fully quit Claude Desktop** (from the system tray, not just closing the
window) and reopen it, so it picks up the new server.

## Check it's working

Ask Claude:

> Using TallyMind, run tally_doctor and tell me if I'm connected.

You should get back a plain-language status: whether Tally is reachable, whether a company is
loaded, and a reminder about the Educational-edition caveat above.

## Example things to ask

- "Using TallyMind, what's my Trial Balance look like right now?"
- "Which ledgers have unusually large closing balances?"
- "Show me overdue debtors past 90 days."
- "Pull the GSTR-1 and GSTR-3B summary for April 2026 and the Day Book for the same period so I
  can compare them."
- "Preview a sales voucher dated today for ₹10,000 against VRO Technology, then show me the
  preview before you touch anything."
- "Process the invoices and bank statement in C:\Clients\VRO Technology\July, then show me the
  batch before posting anything."

## How the safety model works

Every tool that only *reads* data runs freely — there's nothing to protect there. Every tool that
*writes* data works in two separate steps:

1. **Preview** (`preview_ledger_change` or `preview_voucher`) builds the exact XML that would be
   sent to Tally and hands you back a `preview_id`. Nothing has touched Tally yet.
2. **Confirm** (`confirm_import`) is the only tool that actually posts to Tally, and it requires
   that exact `preview_id`. A preview can only ever be confirmed once — replaying an old or
   invalid ID fails rather than silently reposting.

Nothing in TallyMind will ever post a change without both of these steps happening, in order,
with your visibility into the preview in between. As always with accounting software: this
produces a review-ready change, not a replacement for a qualified professional's review before
anything is finalized for compliance or client reporting purposes.

## Troubleshooting

**"TallyPrime XML gateway unavailable"** — Open TallyPrime, load a company, and confirm
**F1 → Settings → Connectivity → Client/Server** is set to Server or Both with the right port.
Run `tally_doctor` again after fixing this.

**Claude doesn't see the TallyMind tools at all** — Make sure you fully quit and reopened Claude
Desktop after installing (a window close isn't enough — quit from the system tray).

**Installer says Python or winget isn't available** — Install Python 3.10+ manually from
[python.org](https://python.org), then re-run the install command.

## Development

```bash
pip install -e ".[dev]"
pytest
```

`install.ps1` is Windows-only and can't be exercised in a Linux dev environment — review it
manually and test it on a real Windows + TallyPrime machine before trusting changes to it.

## License

[MIT](LICENSE) — free for anyone to use, modify, and distribute, commercially or otherwise.
