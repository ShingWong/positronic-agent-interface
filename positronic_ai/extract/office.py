# =====================================================================
# Project Positronic — Polytemporal Cognitive Engram Memory Substrate
# Copyright (C) 2026 Shing Wong. All Rights Reserved.
# =====================================================================
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://gnu.org>.
# =====================================================================

"""Office formats -> markdown. Stdlib first (docx/xlsx/odt/ods are ZIPs of
XML: full structural control for the chunker, zero deps). Pandoc fallback
for files stdlib chokes on (Word numbering/footnotes/tracked-changes soup).
"""
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile

_NS_W = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
_NS_F = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
_NS_T = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
_NSS = {"t": _NS_F, "tab": _NS_T}


def _docx_paras(data: bytes) -> list[str]:
    root = ET.fromstring(data)
    out = []
    for p in root.findall(".//w:p", _NS_W):
        t = "".join(n.text or "" for n in p.findall(".//w:t", _NS_W)).strip()
        if t:
            out.append(t)
    return out


def _odt_rows(xml: bytes) -> list[str]:
    root = ET.fromstring(xml)
    out = []
    for table in root.findall(".//tab:table", _NSS):
        for row in table.findall("tab:table-row", _NSS):
            cells = []
            for cell in row.findall("tab:table-cell", _NSS):
                text = " ".join("".join(p.itertext()) for p in cell.findall(".//t:p", _NSS)
                                if "".join(p.itertext()))
                cells.append(text.strip())
            if any(c.strip() for c in cells):
                out.append(" | ".join(cells))
    if out:
        return out
    for p in root.findall(".//t:p", _NSS):
        t = "".join(p.itertext()).strip()
        if t:
            out.append(t)
    return out


def _pandoc(path: str) -> str:
    bin_ = shutil.which("pandoc")
    if not bin_:
        raise RuntimeError("pandoc not on PATH and stdlib parse failed")
    r = subprocess.run([bin_, "-f", "docx", "-t", "markdown", path],
                       capture_output=True, text=True, timeout=300,
                       check=False)
    if r.returncode != 0:
        raise RuntimeError(f"pandoc failed: {r.stderr[:200]}")
    return r.stdout


def office_to_markdown(path: str) -> str:
    low = path.lower()
    if low.endswith(".docx"):
        try:
            with zipfile.ZipFile(path) as z:
                paras = _docx_paras(z.read("word/document.xml"))
            return "\n\n".join(paras) + "\n"
        except (zipfile.BadZipFile, KeyError, ET.ParseError):
            return _pandoc(path)
    if low.endswith(".xlsx"):
        try:
            import openpyxl as _ox
        except ImportError:
            raise RuntimeError("openpyxl required for xlsx "
                               "(pip install openpyxl)")
        wb = _ox.load_workbook(path, read_only=True, data_only=True)
        blocks = []
        for ws in wb.worksheets:
            rows = []
            for row in ws.iter_rows(values_only=True):
                cells = ["" if v is None else str(v) for v in row]
                if any(c.strip() for c in cells):
                    rows.append(" | ".join(cells))
            if rows:
                blocks.append("\n".join(rows))
        wb.close()
        if not blocks:
            return ""
        return "\n\n".join(blocks) + "\n"
    if low.endswith((".odt", ".ods")):
        try:
            with zipfile.ZipFile(path) as z:
                xml = z.read("content.xml")
            paras = _odt_rows(xml)
            return "\n\n".join(paras) + "\n" if paras else ""
        except (zipfile.BadZipFile, KeyError, ET.ParseError):
            return _pandoc(path)
    raise ValueError(f"unsupported office suffix: {path}")
