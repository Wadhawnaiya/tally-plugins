#!/usr/bin/env python3
"""Generate the fictitious demo client's documents for tally-doc-import.

Every name, GSTIN, and amount here is invented for this demo — none of it
is real client data. Regenerate with:

    python3 demo/generate_demo_docs.py

Requires Pillow (image/PDF rendering) and openpyxl (bank statement xlsx).
These are dev-only dependencies for building the demo, not runtime
dependencies of the plugin itself.
"""

from __future__ import annotations

import os

from openpyxl import Workbook
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = os.path.join(os.path.dirname(__file__), "bright-horizon-traders")

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
REGULAR = os.path.join(FONT_DIR, "DejaVuSans.ttf")
BOLD = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")
MONO = os.path.join(FONT_DIR, "DejaVuSansMono.ttf")

PAGE_W, PAGE_H = 1240, 1754  # ~A4 at 150dpi
MARGIN = 90

FICTIONAL_NOTICE = (
    "This is a computer-generated fictitious demo document, created to test the "
    "tally-doc-import Claude skill. No real transaction, company, or person is involved."
)

SELLER = {
    "name": "Bright Horizon Traders",
    "gstin": "29ABCDE1234F1Z5",
    "state": "Karnataka",
    "address": "14, MG Road, Bengaluru, Karnataka 560001",
}
CUSTOMER_INTRA = {
    "name": "Emerald Retail Co.",
    "gstin": "29PQRSX5678K1Z2",
    "state": "Karnataka",
    "address": "22, Residency Road, Bengaluru, Karnataka 560025",
}
CUSTOMER_INTER = {
    "name": "Vector Traders Pvt Ltd",
    "gstin": "27LMNOP4321Q1Z9",
    "state": "Maharashtra",
    "address": "5, Andheri East, Mumbai, Maharashtra 400069",
}
VENDOR_INTRA = {
    "name": "Silverline Office Supplies",
    "gstin": "29ZXCVB8765R1Z3",
    "state": "Karnataka",
    "address": "9, Commercial Street, Bengaluru, Karnataka 560001",
}
VENDOR_INTER = {
    "name": "Metro Packaging Ltd",
    "gstin": "27ASDFG2468T1Z7",
    "state": "Maharashtra",
    "address": "18, MIDC Industrial Area, Pune, Maharashtra 411019",
}


def money(value: float) -> str:
    return f"Rs. {value:,.2f}"


