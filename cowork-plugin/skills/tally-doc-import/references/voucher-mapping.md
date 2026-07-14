# Document type → Tally voucher mapping

Every example uses the sign convention `preview_voucher` expects: **debit is
negative, credit is positive**, entries in a voucher must sum to zero. Ledger
names below are placeholders — always resolve the client's actual ledger name
via `list_ledgers` first (see `gst-and-ledgers.md`), then substitute it in.

Amounts in examples are illustrative; always compute the real split from the
document (e.g. GST amount = taxable value × rate, split evenly between CGST
and SGST for an intra-state supply, or booked entirely to IGST for
inter-state).

## Sales invoice → `Sales` voucher

The client sold something; the customer owes money; GST collected is a
liability until remitted.

Document: an invoice raised to a customer for ₹10,000 + 9% CGST + 9% SGST
(intra-state).

```
voucher_type = "Sales"
entries = [
  ["<Customer ledger>", -11800.0],   # debit — debtor now owes more
  ["Sales Accounts",     10000.0],   # credit — income
  ["CGST Output",          900.0],  # credit — tax liability
  ["SGST Output",          900.0],  # credit — tax liability
]
```

## Purchase bill → `Purchase` voucher

The client bought something; the vendor is owed money; GST paid is
recoverable (an asset) via input credit.

Document: a vendor's bill for ₹5,000 + 18% IGST (inter-state).

```
voucher_type = "Purchase"
entries = [
  ["Purchase Accounts", -5000.0],   # debit — expense/asset acquired
  ["IGST Input",         -900.0],   # debit — recoverable tax asset
  ["<Vendor ledger>",    5900.0],   # credit — creditor now owed
]
```

## Bank statement — money going out → `Payment` voucher

Document: a bank statement line showing ₹2,500 debited from the account for
an office-supplies purchase paid directly (no separate purchase bill, or the
bill is booked separately and this is just the settlement).

```
voucher_type = "Payment"
entries = [
  ["Office Expenses", -2500.0],   # debit — expense incurred
  ["<Bank ledger>",    2500.0],   # credit — asset (bank balance) decreases
]
```

If the payment settles an existing vendor bill instead of a fresh expense,
debit the vendor/creditor ledger instead of an expense ledger:

```
entries = [
  ["<Vendor ledger>", -2500.0],
  ["<Bank ledger>",    2500.0],
]
```

Note: this reduces the vendor ledger's overall balance but does not tell
Tally which specific bill it's against — `preview_voucher` has no
bill-reference field. If the vendor ledger is bill-wise, knock this payment
off against the right bill manually inside Tally afterward.

## Bank statement — money coming in → `Receipt` voucher

Document: a bank statement line showing ₹11,800 credited, from a customer
who has more than one outstanding invoice.

```
voucher_type = "Receipt"
entries = [
  ["<Bank ledger>",     -11800.0],  # debit — asset (bank balance) increases
  ["<Customer ledger>",  11800.0],  # credit — debtor balance reduced
]
```

This reduces the customer's overall outstanding balance but does not
specify *which* invoice it settles — same limitation as above. Flag in the
batch review table which invoice the payment is believed to match, so the
user (or the client's CA) can apply that bill allocation inside Tally.

## Expense receipt (cash) → `Payment` voucher

Document: a cash receipt for ₹500 of courier charges, no bank/bill involved.

```
voucher_type = "Payment"
entries = [
  ["Courier Charges", -500.0],
  ["Cash",              500.0],
]
```

## Credit note (sales return / reduction) → `Credit Note` voucher

Document: a credit note reducing an earlier sale by ₹1,000 (indicative,
before tax) plus proportional GST reversal.

```
voucher_type = "Credit Note"
entries = [
  ["Sales Accounts",  -1000.0],   # debit — income reversed
  ["CGST Output",       -90.0],   # debit — tax liability reversed
  ["SGST Output",       -90.0],
  ["<Customer ledger>", 1180.0],  # credit — debtor owes less
]
```

## Debit note (purchase return / reduction) → `Debit Note` voucher

Document: a debit note reducing an earlier purchase by ₹800 (indicative)
plus proportional GST reversal, inter-state.

```
voucher_type = "Debit Note"
entries = [
  ["<Vendor ledger>",  -944.0],   # debit — creditor owed less
  ["Purchase Accounts", 800.0],   # credit — expense/asset reversed
  ["IGST Input",         144.0],  # credit — input credit reversed
]
```

## Transfer between own accounts (bank ↔ cash, bank ↔ bank) → `Contra` voucher

Document: a bank statement line showing a ₹5,000 cash withdrawal.

```
voucher_type = "Contra"
entries = [
  ["Cash",           -5000.0],   # debit — cash in hand increases
  ["<Bank ledger>",   5000.0],   # credit — bank balance decreases
]
```

## Adjustment with no cash/bank/party movement → `Journal` voucher

Document: an accountant's note to reclassify an expense already booked to
the wrong head, ₹300.

```
voucher_type = "Journal"
entries = [
  ["Correct Expense Head", -300.0],
  ["Wrong Expense Head",    300.0],
]
```

## Sanity checks before calling `preview_voucher`

- Entries sum to exactly `0.0` (float rounding to 2 decimals is fine; a
  running total that isn't zero means a leg was mis-signed or a GST split
  was computed wrong — recheck before previewing).
- Every ledger name in `entries` matches what `list_ledgers` returned, not a
  freehand guess.
- GST split direction: **Output** tax ledgers (collected from customers) sit
  on the credit side of a Sales voucher and the debit side of its Credit
  Note; **Input** tax ledgers (paid to vendors) sit on the debit side of a
  Purchase voucher and the credit side of its Debit Note.
