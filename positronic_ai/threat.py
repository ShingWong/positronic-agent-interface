# =====================================================================
# Project Positronic — Polytemporal Cognitive Engram Memory Substrate
# Copyright (C) 2026 Shing Wong. All Rights Reserved.
# =====================================================================
# This program is DUAL-LICENSED. You may redistribute and/or modify it 
# under the terms of the GNU Affero General Public License as published by the 
# Free Software Foundation, either version 3 of the License, or (at your 
# option) any later version.
#
# Alternatively, commercial entities, multi-tenant instances, and Managed 
# Service Providers (MSPs) may utilize this program under a separate, 
# proprietary Commercial License Waiver issued directly by the copyright 
# holder, completely exempt from the network-use copyleft restrictions of 
# the AGPLv3 Section 13.
#
# This program is distributed in the hope that it will be useful, but 
# WITHOUT ANY WARRANTY; without even the implied warranty of 
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU 
# Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License 
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
# =====================================================================

"""Threat tagging for mail. Pure function, no DB access.

A SCORE, not a verdict by itself. Every category accumulates weight from the
signals that fired; the highest-priority category reaching its threshold wins.
Nothing about which categories exist is baked into this module -- see
`DEFAULT_SPEC`, and see `docs/USER-GUIDE.md` for how to set your own.

Why it is data rather than code: email archive ingestion for a regulated
company and reading one person's personal mail are different jobs. The
categories, the words that trigger them, and how much evidence is enough
should be settings. Adding "policy violation" or "illegal activity" to the
alert feature must not require a code change and a release.

Shape of a spec:

    {
      "categories": [
        {"tag": "phishing", "priority": 100, "threshold": 1.0,
         "signals": [{"id": "credential-link", "kind": "credential_link",
                      "weight": 1.0}]},
        ...
      ]
    }

`priority` decides which category wins when several reach their threshold
(higher wins). `weight` is how much one signal contributes; `weight: 0` means
"record it as a reason, never move the verdict". `threshold` is how much total
weight that category needs before it fires.

Config overrides MERGE by tag: naming a tag replaces just that category, so
tuning one category does not mean restating the others.
"""

import re
from urllib.parse import urlparse

# ── signal kinds ──────────────────────────────────────────────────────────
# Each is a function of the parsed mail. Adding a kind here IS a code change,
# but adding a category, a word list, or a weight is not -- which is the
# distinction that matters for per-application tuning.

_URL_RE = re.compile(r"https?://[^\s<>'\"]+", re.IGNORECASE)

DEFAULT_CREDENTIAL_TERMS = [
    "login", "log in", "sign in", "verify", "password", "credential",
    "2fa", "one-time",
]

DEFAULT_BRANDS = ["adobe", "microsoft", "apple", "google", "amazon",
                  "paypal", "dhl", "fedex"]

DEFAULT_SCAM_TERMS = [
    "beneficiar", "inheritance", "advance fee", "overdue invoice",
    "wire transfer", "gift cards", "gift card", "crypto wallet",
    "private key", "recovery phrase", "nigerian", "prince",
]

DEFAULT_SPAM_TERMS = [
    "enlargement", "viagra", "cialis", "crypto giveaway", "double your",
    "lottery win", "lottery prize", "miracle cure", "miracle pills",
]

_IP_RE = re.compile(r"\d+\.\d+\.\d+\.\d+")


def default_spec() -> dict:
    """The built-in spec. Reproduces the original hardcoded behaviour exactly.

    Kept as data so that "what the defaults do" is inspectable rather than
    spread across branches of code.
    """
    return {
        "credential_terms": list(DEFAULT_CREDENTIAL_TERMS),
        "brands": list(DEFAULT_BRANDS),
        "categories": [
            {
                "tag": "phishing", "priority": 100, "threshold": 1.0,
                "signals": [
                    {"id": "credential-link", "kind": "credential_link",
                     "weight": 1.0},
                    {"id": "ip-link", "kind": "ip_link", "weight": 1.0},
                    {"id": "punycode-link", "kind": "punycode_link",
                     "weight": 1.0},
                    {"id": "new-sender", "kind": "new_sender", "weight": 0.0},
                    {"id": "foreign-link", "kind": "foreign_link",
                     "weight": 0.0, "unless": ["credential-link"]},
                    {"id": "fake-brand", "kind": "brand_context",
                     "weight": 0.0},
                ],
            },
            {
                "tag": "scam", "priority": 90, "threshold": 2.0,
                "signals": [
                    {"id": "scam-lexicon", "kind": "lexicon", "weight": 1.0,
                     "terms": list(DEFAULT_SCAM_TERMS)},
                    {"id": "new-sender", "kind": "new_sender", "weight": 1.0},
                ],
            },
            {
                "tag": "spam", "priority": 80, "threshold": 1.0,
                "signals": [
                    {"id": "spam-lexicon", "kind": "lexicon", "weight": 1.0,
                     "terms": list(DEFAULT_SPAM_TERMS)},
                ],
            },
        ],
    }


