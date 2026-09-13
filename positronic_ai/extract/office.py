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

_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def _docx_paras(data: bytes) -> list[str]:
    root = ET.fromstring(data)
    out = []
    for p in root.findall(".//w:p", _NS):
        t = "".join(n.text or "" for n in p.findall(".//w:t", _NS)).strip()
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
    raise ValueError(f"unsupported office suffix: {path}")
