# Client info — Bright Horizon Traders (demo)

Everything below is fictitious, invented for this demo. No real company,
person, or GSTIN is involved.

- **Company name**: Bright Horizon Traders
- **GSTIN**: 29ABCDE1234F1Z5
- **State**: Karnataka (GST state code 29)
- **Registered address**: 14, MG Road, Bengaluru, Karnataka 560001
- **Financial year**: 2026-27
- **Bank account**: HDFC Bank Current A/c XXXX-4471

## Scenario

Bright Horizon Traders' documents for the first half of July 2026: two
sales invoices, two purchase bills, a credit note, a debit note, one cash
expense receipt, and a bank statement — enough to exercise every voucher
type `tally-doc-import` handles except Journal (a Journal entry is an
accountant's own adjustment, not something a source document produces, so
there's deliberately no document for it here).

One bank statement line (`NEFT-RAJESH KUMAR`, 11-07-2026) doesn't match any
party in these documents on purpose — see `demo/README.md` for why that's
there and what should happen with it.

## Parties in these documents

| Party | Role | State | GSTIN |
|---|---|---|---|
| Emerald Retail Co. | Customer (intra-state) | Karnataka | 29PQRSX5678K1Z2 |
| Vector Traders Pvt Ltd | Customer (inter-state) | Maharashtra | 27LMNOP4321Q1Z9 |
| Silverline Office Supplies | Vendor (intra-state) | Karnataka | 29ZXCVB8765R1Z3 |
| Metro Packaging Ltd | Vendor (inter-state) | Maharashtra | 27ASDFG2468T1Z7 |
| Swift Couriers | Cash expense, unregistered | Karnataka | — (no GST) |

None of these ledgers need to exist in Tally beforehand — drafting them is
part of what this demo exercises.