# Signals that are informational for every category, and so are always
# recorded as reasons even when no category references them.
_ALWAYS_REPORTED = ("new_sender", "foreign_link", "brand_context")


def _sender_domain(sender: str) -> str:
    m = re.search(r"@([\w.\-]+)", sender or "")
    return m.group(1).lower() if m else ""


def _hits_terms(terms, low: str) -> bool:
    return any(t.lower() in low for t in terms or ())


def _eval_signals(spec: dict, *, sender, subject, body, sdom, hosts,
                  history_count) -> dict:
    """Evaluate every signal kind present in the spec. Returns id -> reason str.

    A reason string may carry a detail (a hostname, a brand) the way the
    original did, so operator-facing output stays the same shape.
    """
    text = f"{subject or ''}\n{body or ''}"
    low = text.lower()
    cred_terms = spec.get("credential_terms") or DEFAULT_CREDENTIAL_TERMS
    cred = _hits_terms(cred_terms, low)

    out: dict = {}
    unless: dict = {}
    for cat in spec.get("categories") or []:
        for sig in cat.get("signals") or []:
            kind = sig.get("kind")
            sid = sig.get("id") or kind
            if sig.get("unless"):
                unless.setdefault(sid, set()).update(sig["unless"])
            if kind == "new_sender":
                if history_count <= 0:
                    out.setdefault(sid, []).append("isolation:new-sender")
            elif kind == "brand_context":
                for brand in spec.get("brands") or []:
                    if brand in low and brand not in sdom:
                        out.setdefault(sid, []).append(f"fake-context:{brand}")
                        break
            elif kind == "credential_link":
                for h in hosts:
                    if h and sdom and h != sdom and cred:
                        out.setdefault(sid, []).append(
                            f"credential-link:{h}")
            elif kind == "foreign_link":
                for h in hosts:
                    if h and sdom and h != sdom:
                        out.setdefault(sid, []).append(
                            f"foreign-link:{h}")
            elif kind == "ip_link":
                for h in hosts:
                    if _IP_RE.fullmatch(h.lower()):
                        out.setdefault(sid, []).append("ip-link")
            elif kind == "punycode_link":
                for h in hosts:
                    if h.lower().startswith("xn--"):
                        out.setdefault(sid, []).append("punycode-link")
            elif kind == "lexicon":
                if _hits_terms(sig.get("terms"), low):
                    # Reason is the signal id unless overridden, so the
                    # defaults reproduce the original strings ("scam-lexicon")
                    # and a new category gets a predictable one.
                    out.setdefault(sid, []).append(sig.get("reason") or sid)
            elif kind == "custom_text":
                # Escape hatch: a plain regex supplied by config. Lets an
                # operator add a category without a release, at the cost of
                # running a regex they wrote on every message.
                pat = sig.get("pattern")
                if pat:
                    try:
                        if re.search(pat, text, re.IGNORECASE):
                            out.setdefault(sid, []).append(
                                sig.get("reason") or f"{sid}:match")
                    except re.error as ex:
                        raise ValueError(
                            f"threat signal {sid!r} has a bad pattern: {ex}") from ex

    # `unless` expresses mutual exclusion. The original branched --
    # "if credential words: credential-link ELSE foreign-link" -- so a mail
    # with a credential link reported only the former. Two independent signals
    # cannot express that; `unless` can. Resolved to a fixpoint so a chain of
    # suppressions settles regardless of evaluation order.
    for _ in range(len(unless) + 1):
        drop = {sid for sid, blockers in unless.items()
                if sid in out and (blockers & set(out))}
        if not drop:
            break
        for sid in drop:
            out.pop(sid, None)
            unless.pop(sid, None)
    return out


def score_threat(sender="", subject="", body="", sender_history_count=0,
                 spec=None) -> dict:
    """Score one mail. Returns {tag, reasons, scores}.

    `spec` defaults to `default_spec()`. `scores` maps every category tag to the
    weight it accumulated and whether it reached its threshold, so a caller can
    explain a verdict or show a near miss instead of only a label.
    """
    spec = spec or default_spec()
    sdom = _sender_domain(sender or "")
    hosts = []
    for u in _URL_RE.findall(body or ""):
        try:
            hosts.append(urlparse(u).hostname or "")
        except ValueError:
            continue

    fired = _eval_signals(spec, sender=sender, subject=subject, body=body,
                          sdom=sdom, hosts=hosts,
                          history_count=sender_history_count)

    scores: dict = {}
    tag = "clean"
    ranked = sorted(spec.get("categories") or [],
                    key=lambda c: c.get("priority", 0), reverse=True)
    best = None
    for cat in ranked:
        ctag = cat.get("tag")
        thr = float(cat.get("threshold", 1.0))
        total = 0.0
        for sig in cat.get("signals") or []:
            sid = sig.get("id") or sig.get("kind")
            if sid in fired:
                total += float(sig.get("weight", 1.0))
        reached = total >= thr
        scores[ctag] = {"score": round(total, 4), "threshold": thr,
                        "fired": reached}
        if reached and best is None:
            best = ctag

    if best:
        tag = best

    # Reasons split in two, because the original behaved this way:
    #  * standalone signals (new sender, foreign link, brand context) were
    #    recorded whether or not they moved the verdict;
    #  * lexicon reasons were appended INSIDE the branch that chose the tag,
    #    so "scam-lexicon" only ever appeared when scam actually won. Firing
    #    a lexicon signal while a higher-priority category wins must NOT
    #    report it -- caught by the characterization test.
    lexicon_ids = {
        (sig.get("id") or sig.get("kind"))
        for cat in (spec.get("categories") or [])
        for sig in (cat.get("signals") or [])
        if sig.get("kind") == "lexicon"
    }
    reasons = {r for sid, rs in fired.items()
               if sid not in lexicon_ids for r in rs}
    if best:
        winner = next(c for c in ranked if c.get("tag") == best)
        for sig in winner.get("signals") or []:
            sid = sig.get("id") or sig.get("kind")
            if sid in lexicon_ids and sid in fired:
                reasons.update(fired[sid])
    return {"tag": tag, "reasons": sorted(reasons), "scores": scores}


