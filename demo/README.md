# Demo: Bright Horizon Traders

A fictitious client's documents for trying out `tally-doc-import` end to
end — from a folder of raw paperwork to vouchers reviewed and posted in
TallyPrime, then checked with `tally-mind`. Nothing in here is real: see
`bright-horizon-traders/client-info.md` for the invented company, parties,
and GSTINs.

## What's in the folder

`bright-horizon-traders/` contains 8 documents covering every voucher type
`tally-doc-import` handles except Journal (a Journal entry comes from an
accountant's own adjustment, not a source document — nothing to demo there):

| File | Document | Expected voucher |
|---|---|---|
| `INV-2026-041.pdf` | Sales invoice, intra-state (Karnataka → Karnataka) | Sales |
| `INV-2026-042.pdf` | Sales invoice, inter-state (Karnataka → Maharashtra) | Sales |
| `SIL-778.pdf` | Purchase bill, intra-state | Purchase |
| `MPL-1190.pdf` | Purchase bill, inter-state | Purchase |
| `CN-2026-005.pdf` | Credit note against INV-2026-041 | Credit Note |
| `DN-2026-002.pdf` | Debit note against MPL-1190 | Debit Note |
| `courier-receipt.png` | Cash expense, no GST (unregistered supplier) | Payment |
| `bank-statement-july-2026.xlsx` | 5 bank lines for 01–13 Jul 2026 | Receipt / Payment / Contra / Payment (see below) |

The bank statement's 5 lines should become:

| Date | Description | Amount | Expected voucher |
|---|---|---|---|
| 04-07-2026 | NEFT FROM EMERALD RETAIL CO INV041 | ₹53,100 credit | Receipt (settles INV-2026-041) |
| 09-07-2026 | NEFT TO SILVERLINE OFFICE SUPPLIES | ₹9,440 debit | Payment (settles SIL-778) |
| 11-07-2026 | NEFT-RAJESH KUMAR | ₹25,000 credit | **Deliberately unmatched — see below** |
| 12-07-2026 | CASH WITHDRAWAL SELF | ₹15,000 debit | Contra (bank → cash) |
| 13-07-2026 | BANK CHARGES QTR JUN-SEP | ₹590 debit | Payment (bank charges expense) |

**The `NEFT-RAJESH KUMAR` line is intentional.** No document here names that
party, and it doesn't match any customer or vendor in the batch. This is
the test for whether the skill does the right thing when it can't resolve
who a transaction belongs to: it should flag this line as unresolved in the
batch review rather than invent a ledger or guess a match. If Claude
quietly drafts a voucher for this line without flagging the ambiguity
first, that's the one thing in this demo that should *not* happen.

## Prerequisites

- TallyPrime running with the gateway enabled (see the main
  [README](../README.md#requirements)), and a company loaded — **use a
  throwaway/test company for this demo**, not a real client's books, since
  it will actually create ledgers and post vouchers.
- The `tally-plugins` cowork-plugin installed in Claude (Desktop, Code, or Cowork),
  with `tallymind` connected (`tally_doctor` should report ready).

## Running the demo

1. Ask Claude, pointing at this folder's absolute path on your machine, e.g.:

   > Using tally-doc-import, process the documents in
   > `demo/bright-horizon-traders` and show me the batch before posting
   > anything.

2. Claude should read all 8 documents (including running
   `scripts/xlsx_to_csv.py` on the bank statement), normalize every date to
   ISO `YYYY-MM-DD`, work out the GST split per document (CGST+SGST for the
   Karnataka↔Karnataka transactions, IGST for the Karnataka↔Maharashtra
   ones), and resolve or draft the ledgers involved. On a fresh company,
   expect new-ledger drafts for: `Emerald Retail Co.`, `Vector Traders Pvt
   Ltd`, `Silverline Office Supplies`, `Metro Packaging Ltd` (all Sundry
   Debtors/Creditors, bill-wise), the bank ledger, `Cash`, `Sales Accounts`,
   `Purchase Accounts`, CGST/SGST/IGST Output and Input ledgers, and
   expense ledgers for courier charges and bank charges.

3. Claude presents one consolidated batch: 10 drafted vouchers (6 from the
   PDFs, 4 from the bank statement), the new-ledger drafts backing them,
   and the `NEFT-RAJESH KUMAR` line called out separately as unresolved —
   not silently included as an 11th voucher.

4. Review the batch. Confirm what looks right; ask for a correction on
   anything that doesn't (e.g. if a GST split or a ledger match looks off)
   before approving.

5. Once approved, Claude confirms every approved ledger preview first,
   then every approved voucher preview, and reports back which posted and
   which (if any) failed — per item, not just a single "done."

6. Check the result with `tally-mind`:

   > Using TallyMind, show me the Day Book for July 2026, and the
   > outstanding balances for Emerald Retail Co. and Vector Traders.

   Emerald Retail Co.'s outstanding balance should reflect the invoice,
   the payment received, and the credit note netting against each other;
   Vector Traders should still show the full invoice outstanding (nothing
   in this demo pays it).

## Regenerating the documents

`generate_demo_docs.py` builds every file in `bright-horizon-traders/`
from scratch (Pillow for the PDFs/image, openpyxl for the spreadsheet).
Re-run it after editing amounts, dates, or parties:

```bash
python3 demo/generate_demo_docs.py
```