class Sheet:
    """Tiny cursor-based text/table layout on a PIL canvas."""

    def __init__(self) -> None:
        self.img = Image.new("RGB", (PAGE_W, PAGE_H), "white")
        self.draw = ImageDraw.Draw(self.img)
        self.y = MARGIN
        self.font = ImageFont.truetype(REGULAR, 22)
        self.font_bold = ImageFont.truetype(BOLD, 22)
        self.font_small = ImageFont.truetype(REGULAR, 18)
        self.font_title = ImageFont.truetype(BOLD, 36)

    def text(self, s: str, font=None, x=None, gap=32, fill="black") -> None:
        self.draw.text((x if x is not None else MARGIN, self.y), s, font=font or self.font, fill=fill)
        self.y += gap

    def title(self, s: str) -> None:
        self.text(s, font=self.font_title, gap=52)

    def rule(self, gap=20) -> None:
        self.y += 6
        self.draw.line([(MARGIN, self.y), (PAGE_W - MARGIN, self.y)], fill="black", width=2)
        self.y += gap

    def kv_row(self, left: str, right: str) -> None:
        self.draw.text((MARGIN, self.y), left, font=self.font, fill="black")
        self.draw.text((PAGE_W // 2 + 20, self.y), right, font=self.font, fill="black")
        self.y += 32

    def table(self, headers: list[str], col_x: list[int], rows: list[list[str]]) -> None:
        top = self.y
        for h, x in zip(headers, col_x):
            self.draw.text((x, self.y), h, font=self.font_bold, fill="black")
        self.y += 30
        self.draw.line([(MARGIN, self.y), (PAGE_W - MARGIN, self.y)], fill="black", width=2)
        self.y += 14
        for row in rows:
            for cell, x in zip(row, col_x):
                self.draw.text((x, self.y), cell, font=self.font, fill="black")
            self.y += 34
        self.draw.line([(MARGIN, self.y), (PAGE_W - MARGIN, self.y)], fill="black", width=1)
        self.y += 20
        self.draw.rectangle([(MARGIN - 10, top - 10), (PAGE_W - MARGIN + 10, self.y)], outline="black", width=2)

    def footer_notice(self) -> None:
        self.draw.text(
            (MARGIN, PAGE_H - 70), FICTIONAL_NOTICE, font=self.font_small, fill=(120, 120, 120)
        )

    def save_pdf(self, path: str) -> None:
        self.img.save(path, "PDF", resolution=150.0)


def party_block(sheet: Sheet, label: str, party: dict) -> None:
    sheet.text(label, font=sheet.font_bold, gap=30)
    sheet.text(party["name"], gap=28)
    sheet.text(party["address"], gap=28)
    sheet.text(f"GSTIN: {party['gstin']}  |  State: {party['state']}", gap=36)


def render_tax_invoice(
    path: str,
    doc_label: str,
    number: str,
    date: str,
    seller: dict,
    buyer: dict,
    items: list[tuple[str, str, str]],
    taxable_value: float,
    cgst: float | None,
    sgst: float | None,
    igst: float | None,
    total: float,
) -> None:
    sh = Sheet()
    sh.title(doc_label)
    sh.kv_row(f"No: {number}", f"Date: {date}")
    sh.rule()
    party_block(sh, "Seller", seller)
    sh.y += 10
    party_block(sh, "Buyer", buyer)
    sh.y += 20

    col_x = [MARGIN, MARGIN + 620, MARGIN + 820]
    rows = [[desc, qty, amt] for desc, qty, amt in items]
    sh.table(["Description", "Qty", "Amount"], col_x, rows)
    sh.y += 10

    sh.kv_row("Taxable Value", money(taxable_value))
    if cgst is not None:
        sh.kv_row(f"CGST @ 9%", money(cgst))
        sh.kv_row(f"SGST @ 9%", money(sgst))
    if igst is not None:
        sh.kv_row(f"IGST @ 18%", money(igst))
    sh.text(f"Grand Total: {money(total)}", font=sh.font_bold, gap=40)

    sh.footer_notice()
    sh.save_pdf(path)


def render_note(
    path: str,
    doc_label: str,
    number: str,
    date: str,
    issuer: dict,
    counterparty: dict,
    against_doc: str,
    reason: str,
    taxable_value: float,
    cgst: float | None,
    sgst: float | None,
    igst: float | None,
    total: float,
) -> None:
    sh = Sheet()
    sh.title(doc_label)
    sh.kv_row(f"No: {number}", f"Date: {date}")
    sh.text(f"Against: {against_doc}", gap=36)
    sh.rule()
    party_block(sh, "Issued by", issuer)
    sh.y += 10
    party_block(sh, "Issued to", counterparty)
    sh.y += 10
    sh.text(f"Reason: {reason}", gap=40)

    sh.kv_row("Taxable Value (reduction)", money(taxable_value))
    if cgst is not None:
        sh.kv_row("CGST @ 9%", money(cgst))
        sh.kv_row("SGST @ 9%", money(sgst))
    if igst is not None:
        sh.kv_row("IGST @ 18%", money(igst))
    sh.text(f"Total: {money(total)}", font=sh.font_bold, gap=40)

    sh.footer_notice()
    sh.save_pdf(path)


def render_cash_receipt(path: str) -> None:
    """A small, slightly-off-center 'photographed' cash receipt (no GST)."""
    img = Image.new("RGB", (700, 900), (245, 245, 240))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(MONO, 22)
    font_bold = ImageFont.truetype(BOLD, 26)

    x, y = 60, 60
    draw.text((x, y), "SWIFT COURIERS", font=font_bold, fill="black")
    y += 40
    draw.text((x, y), "Speed Post & Local Delivery", font=font, fill="black")
    y += 30
    draw.text((x, y), "Shop 4, Cross Rd, Bengaluru", font=font, fill="black")
    y += 50
    draw.line([(x, y), (640, y)], fill="black", width=2)
    y += 30
    draw.text((x, y), "CASH RECEIPT", font=font_bold, fill="black")
    y += 40
    draw.text((x, y), "Date: 06-07-2026", font=font, fill="black")
    y += 34
    draw.text((x, y), "Receipt No: SC-2291", font=font, fill="black")
    y += 34
    draw.text((x, y), "Received from: Bright Horizon Traders", font=font, fill="black")
    y += 50
    draw.text((x, y), "Speed Post charges - 3 parcels", font=font, fill="black")
    y += 40
    draw.text((x, y), "Amount Paid: Rs. 450.00", font=font_bold, fill="black")
    y += 60
    draw.line([(x, y), (640, y)], fill="black", width=1)
    y += 30
    draw.text((x, y), "(No GST - unregistered supplier)", font=font, fill=(90, 90, 90))
    y += 60
    draw.text((x, y), "Thank you!", font=font, fill="black")

    img = img.rotate(-1.5, fillcolor=(245, 245, 240), expand=False)

    draw2 = ImageDraw.Draw(img)
    small = ImageFont.truetype(REGULAR, 14)
    draw2.text((20, 860), FICTIONAL_NOTICE[:70], font=small, fill=(150, 150, 150))
    img.save(path)


def build_bank_statement(path: str) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "July2026"

    ws.append(["Bright Horizon Traders - HDFC Bank Current A/c XXXX-4471"])
    ws.append(["Statement period: 01-Jul-2026 to 13-Jul-2026"])
    ws.append([])
    ws.append(["Date", "Description", "Debit", "Credit", "Balance"])

    rows = [
        ("04-07-2026", "NEFT FROM EMERALD RETAIL CO INV041", "", 53100.00, 812450.00),
        ("09-07-2026", "NEFT TO SILVERLINE OFFICE SUPPLIES", 9440.00, "", 803010.00),
        ("11-07-2026", "NEFT-RAJESH KUMAR", "", 25000.00, 828010.00),
        ("12-07-2026", "CASH WITHDRAWAL SELF", 15000.00, "", 813010.00),
        ("13-07-2026", "BANK CHARGES QTR JUN-SEP", 590.00, "", 812420.00),
    ]
    for row in rows:
        ws.append(list(row))

    ws.append([])
    ws.append([FICTIONAL_NOTICE])

    for col, width in zip("ABCDE", (16, 40, 14, 14, 14)):
        ws.column_dimensions[col].width = width

    wb.save(path)


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

    render_tax_invoice(
        os.path.join(OUT_DIR, "INV-2026-041.pdf"),
        "TAX INVOICE", "INV-2026-041", "02-07-2026",
        SELLER, CUSTOMER_INTRA,
        items=[("Consulting Services - June 2026", "1", "45,000.00")],
        taxable_value=45000.00, cgst=4050.00, sgst=4050.00, igst=None, total=53100.00,
    )

    render_tax_invoice(
        os.path.join(OUT_DIR, "INV-2026-042.pdf"),
        "TAX INVOICE", "INV-2026-042", "05-07-2026",
        SELLER, CUSTOMER_INTER,
        items=[("Software Implementation Services", "1", "60,000.00")],
        taxable_value=60000.00, cgst=None, sgst=None, igst=10800.00, total=70800.00,
    )

    render_tax_invoice(
        os.path.join(OUT_DIR, "SIL-778.pdf"),
        "TAX INVOICE", "SIL-778", "03-07-2026",
        VENDOR_INTRA, SELLER,
        items=[("Office stationery & printer supplies", "1", "8,000.00")],
        taxable_value=8000.00, cgst=720.00, sgst=720.00, igst=None, total=9440.00,
    )

    render_tax_invoice(
        os.path.join(OUT_DIR, "MPL-1190.pdf"),
        "TAX INVOICE", "MPL-1190", "08-07-2026",
        VENDOR_INTER, SELLER,
        items=[("Packaging materials - corrugated boxes", "1", "15,000.00")],
        taxable_value=15000.00, cgst=None, sgst=None, igst=2700.00, total=17700.00,
    )

    render_note(
        os.path.join(OUT_DIR, "CN-2026-005.pdf"),
        "CREDIT NOTE", "CN-2026-005", "10-07-2026",
        issuer=SELLER, counterparty=CUSTOMER_INTRA,
        against_doc="Invoice INV-2026-041 dated 02-07-2026",
        reason="Billing correction - service scope reduced",
        taxable_value=5000.00, cgst=450.00, sgst=450.00, igst=None, total=5900.00,
    )

    render_note(
        os.path.join(OUT_DIR, "DN-2026-002.pdf"),
        "DEBIT NOTE", "DN-2026-002", "13-07-2026",
        issuer=SELLER, counterparty=VENDOR_INTER,
        against_doc="Bill MPL-1190 dated 08-07-2026",
        reason="Damaged packaging materials returned to vendor",
        taxable_value=3000.00, cgst=None, sgst=None, igst=540.00, total=3540.00,
    )

    render_cash_receipt(os.path.join(OUT_DIR, "courier-receipt.png"))
    build_bank_statement(os.path.join(OUT_DIR, "bank-statement-july-2026.xlsx"))

    print(f"Generated demo documents in {OUT_DIR}")


if __name__ == "__main__":
    main()
