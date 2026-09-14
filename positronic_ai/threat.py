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

"""Threat tagging heuristics for mail (v0.2). Pure function, no DB access.

Tags: phishing (credential theft / fake login / malicious links),
scam (financial fraud / advance-fee / fake invoices),
spam (general junk). Precedence: phishing > scam > spam > clean.
"""

import re
from urllib.parse import urlparse

_URL_RE = re.compile(r"https?://[^\s<>'\"]+", re.IGNORECASE)
_CRED_RE = re.compile(r"\b(login|log in|sign in|verify|password|credential|2fa|one-time)\b", re.IGNORECASE)
_BRANDS = ("adobe", "microsoft", "apple", "google", "amazon", "paypal", "dhl", "fedex")

_SCAM_RE = re.compile(
    r"\b(beneficiar|inheritance|advance fee|overdue invoice|wire transfer|"
    r"gift ?cards?|crypto wallet|private key|recovery phrase|nigerian|prince)\b",
    re.IGNORECASE)
_SPAM_RE = re.compile(
    r"\b(enlargement|viagra|cialis|crypto giveaway|double your|"
    r"lottery (win|prize)|miracle (cure|pills?))\b",
    re.IGNORECASE)


def _sender_domain(sender: str) -> str:
    m = re.search(r"@([\w.\-]+)", sender or "")
    return m.group(1).lower() if m else ""


def score_threat(sender="", subject="", body="",
                 sender_history_count=0) -> dict:
    """Score one mail. Returns {tag, reasons} with tag in
    clean|spam|phishing|scam."""
    reasons: list[str] = []
    text = f"{subject or ''}\n{body or ''}"
    sdom = _sender_domain(sender or "")
    urls = _URL_RE.findall(body or "")
    hosts = []
    for u in urls:
        try:
            hosts.append(urlparse(u).hostname or "")
        except ValueError:
            continue

    if sender_history_count <= 0:
        reasons.append("isolation:new-sender")
    low = text.lower()
    for brand in _BRANDS:
        if brand in low and brand not in sdom:
            reasons.append(f"fake-context:{brand}")
            break
    cred = bool(_CRED_RE.search(text))
    for h in hosts:
        hl = h.lower()
        if hl != sdom and sdom and hl:
            if cred:
                reasons.append(f"credential-link:{hl}")
            else:
                reasons.append(f"foreign-link:{hl}")
        if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", hl):
            reasons.append("ip-link")
        if hl.startswith("xn--"):
            reasons.append("punycode-link")

    tag = "clean"
    if any(r.startswith(("credential-link", "ip-link", "punycode-link"))
           for r in reasons):
        tag = "phishing"
    elif _SCAM_RE.search(text) and sender_history_count <= 0:
        tag = "scam"
        reasons.append("scam-lexicon")
    elif _SPAM_RE.search(text):
        tag = "spam"
        reasons.append("spam-lexicon")
    return {"tag": tag, "reasons": reasons}
