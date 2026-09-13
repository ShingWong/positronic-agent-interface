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

"""EML parsing for the mail pipeline. Policy, not cleverness: prefer
text/plain when substantial else HTML; never lose a mail to one bad part;
flag (never silently drop) winmail/RTF/charset issues for the converter
queue. Quote policy: newest 2 levels kept, signatures/disclaimers stripped
(they poison embeddings — identical vectors across thousands of mails).

Deviation from the task brief (evidence-backed): the brief's snippet calls
`part.get_content()` under `policy.compat32`, but legacy `Message` objects
have no `get_content()` on this interpreter (3.13) — every text part raises
AttributeError and both brief tests come back with empty `parts`. Content
extraction is therefore done per part: `get_payload(decode=True)` (compat32
handles base64/QP CTE) then the declared→utf-8→replace charset chain with a
`charset_fallback` flag, per the brief's stated policy.

Leniency also covers `doveadm fetch body` payloads (what brain_henry pulls):
a bare `body:` field line and top-level MIME headers stripped server-side —
we re-synthesize the multipart envelope from the leading boundary line and
flag `recovered`.
"""
import email
import re
from email import policy

from .html import html_to_markdown
from .md import md_normalize

DISCLAIMER = ("confidentiality", "intended only for", "unsubscribe",
              "view in browser", "privileged and confidential")
MAX_PART_CHARS = 50_000     # per-part cap; over → truncate + flag
PLAIN_MIN_SHARE = 0.5       # plain counts as "substantial" at >= 50% of html
PLAIN_MIN_CHARS = 40        # ... and never under this

_DOVEADM_BODY = re.compile(rb"(?i)^body[ \t]*:[^\r\n]*\r?\n")
_BOUND_OPEN = re.compile(r"^--(\S+?)(--)?[ \t]*$")
_QUOTE = re.compile(r"^\s*(>+)")
_SIG_DASH = re.compile(r"^--\s*$")
_RTF_CTRL = re.compile(r"\\'[0-9a-fA-F]{2}|\\[a-zA-Z]{1,32}-?\d{1,10} ?"
                       r"|\\[^a-zA-Z]|[{}]")


def _is_boiler(line: str) -> bool:
    low = line.lower()
    return any(d in low for d in DISCLAIMER)


def _recover(raw: bytes) -> tuple[bytes, bool]:
    """Undo `doveadm fetch body` mutilation: drop the field line and, if the
    payload starts on a multipart boundary opener, rebuild the top-level
    MIME header from it. Returns (possibly fixed bytes, recovered?)."""
    m = _DOVEADM_BODY.match(raw)
    body = raw[m.end():] if m else raw
    head = body.decode("latin-1", "replace").split("\n", 8)
    opener = _BOUND_OPEN.match(head[0].rstrip("\r")) if head else None
    if (opener and not opener.group(2)
            and any(ln.lstrip("\r").startswith("Content-Type:")
                    for ln in head[1:9])):
        boundary = opener.group(1).encode("latin-1", "replace")
        synth = (b"MIME-Version: 1.0\r\nContent-Type: multipart/mixed; "
                 b'boundary="' + boundary + b'"\r\n\r\n' + body)
        return synth, True
    if m:
        return body, True
    return raw, False


def _hdr(msg, name: str) -> str:
    try:
        return str(msg.get(name, ""))
    except Exception:  # noqa: BLE001 — header damage never kills the mail
        return ""


def _subject(msg) -> str:
    from email.header import decode_header
    raw = str(msg.get("Subject", "") or "")
    try:
        parts = decode_header(raw)
        return "".join(t.decode(cs or "utf-8", "replace") if isinstance(t, bytes)
                       else t for t, cs in parts)
    except Exception:  # noqa: BLE001 — malformed RFC2047: keep it raw
        return raw


