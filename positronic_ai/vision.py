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

"""Table-text routing to a vision-capable LLM (Qwen variant on :8080).

bge-m3 embeds table text poorly (rows/columns collapse into noise), while a
large Qwen restructures tables well but is slow. So: detect table structure,
send only table chunks to the vision endpoint for restructuring, keep
everything else on the fast bge path.

Failover mirrors embed.py: one URL or a list, tried in order.
Config key is `vision_url` (same redundancy syntax as `local_url`):

    positronic config vision_url "http://127.0.0.1:8080, http://192.168.4.20:8081"
"""
import json
import re
import urllib.error
import urllib.request

DEFAULT_VISION_URL = "http://127.0.0.1:8080"

_TABLE_PROMPT = (
    "Restructure the following table text into clean markdown. "
    "Preserve every row, column, header, and numeric value exactly. "
    "Do not summarize, omit, or invent data. Output only the table.\n\n"
)


def _as_url_list(url) -> list[str]:
    """Accept one URL or a list; split strings on comma/space (same as embed)."""
    if isinstance(url, (list, tuple)):
        return [str(u).strip() for u in url if str(u).strip()]
    return [u for u in str(url).replace(",", " ").split() if u]


_HDR_RE = re.compile(
    r"^(Received|Authentication-Results|X-[\w-]+|Return-Path|DKIM-Signature|"
    r"ARC-|Message-ID|From|To|Cc|Date|Subject|MIME-|Content-|smtp\.|cipher=):?",
    re.IGNORECASE)
_CSS_RE = re.compile(
    r"(!important|@[a-z-]+|\{[^{}]*[;:])|"
    r"^\s*[.#][\w\-]+\s*[{,]|"
    r":\s*#[0-9a-fA-F]{3,6}|"
    r"\b\d+px\b|\bcolor\s*:|\bmargin\b|\bpadding\b|\bfont-",
    re.IGNORECASE)
_DATA_RE = re.compile(
    r"[$€£¥]\s?[\d,]+\.?\d*|"          # currency
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|"  # dates
    r"\b\d+\.\d{2}\b|"                  # decimals (prices, totals)
    r"\b\d{1,3}(,\d{3})+\b|"            # thousands
    r"\b\d+\s?%|"                       # percentages
    r"\b[A-Z]{2}\s?\d{3,4}\b|"          # flight/order numbers
    r"\b(Q[1-4]|FY\d{2,4}|Total|Subtotal|Balance|Amount)\b",
    re.IGNORECASE)


def _is_css(line: str) -> bool:
    return bool(_CSS_RE.search(line))


def _is_linky(line: str) -> bool:
    """Link/button grid line: mostly brackets, URLs, or bare CTAs."""
    s = line.strip()
    if not s:
        return False
    if s.startswith(("<http", "http")):
        return True
    brackets = len(re.findall(r"\[[^\]]*\]", s))
    words = len(s.split())
    return brackets >= 2 and brackets >= words / 2


def looks_like_table(text: str, min_rows: int = 2) -> bool:
    """Cheap detector: pipe-delimited rows or aligned column runs."""
    return detect_table(text, min_rows=min_rows)[0]


def detect_table(text: str, min_rows: int = 8) -> tuple[bool, dict]:
    """Detect table structure; return (is_table, signals dict for telemetry).

    v2 signals (from 682-mail sweep):
    - CSS lines and link-grid lines are excluded BEFORE counting alignment,
      killing the Amtrak-stylesheet and coupon-grid false positives.
    - data_lines counts lines with currency/dates/numbers/totals — real
      tables carry data, button grids do not.
    - Fires only when structural rows AND data density both hold.
    """
    sig = {"pipe_rows": 0, "aligned_lines": 0, "max_run": 0,
           "total_lines": 0, "css_lines": 0, "hdr_lines": 0, "link_lines": 0,
           "data_lines": 0, "min_rows": min_rows}
    if not text:
        return False, sig
    lines = [ln for ln in text.splitlines() if ln.strip()]
    sig["total_lines"] = len(lines)
    if len(lines) < 2:
        return False, sig
    content = [ln for ln in lines if not _is_css(ln)]
    sig["css_lines"] = len(lines) - len(content)
    nohdr = [ln for ln in content if not _HDR_RE.search(ln.strip())]
    sig["hdr_lines"] = len(content) - len(nohdr)
    struct = [ln for ln in nohdr if not _is_linky(ln)]
    sig["link_lines"] = len(content) - len(struct)
    if not struct:
        return False, sig
    pipe_rows = sum(1 for ln in struct if ln.count("|") >= 2)
    sig["pipe_rows"] = pipe_rows
    aligned = sum(1 for ln in struct
                  if len(re.findall(r" {2,}\S", ln)) >= 2)
    sig["aligned_lines"] = aligned
    run = best = 0
    for ln in struct:
        run = run + 1 if ln.count("|") >= 2 else 0
        best = max(best, run)
    sig["max_run"] = best
    data = sum(1 for ln in struct if _DATA_RE.search(ln))
    sig["data_lines"] = data
    struct_rows = max(pipe_rows, aligned, best)
    table_like = struct_rows >= 2 and data >= 2
    big_enough = struct_rows >= min_rows and data >= min_rows // 2
    sig["table_like"] = table_like
    sig["big_enough"] = big_enough
    return (table_like and big_enough), sig


def restructure_table(text: str, url: str, timeout: int = 300) -> str:
    """Send table text to the vision endpoint, failover across URL list."""
    body = json.dumps({
        "messages": [{"role": "user",
                      "content": _TABLE_PROMPT + text}],
        "max_tokens": 2000,
        "temperature": 0,
    }).encode()
    last_err: Exception | None = None
    for u in _as_url_list(url):
        req = urllib.request.Request(
            u.rstrip("/") + "/v1/chat/completions", data=body,
            headers={"Content-Type": "application/json"})
        try:
            d = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
            return d["choices"][0]["message"]["content"].strip()
        except Exception as e:  # noqa: BLE001 (try next URL)
            last_err = e
            continue
    raise RuntimeError(f"vision failed on all urls: {last_err}") from None


def maybe_restructure(text: str, url: str, timeout: int = 300) -> tuple[str, bool]:
    """Return (possibly restructured text, was_table). Non-tables pass through."""
    if not looks_like_table(text):
        return text, False
    return restructure_table(text, url, timeout), True
