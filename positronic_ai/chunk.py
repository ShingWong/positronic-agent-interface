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

"""Sentence-aware chunking for embedding. Split on markdown structure
(headings, list items, table rows, paragraphs) then sentences; merge small
units to budget; 1-sentence overlap across seams; subject-context prefix
(counters chunk-context loss: 'approved, ship it Friday' is meaningless
without the thread)."""
import re

_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")
_BLOCK = re.compile(r"(?m)^(#{1,6}\s+.*|[-*]\s+.*|\|.*\||>.*)$")


def _sentences(text: str) -> list[str]:
    parts = [s.strip() for s in _SENT.split(text.strip())]
    return [p for p in parts if p]


def chunk_markdown(md: str, subject: str = "", max_chars: int = 7000,
                   overlap_sents: int = 1) -> list[str]:
    prefix = f"Subject: {subject.strip()}\n" if subject.strip() else ""
    units: list[str] = []
    for para in re.split(r"\n{2,}", md):
        para = para.strip()
        if not para:
            continue
        if _BLOCK.match(para):
            units.append(para)
            continue
        sents = _sentences(para)
        units.extend(sents if sents else [para])
    chunks, cur = [], ""
    for u in units:
        if cur and len(cur) + 2 + len(u) > max_chars:
            chunks.append(cur)
            tail = " ".join(_sentences(cur)[-overlap_sents:]) if overlap_sents else ""
            cur = (tail + " " + u).strip() if tail else u
        else:
            cur = (cur + "  " + u).strip() if cur else u
    if cur:
        chunks.append(cur)
    # pathological: single unit over budget with no sentence end — word cut
    fixed = []
    for c in chunks:
        while len(c) > max_chars * 2:
            cut = c.rfind(" ", 0, max_chars)
            cut = cut if cut > 0 else max_chars
            fixed.append(c[:cut])
            c = c[cut:].strip()
        fixed.append(c)
    return [prefix + c for c in fixed if c.strip()] or ([prefix.strip()] if prefix else [])
