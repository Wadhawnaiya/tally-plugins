---
name: tally-doc-import
description: This skill should be used when the user wants to turn a client's raw documents — invoices, bank statements, receipts — into TallyPrime vouchers, e.g. "process this client's document folder", "import these invoices into Tally", "draft vouchers from this bank statement". Reads mixed-format documents (PDF, scans, Excel/CSV) and drafts GST-correct vouchers via tally-mind's preview-then-confirm gate.
---

# Tally Document Import

Turn a folder of a client's real paperwork into Tally vouchers. This skill only
drafts and orchestrates — it never talks to Tally directly. All reading,
ledger lookups, and posting go through the `tallymind` MCP server's tools
(the same server the `tally-mind` skill uses), so every write still passes
through the existing preview → confirm gate.

## Prerequisites

Confirm before starting:

- TallyPrime is running on the machine `tallymind` is configured to reach,
  with the client's company loaded.
- A folder path containing that client's documents for the period.

Call `tally_doctor` first. If a company other than the one currently active
is needed, call `set_company(name)` before doing anything else — every
lookup and write below applies to whichever company is active.

## Workflow

### 1. Locate and read the documents

List the folder's contents and group files by extension: PDF, JPG/PNG
(scans/photos), XLSX/XLS/CSV, and anything else.

- Read PDFs and images directly — Claude reads these natively, no OCR step
  needed.
- Read CSV files directly, they're already plain text.
- For XLSX files, run `python scripts/xlsx_to_csv.py <file>` to get a
  plain-text table (the script is dependency-free stdlib, see the script's
  own header for its `.xls` legacy-format limitation). The script has no
  access to cell number-formatting, so any date or percentage column prints
  as a raw underlying number (e.g. a date as `45852`, not `2025-07-14`) —
  treat any suspicious integer-looking column next to words like "date" as
  a formatted value and cross-check it against the source document rather
  than taking it at face value.
- If a file can't be read or classified, don't skip it silently — carry it
  into the final batch summary as "unprocessed" with the reason.

### 2. Classify each document and extract the transaction

For each document, decide what kind of source it is and which Tally voucher
type it maps to (sales invoice, purchase bill, bank payment/receipt line,
expense receipt, credit/debit note, journal adjustment). The full mapping
table with worked examples is in `references/voucher-mapping.md` — consult
it before drafting entries for a document type not already handled in this
session.

Extract, per transaction: date, party name, invoice/reference number, line
items, GST rate and split (CGST/SGST or IGST), total, and a one-line
narration suitable for the voucher's `NARRATION` field.

Normalize the extracted date to ISO `YYYY-MM-DD` immediately — TallyMind's
`preview_voucher` rejects any other format outright. Indian documents are
`DD/MM/YYYY`; never assume US `MM/DD/YYYY` ordering. When the day/month
order is genuinely ambiguous (e.g. `03/04/2026`), don't guess — flag the
ambiguity in the batch review table (step 5) so the user resolves it.

### 3. Resolve ledgers — reuse what exists, draft what's missing

For every ledger name a transaction touches (party, tax, sales/purchase/
expense head, bank/cash), call `list_ledgers(query=name)` first.

- If a fuzzy match comes back, use Tally's exact ledger name from that
  match — never invent a slightly different spelling of an existing ledger.
- If nothing matches, draft a new ledger with `preview_ledger_change`. Parent
  group and naming conventions (which group a new customer, a new GST
  ledger, or a new expense head should go under) are in
  `references/gst-and-ledgers.md`.

### 4. Build voucher entries with the correct sign convention

`preview_voucher`'s `entries` parameter is a list of `[ledger_name,
signed_amount]` pairs that must sum to exactly zero. The convention baked
into TallyMind is:

**Debit is negative, credit is positive.** TallyMind encodes the ordinary
accounting direction as a signed number: a debit leg (an increase in an
asset or expense) is passed as a negative amount; a credit leg (an increase
in a liability, equity, or income) is passed as a positive amount.

Call `preview_voucher(date, voucher_type, number, narration, entries)` for
every transaction, one call per voucher. Use the source document's own
invoice/reference number as `number` when the document has one; pass `""`
to let Tally auto-number when it doesn't.

Worked entry examples for each voucher type are in
`references/voucher-mapping.md` — use them to sanity-check the sign of each
leg before calling `preview_voucher`, especially for GST tax legs.

`preview_voucher` has no field for tying a Receipt/Payment to a specific
outstanding bill — it posts the net ledger effect only. Even against a
bill-wise (`billwise=True`) party ledger, matching the payment to a
specific invoice still has to happen inside Tally afterward; say so in the
batch review table (step 5) whenever a Receipt/Payment is meant to settle a
particular earlier invoice, so the user knows manual bill-matching is still
needed.

### 5. Present one consolidated batch for review — confirm nothing yet

Build a single table covering the whole batch: source file, voucher type,
date, party, amount, GST split, narration, and the `preview_id` returned for
each. List any new-ledger previews needed above the voucher table, since
those must be confirmed first (step 6).

Show this table to the user before calling `confirm_import` on anything.
This is the one required checkpoint in this whole skill — nothing gets
posted without it. If the user asks for a correction, re-run the relevant
`preview_*` call with the fix; the old `preview_id` simply goes unused (each
one is single-use and only takes effect if confirmed).

### 6. Confirm only what's approved, in the right order

- Confirm every approved **ledger** preview first — a voucher referencing a
  ledger that doesn't exist yet in Tally will fail.
- Then confirm every approved **voucher** preview.
- Call `confirm_import(preview_id)` once per approved item. Report back
  per item, not just in aggregate: which posted, and which failed and why —
  a failure on one voucher must never be silently absorbed into an overall
  "done" message.
- Leave anything the user didn't approve un-confirmed; its preview simply
  expires unused.

### 7. Professional guardrail

Same guardrail as `tally-mind`: this produces a review-ready batch, not a
substitute for the client's Chartered Accountant reviewing it before
anything is finalized for compliance or client reporting purposes.

## Additional resources

### Reference files

- **`references/voucher-mapping.md`** — document type → Tally voucher type →
  debit/credit legs, with a worked `entries` example for each of: sales
  invoice, purchase bill, bank payment, bank receipt, expense receipt,
  credit note, debit note.
- **`references/gst-and-ledgers.md`** — GST ledger naming and parent-group
  conventions (Duties & Taxes, Sundry Debtors/Creditors, Sales/Purchase
  Accounts, Direct/Indirect Expenses), and the ledger resolution/creation
  policy in detail.

### Scripts

- **`scripts/xlsx_to_csv.py`** — converts an `.xlsx` file's sheets to
  plain-text CSV using only the Python standard library (no pandas/openpyxl
  dependency). Run it, then read its stdout output like any other text.
