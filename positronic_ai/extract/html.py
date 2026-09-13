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

"""HTML -> markdown via system html2text. Markdown is the canonical
intermediate: one chunker serves HTML and md inputs."""
import shutil
import subprocess


def _bin() -> str:
    p = shutil.which("html2text")
    if not p:
        raise RuntimeError("html2text not on PATH (apt install html2text)")
    return p


def html_to_markdown(html: str) -> str:
    r = subprocess.run([_bin(), "-nobs"], input=html, capture_output=True,
                       text=True, timeout=60, check=False)
    if r.returncode != 0:
        raise RuntimeError(f"html2text failed: {r.stderr[:200]}")
    return r.stdout
