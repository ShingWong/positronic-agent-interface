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

"""HTML -> plain text via pandoc. Plain text is the canonical
intermediate: one chunker serves HTML and md inputs.

Replaced html2text (v0.2): the C++ binary segfaults (munmap_chunk) on
large marketing HTML, and its markdown-table output confused the table
detector. Pandoc's plain writer flattens layout tables into aligned
columns with values intact (verified: Priceline itinerary keeps flights,
$304.86 totals; 107KB HTML -> 59KB clean text)."""
import shutil
import subprocess


def _bin() -> str:
    p = shutil.which("pandoc")
    if not p:
        raise RuntimeError("pandoc not on PATH (apt install pandoc)")
    return p


def html_to_markdown(html: str) -> str:
    r = subprocess.run([_bin(), "-f", "html", "-t", "plain", "--wrap=none"],
                       input=html, capture_output=True,
                       text=True, timeout=120, check=False)
    if r.returncode != 0:
        raise RuntimeError(f"pandoc failed: {r.stderr[:200]}")
    return r.stdout