def _decode_text(part) -> tuple[str, bool]:
    """payload bytes -> str via declared→utf-8→replace; True = fallback."""
    data = part.get_payload(decode=True)
    if data is None:
        p = part.get_payload()
        data = p.encode("utf-8", "replace") if isinstance(p, str) else b""
    declared = part.get_content_charset()
    for i, cs in enumerate([c for c in (declared, "utf-8") if c]):
        try:
            return data.decode(cs), i > 0
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", "replace"), True


def _rtf_to_text(s: str) -> str:
    t = _RTF_CTRL.sub("", s)
    return re.sub(r"[ \t]{2,}", " ", t).strip()


def parse_eml(raw: bytes) -> dict:
    fixed, recovered = _recover(raw)
    msg = email.message_from_bytes(fixed, policy=policy.compat32)
    flags: dict[str, bool | str] = {}
    if recovered:
        flags["recovered"] = True
    parts: list[dict] = []
    try:
        walker = msg.walk() if msg.is_multipart() else [msg]
        for part in walker:
            try:
                mime = part.get_content_type()
                if mime.startswith("multipart/"):
                    continue
                fname = (part.get_filename() or "").lower()
                if mime == "application/ms-tnef" or fname == "winmail.dat":
                    flags["winmail"] = True
                    continue
                if mime in ("text/plain", "text/html"):
                    text, fell_back = _decode_text(part)
                    if fell_back:
                        flags["charset_fallback"] = True
                    if len(text) > MAX_PART_CHARS:
                        text = text[:MAX_PART_CHARS]
                        flags["truncated"] = True
                    if text.strip():
                        parts.append({"mime": mime, "text": text})
                elif mime == "text/rtf":
                    flags["rtf_only"] = True
                    text, fell_back = _decode_text(part)
                    if fell_back:
                        flags["charset_fallback"] = True
                    stripped = _rtf_to_text(text)
                    if len(stripped) > MAX_PART_CHARS:
                        stripped = stripped[:MAX_PART_CHARS]
                        flags["truncated"] = True
                    if stripped.strip():
                        parts.append({"mime": "text/rtf", "text": stripped})
            except Exception as ex:  # noqa: BLE001 — one bad part never kills the mail
                flags["part_error"] = str(ex)[:100]
    except Exception as ex:  # noqa: BLE001
        flags["parse_error"] = str(ex)[:100]
    return {"subject": _subject(msg),
            "from": _hdr(msg, "From"), "to": _hdr(msg, "To"),
            "date": _hdr(msg, "Date"), "parts": parts, "flags": flags}


def choose_body(parts: list[dict]) -> tuple[str, str]:
    """Policy: newest/substantial text/plain else html else stripped rtf."""
    def best(mime: str) -> str:
        cand = [p["text"] for p in parts if p["mime"] == mime]
        return max(cand, key=len, default="")

    plain, html, rtf = best("text/plain"), best("text/html"), best("text/rtf")
    if plain and not html:
        return "text/plain", plain
    if plain and len(plain.strip()) >= PLAIN_MIN_CHARS and \
            len(plain) >= PLAIN_MIN_SHARE * len(html):
        return "text/plain", plain
    if html:
        return "text/html", html
    if plain:
        return "text/plain", plain
    return "text/rtf", rtf


def trim_quotes(text: str) -> str:
    """Drop quote depth > 2, classic `-- ` signature tail, boiler lines."""
    out: list[str] = []
    for line in text.split("\n"):
        q = _QUOTE.match(line)
        if q and len(q.group(1)) > 2:
            continue
        if _SIG_DASH.match(line):
            break
        if _is_boiler(line):
            continue
        out.append(line)
    return "\n".join(out)


def body_markdown(m: dict) -> str:
    """Parse result -> normalized markdown body ('' if no textual parts).
    The walker chunks this; headers-only mail chunks to nothing and is
    logged, not silently dropped."""
    mime, text = choose_body(m.get("parts", []))
    if not text.strip():
        return ""
    md = html_to_markdown(text) if mime == "text/html" else text
    return md_normalize(trim_quotes(md))
