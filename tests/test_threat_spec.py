"""The default spec must reproduce the ORIGINAL hardcoded threat logic.

The original `score_threat` was branchy code: hardcoded regexes, a hardcoded
brand list, a hardcoded precedence. It was replaced with a data-driven spec.
Behaviour must not move, or every tag already written to a user's mail is now
wrong for a reason nobody chose.

`_original` below is the old implementation, transcribed. It is the oracle.
"""
import re
from urllib.parse import urlparse

from positronic_ai.threat import default_spec, score_threat

_URL_RE = re.compile(r"https?://[^\s<>'\"]+", re.IGNORECASE)
_CRED_RE = re.compile(
    r"\b(login|log in|sign in|verify|password|credential|2fa|one-time)\b",
    re.IGNORECASE)
_BRANDS = ("adobe", "microsoft", "apple", "google", "amazon", "paypal",
           "dhl", "fedex")
_SCAM_RE = re.compile(
    r"\b(beneficiar|inheritance|advance fee|overdue invoice|wire transfer|"
    r"gift ?cards?|crypto wallet|private key|recovery phrase|nigerian|prince)\b",
    re.IGNORECASE)
_SPAM_RE = re.compile(
    r"\b(enlargement|viagra|cialis|crypto giveaway|double your|"
    r"lottery (win|prize)|miracle (cure|pills?))\b",
    re.IGNORECASE)


def _sender_domain(sender):
    m = re.search(r"@([\w.\-]+)", sender or "")
    return m.group(1).lower() if m else ""


def _original(sender="", subject="", body="", sender_history_count=0):
    reasons = []
    text = f"{subject or ''}\n{body or ''}"
    sdom = _sender_domain(sender or "")
    hosts = []
    for u in _URL_RE.findall(body or ""):
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


CASES = [
    # (sender, subject, body, history_count, why)
    ("", "", "", 0, "empty everything"),
    ("a@x.com", "hello", "plain body", 5, "known sender, nothing to see"),
    ("new@x.com", "hello", "plain body", 0, "new sender, no signals"),
    ("evil@evil.com", "Sign in to Adobe",
     "https://evil.com/login", 0, "brand + credential link -> phishing"),
    ("boss@corp.com", "Report",
     "see https://other.example/x", 9, "foreign link only: reason, not tag"),
    ("boss@corp.com", "Invoice",
     "please wire transfer to https://1.2.3.4/pay", 0, "ip link -> phishing"),
    ("a@x.com", "hi", "visit https://xn--80ak6aa92e.com/", 3,
     "punycode -> phishing"),
    ("new@x.com", "Advance fee required",
     "I am a prince with an inheritance", 0, "scam lexicon + new sender"),
    ("known@x.com", "Advance fee required",
     "I am a prince with an inheritance", 12,
     "scam lexicon but KNOWN sender -> not scam"),
    ("a@x.com", "Viagra deal", "cialis enlargement", 4, "spam lexicon"),
    ("a@x.com", "viagra", "cialis", 0, "spam even for a new sender"),
    ("new@x.com", "Invoice", "overdue invoice attached", 0,
     "scam lexicon alone, no other signals"),
    ("a@corp.com", "Adobe policy", "you must verify your password now", 7,
     "credential words but NO link -> clean"),
    ("new@x.com", "Welcome", "click https://evil.example/a "
     "and https://good.example/b", 0, "two foreign links"),
    ("a@x.com", "Paypal", "login at https://phish.example", 2,
     "brand from a non-brand domain + credential link"),
    ("new@x.com", "Crypto wallet", "send your private key", 0,
     "two scam terms, new sender"),
    ("a@x.com", "dhl", "delivery", 5, "brand matches sender domain"),
]


def test_default_spec_matches_original_on_every_case():
    spec = default_spec()
    for sender, subj, body, hist, why in CASES:
        want = _original(sender, subj, body, hist)
        got = score_threat(sender, subj, body, hist, spec=spec)
        assert got["tag"] == want["tag"], (
            f"[{why}] tag {got['tag']!r} != original {want['tag']!r}")
        assert set(got["reasons"]) == set(want["reasons"]), (
            f"[{why}] reasons {got['reasons']} != original {want['reasons']}")


def test_default_spec_is_self_consistent():
    spec = default_spec()
    prio = {c["tag"]: c["priority"] for c in spec["categories"]}
    for sender, subj, body, hist, why in CASES:
        got = score_threat(sender, subj, body, hist, spec=spec)
        assert got["scores"], f"[{why}] no scores"
        # A category may reach its threshold and still lose on priority, so
        # the winner is the highest-priority fired category, not the only
        # fired one.
        fired = [t for t, s in got["scores"].items() if s["fired"]]
        if got["tag"] == "clean":
            assert not fired, f"[{why}] clean yet fired {fired}"
        else:
            assert got["tag"] in fired, f"[{why}] winner did not fire"
            assert max(fired, key=lambda t: prio[t]) == got["tag"], (
                f"[{why}] winner {got['tag']} is not the highest-priority "
                f"fired category {fired}")
        # No lexicon reason may appear unless that category won.
        if got["tag"] != "scam":
            assert "scam-lexicon" not in got["reasons"], (
                f"[{why}] scam-lexicon leaked while {got['tag']} won")
        if got["tag"] != "spam":
            assert "spam-lexicon" not in got["reasons"], (
                f"[{why}] spam-lexicon leaked while {got['tag']} won")