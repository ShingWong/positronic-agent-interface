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

"""Threat tagger unit tests — synthetic fixtures only, no real mail."""
from positronic_ai.threat import score_threat


def test_clean_known_sender_plain_mail():
    out = score_threat("boss@company.com", "Q3 report",
                       "Here is the quarterly report draft.", 12)
    assert out["tag"] == "clean"


def test_phishing_fake_brand_credential_link():
    out = score_threat("support@evil.example",
                       "Adobe login required",
                       "Please login at https://adobe-verify.example/signin "
                       "to verify your password.", 0)
    assert out["tag"] == "phishing"
    assert any("fake-context" in r or "credential-link" in r
               for r in out["reasons"])


def test_scam_advance_fee_new_sender():
    out = score_threat("prince@unknown.example", "Inheritance claim",
                       "You are the beneficiary of a large inheritance. "
                       "Wire transfer fee required.", 0)
    assert out["tag"] == "scam"


def test_spam_junk_lexicon():
    out = score_threat("promo@blast.example", "Win now",
                       "Lottery prize! Double your crypto giveaway today.", 3)
    assert out["tag"] == "spam"


def test_ip_link_is_phishing():
    out = score_threat("a@b.example", "Verify account",
                       "Login now: http://10.1.2.3/verify password.", 0)
    assert out["tag"] == "phishing"
    assert "ip-link" in out["reasons"]


def test_phishing_beats_scam_precedence():
    out = score_threat("x@y.example", "Adobe invoice overdue",
                       "Login https://evil.example/verify password. "
                       "You are the beneficiary of an inheritance.", 0)
    assert out["tag"] == "phishing"
