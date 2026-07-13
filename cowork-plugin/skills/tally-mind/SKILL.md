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
