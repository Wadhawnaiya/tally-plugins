#!/usr/bin/env python3
"""Convert an .xlsx workbook's sheets to plain-text CSV, stdlib only.

No pandas/openpyxl dependency: .xlsx is a zip of XML parts, so this reads
xl/worksheets/sheetN.xml (+ xl/sharedStrings.xml for text cells) directly.

Usage:
    python xlsx_to_csv.py <path-to-file.xlsx> [sheet_index]

Prints each sheet as CSV to stdout, one "=== Sheet: <name> ===" header per
sheet, so a multi-sheet workbook (e.g. a bank statement with a summary tab
and a transactions tab) is readable in one pass. Pass sheet_index (0-based)
to print only one sheet.

Legacy .xls (pre-2007 binary format) is not covered — it's an OLE compound
file, not a zip, and needs a real parser (xlrd or similar). If handed a
.xls, ask the user to re-save it as .xlsx or .csv from Excel/LibreOffice
first rather than guessing at its binary layout.

This script never reads xl/styles.xml, so it has no idea which cells are
number-formatted. A column that displays as a date or percentage in Excel
prints here as its raw underlying number (a date as a serial like "45852",
not "2025-07-14"; a percentage as "0.18", not "18%"). Treat any
suspicious-looking integer next to a column named "date" as a formatted
value and cross-check it against the source document before trusting it.

Handles both shared-string cells (t="s", the usual case for files saved
from Excel/LibreOffice) and inline-string cells (t="inlineStr", value under
<is><t> rather than a sharedStrings.xml lookup) — openpyxl, a common
Python library for generating .xlsx exports, defaults to inline strings.
"""

from __future__ import annotations

import csv
import re
import sys
import zipfile
from xml.etree import ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _col_to_index(cell_ref: str) -> int:
    """'C7' -> 2 (0-based column index)."""
    letters = re.match(r"[A-Z]+", cell_ref).group()
    index = 0
    for ch in letters:
        index = index * 26 + (ord(ch) - ord("A") + 1)
    return index - 1


def _load_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    strings = []
    for si in root.findall("m:si", NS):
        text = "".join(t.text or "" for t in si.findall(".//m:t", NS))
        strings.append(text)
    return strings


def _load_sheet_names(zf: zipfile.ZipFile) -> list[str]:
    root = ET.fromstring(zf.read("xl/workbook.xml"))
    return [sheet.get("name") for sheet in root.findall(".//m:sheet", NS)]


def _sheet_rows(zf: zipfile.ZipFile, sheet_path: str, shared: list[str]) -> list[list[str]]:
    root = ET.fromstring(zf.read(sheet_path))
    rows: list[list[str]] = []
    for row in root.findall(".//m:sheetData/m:row", NS):
        row_cells: dict[int, str] = {}
        max_col = -1
        for cell in row.findall("m:c", NS):
            ref = cell.get("r", "A1")
            col_idx = _col_to_index(ref)
            max_col = max(max_col, col_idx)
            cell_type = cell.get("t")
            if cell_type == "inlineStr":
                is_el = cell.find("m:is", NS)
                row_cells[col_idx] = (
                    "".join(t.text or "" for t in is_el.findall(".//m:t", NS)) if is_el is not None else ""
                )
                continue
            value_el = cell.find("m:v", NS)
            if value_el is None:
                row_cells[col_idx] = ""
                continue
            raw = value_el.text or ""
            if cell_type == "s":
                row_cells[col_idx] = shared[int(raw)] if raw.isdigit() else ""
            else:
                row_cells[col_idx] = raw
        rows.append([row_cells.get(i, "") for i in range(max_col + 1)])
    return rows


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    path = sys.argv[1]
    only_index = int(sys.argv[2]) if len(sys.argv) > 2 else None

    with zipfile.ZipFile(path) as zf:
        shared = _load_shared_strings(zf)
        sheet_names = _load_sheet_names(zf)
        sheet_paths = sorted(
            name for name in zf.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", name)
        )

        writer = csv.writer(sys.stdout)
        for i, sheet_path in enumerate(sheet_paths):
            if only_index is not None and i != only_index:
                continue
            name = sheet_names[i] if i < len(sheet_names) else sheet_path
            print(f"=== Sheet: {name} ===")
            for row in _sheet_rows(zf, sheet_path, shared):
                writer.writerow(row)
            print()


if __name__ == "__main__":
    main()