def merge_spec(override: dict | None) -> dict:
    """Merge a config override into the default spec, by category tag.

    A named tag REPLACES that category wholesale. Other categories survive, so
    an operator adding "policy" does not have to restate "phishing".
    """
    spec = default_spec()
    # Order matters: `False` means disabled, and `not False` is True, so a
    # falsy check placed first would silently ignore a brain that asked for
    # threat scoring to be turned off.
    if override is False:
        return {"categories": [], "credential_terms": [],
                "brands": [], "disabled": True}
    if override is None or override == {}:
        return spec
    if not isinstance(override, dict):
        raise ValueError(  # noqa: TRY004 (CLI catches ValueError)
            "threat config must be an object, false, or null")

    for key in ("credential_terms", "brands"):
        if key in override:
            spec[key] = list(override[key] or [])

    new_cats = override.get("categories")
    if new_cats is not None:
        if not isinstance(new_cats, list):
            raise ValueError("threat.categories must be a list")
        replaced: dict = {}
        order: list = []
        for cat in spec["categories"]:
            replaced[cat["tag"]] = cat
            order.append(cat["tag"])
        for cat in new_cats:
            if not isinstance(cat, dict) or not cat.get("tag"):
                raise ValueError("each threat category needs a tag")
            validate_category(cat)
            if cat["tag"] not in replaced:
                order.append(cat["tag"])
            replaced[cat["tag"]] = cat
        spec["categories"] = [replaced[t] for t in order]
    return spec


def validate_category(cat: dict) -> None:
    for k in ("tag", "priority", "threshold", "signals"):
        if k not in cat:
            raise ValueError(f"threat category missing {k!r}: {cat!r}")
    if not isinstance(cat["signals"], list) or not cat["signals"]:
        raise ValueError(f"threat category {cat['tag']!r} needs signals")
    float(cat["threshold"])
    for sig in cat["signals"]:
        if not isinstance(sig, dict) or "kind" not in sig:
            raise ValueError(f"threat signal needs a kind: {sig!r}")
        float(sig.get("weight", 1.0))
        if sig["kind"] == "custom_text" and not sig.get("pattern"):
            raise ValueError(
                f"custom_text signal {sig.get('id')!r} needs a pattern")


_KNOWN_KINDS = {"new_sender", "brand_context", "credential_link",
                "foreign_link", "ip_link", "punycode_link", "lexicon",
                "custom_text"}


def validate_spec_override(override, *, brain: str = "") -> None:
    """Validate a brain's `threat` config block. Raises on anything unusable."""
    tag = f"brains.{brain}.threat" if brain else "threat"
    if override is False or override is None:
        return
    if not isinstance(override, dict):
        raise ValueError(  # noqa: TRY004 (CLI catches ValueError)
            f"{tag} must be an object, false, or null")
    for key in ("credential_terms", "brands"):
        if key in override and not isinstance(override[key], list):
            raise ValueError(f"{tag}.{key} must be a list")
    cats = override.get("categories")
    if cats is None:
        return
    if not isinstance(cats, list):
        raise ValueError(  # noqa: TRY004 (CLI catches ValueError)
            f"{tag}.categories must be a list")
    for cat in cats:
        try:
            validate_category(cat)
        except ValueError as ex:
            raise ValueError(f"{tag}: {ex}") from ex
        for sig in cat["signals"]:
            if sig["kind"] not in _KNOWN_KINDS:
                raise ValueError(
                    f"{tag}: unknown signal kind {sig['kind']!r}; "
                    f"known kinds: {sorted(_KNOWN_KINDS)}")
    tags = [c["tag"] for c in cats]
    dupes = sorted({t for t in tags if tags.count(t) > 1})
    if dupes:
        raise ValueError(f"{tag}: duplicate category tag(s): {dupes}")


def spec_from_config(brain_cfg: dict | None) -> dict:
    """Resolve a brain's threat config block into a spec."""
    return merge_spec((brain_cfg or {}).get("threat"))