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

"""PDF text layer via poppler pdftotext. Scanned (textless) PDFs are NOT
handled here — they route to OCR (tesseract) per the build plan."""
import shutil
import subprocess


def pdf_to_text(path: str, layout: bool = True) -> str:
    bin_ = shutil.which("pdftotext")
    if not bin_:
        raise RuntimeError("pdftotext not on PATH (apt install poppler-utils)")
    args = [bin_, "-enc", "UTF-8"]
    if layout:
        args.append("-layout")
    args += [path, "-"]
    r = subprocess.run(args, capture_output=True, text=True, timeout=300,
                       check=False)
    if r.returncode != 0:
        raise RuntimeError(f"pdftotext failed: {r.stderr[:200]}")
    return r.stdout
