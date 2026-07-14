# GST ledger naming and ledger-resolution policy

## Resolve before creating — always

Never call `preview_ledger_change` for a ledger without first calling
`list_ledgers(query=<name>)` (and trying at least one alternate spelling —
see below). Every client's chart of accounts already has its own naming
habits; matching those beats introducing a second, slightly different
ledger for the same real-world account. `list_ledgers` fuzzy-matches (e.g.
"VRO" finds "VRO Technology"), so a rough guess at the name is enough to
surface an existing exact name to use instead.

Try more than one query if the first comes back empty. GST ledgers in
particular have several common naming habits across different clients'
books — try the specific form first, then a more generic one:

| Looking for | Try in order |
|---|---|
| Output CGST (sales tax collected) | "CGST Output", "CGST Payable", "Output CGST", "CGST" |
| Output SGST | "SGST Output", "SGST Payable", "Output SGST", "SGST" |
| Output IGST | "IGST Output", "IGST Payable", "Output IGST", "IGST" |
| Input CGST (purchase tax paid) | "CGST Input", "Input CGST", "CGST ITC", "CGST" |
| Input SGST | "SGST Input", "Input SGST", "SGST ITC", "SGST" |
| Input IGST | "IGST Input", "Input IGST", "IGST ITC", "IGST" |

If a plain "CGST"/"SGST"/"IGST" ledger is the only match and the client
evidently uses one ledger per tax type regardless of input/output
direction, use that one ledger for both legs rather than creating a second,
more specific one the client doesn't otherwise use — consistency with the
client's existing books beats textbook correctness here.

## When nothing matches — draft a new ledger

Use `preview_ledger_change(name, parent, opening_balance=0.0, billwise=False)`
with these parent-group conventions:

| New ledger for | `parent` | `billwise` |
|---|---|---|
| A new customer | `"Sundry Debtors"` | `True` |
| A new vendor | `"Sundry Creditors"` | `True` |
| A GST tax ledger (any of the six above) | `"Duties & Taxes"` | `False` |
| A sales/income head | `"Sales Accounts"` | `False` |
| A purchase/cost-of-goods head | `"Purchase Accounts"` | `False` |
| A recurring operating expense (rent, salaries, courier, office supplies) | `"Indirect Expenses"` | `False` |
| An expense directly tied to producing goods/services sold | `"Direct Expenses"` | `False` |
| A bank account | `"Bank Accounts"` | `False` |
| Cash in hand | `"Cash-in-Hand"` | `False` |

Turn on `billwise=True` for new customer/vendor ledgers so Tally tracks
outstanding bills against them individually — this is the standard default
for any real client's Sundry Debtors/Creditors, and it's what
`get_outstanding` (overdue debtors/creditors) reports against later. Note
that `billwise=True` only turns bill-wise *tracking* on for the ledger;
`preview_voucher` itself has no field to say which specific bill a given
Receipt/Payment should knock off, so matching a payment to a particular
invoice inside a bill-wise ledger is still a manual step done in Tally
after the voucher posts.

If an existing ledger for the same real party or tax type already has a
name that doesn't match the table above (e.g. the client calls their bank
ledger "HDFC Bank Current a/c" instead of something generic), that's
expected and fine — the table only governs what to name a *new* ledger, not
what to expect an existing one to be called. Existing ledgers found via
`list_ledgers` always take precedence over inventing a fresh one.

## Reading the tax rate off a document

GST invoices show the tax breakdown directly (CGST %, SGST %, or IGST %,
each with an amount). Use the document's own printed amounts rather than
recomputing from the rate when they're present — printed GST amounts on a
real invoice sometimes differ by a rupee or two from a clean rate × base
calculation due to the vendor's own rounding, and the voucher should match
what the document actually says, not a theoretically "corrected" figure.

If a document shows only a rate and a total (no separate tax line), back
out the taxable value and tax amount from the total: for a GST-inclusive
total `T` at combined rate `r` (e.g. 18% = 0.18), taxable value =
`T / (1 + r)`, and total tax = `T − taxable value`, split evenly between
CGST/SGST for intra-state or booked entirely to IGST for inter-state.
Flag this as an assumption in the batch review table (step 5 in SKILL.md)
so the user can double check it against the source document.

## Determining intra-state vs inter-state

Compare the client company's registered state to the party's state (shown
on the invoice, or inferable from the first two digits of the party's
GSTIN if printed on the document). Same state → CGST + SGST split. Different
states → IGST only. If the state can't be determined from the document,
say so explicitly in the batch review table rather than guessing.
