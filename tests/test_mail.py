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

"""Synthetic EML strings only — never real mail (PII firewall)."""
from positronic_ai.extract.mail import parse_eml

RAW = b"""From: a@x.com\r\nTo: b@x.com\r\nSubject: Q3\r\nContent-Type: multipart/alternative; boundary=B\r\n\r\n--B\r\nContent-Type: text/plain\r\n\r\nShort note\r\n--B\r\nContent-Type: text/html; charset=UTF-8\r\nContent-Transfer-Encoding: quoted-printable\r\n\r\n<h1>Hi</h1><p>Body here</p>\r\n--B--\r\n"""


def test_parse_prefers_html_over_short_plain():
    from positronic_ai.extract.mail import parse_eml
    m = parse_eml(RAW)
    assert m["subject"] == "Q3"
    assert any(p["mime"] == "text/html" and "Body here" in p["text"] for p in m["parts"])


def test_charset_lie_flagged_not_lost():
    from positronic_ai.extract.mail import parse_eml
    raw = "Subject: T\r\nContent-Type: text/plain; charset=windows-1252\r\n\r\ncaf\xe9\n".encode("latin-1")
    m = parse_eml(raw)
    assert "caf" in m["parts"][0]["text"]  # content survives, flag records the lie


def test_shape_is_exact():
    m = parse_eml(RAW)
    assert set(m) == {"subject", "from", "to", "date", "parts", "flags"}
    assert all(set(p) == {"mime", "text"} for p in m["parts"])
    assert m["from"] == "a@x.com" and m["to"] == "b@x.com"


def test_rfc2047_subject_decoded():
    raw = (b"Subject: =?UTF-8?Q?Q3_caf=C3=A9?=\r\n"
           b"Content-Type: text/plain; charset=UTF-8\r\n\r\nbody\r\n")
    m = parse_eml(raw)
    assert m["subject"].startswith("Q3")
    assert "caf" in m["subject"]


def test_winmail_flagged_body_survives():
    raw = (b"Subject: msg\r\nContent-Type: multipart/mixed; boundary=B\r\n\r\n"
           b"--B\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\nreal text\r\n"
           b"--B\r\nContent-Type: application/ms-tnef; name=\"winmail.dat\"\r\n"
           b"Content-Disposition: attachment; filename=\"winmail.dat\"\r\n"
           b"Content-Transfer-Encoding: base64\r\n\r\nAAECAw==\r\n--B--\r\n")
    m = parse_eml(raw)
    assert m["flags"].get("winmail") is True
    assert any(p["mime"] == "text/plain" and "real text" in p["text"]
               for p in m["parts"])


def test_charset_fallback_on_bogus_declared():
    raw = (b"Content-Type: text/plain; charset=not-a-real-charset\r\n\r\n"
           b"caf\xc3\xa9\r\n")
    m = parse_eml(raw)
    assert "caf" in m["parts"][0]["text"]
    assert m["flags"].get("charset_fallback") is True


def test_rtf_control_words_stripped_and_flagged():
    raw = (b"Content-Type: text/rtf; charset=us-ascii\r\n\r\n"
           b"{\\rtf1\\ansi\\deff0 {\\fonttbl}\\b Hello\\b0  world.}\r\n")
    m = parse_eml(raw)
    assert m["flags"].get("rtf_only") is True
    rtf = [p for p in m["parts"] if p["mime"] == "text/rtf"]
    assert rtf and "Hello" in rtf[0]["text"]
    assert "\\rtf1" not in rtf[0]["text"] and "{" not in rtf[0]["text"]


def test_one_bad_part_never_kills_the_mail(monkeypatch):
    # compat32 silently tolerates bad base64, so drive the isolation path
    # directly: a decoder that explodes on one part must not kill the mail.
    import positronic_ai.extract.mail as M

    orig = M._decode_text

    def boom(part):
        if part.get_content_type() == "text/html":
            raise RuntimeError("simulated decode explosion")
        return orig(part)

    monkeypatch.setattr(M, "_decode_text", boom)
    m = parse_eml(RAW)
    assert [p["mime"] for p in m["parts"]] == ["text/plain"]
    assert "part_error" in m["flags"]


def test_doveadm_body_only_multipart_recovered():
    # shape produced by `doveadm fetch body`: bare "body:" field line, then
    # the multipart body itself (top-level MIME headers stripped server-side)
    raw = (b"body:\r\n"
           b"--=_Part_1397416\r\n"
           b"Content-Type: text/plain; charset=UTF-8\r\n"
           b"Content-Transfer-Encoding: 7bit\r\n\r\nplain words\r\n"
           b"--=_Part_1397416\r\n"
           b"Content-Type: text/html; charset=UTF-8\r\n"
           b"Content-Transfer-Encoding: quoted-printable\r\n\r\n"
           b"<h1>Hi</h1><p>Body here</p>\r\n"
           b"--=_Part_1397416--\r\n")
    m = parse_eml(raw)
    assert any(p["mime"] == "text/html" and "Body here" in p["text"]
               for p in m["parts"])
    assert any(p["mime"] == "text/plain" and "plain words" in p["text"]
               for p in m["parts"])
    assert m["flags"].get("recovered") is True


def test_truncated_flag_on_huge_part():
    big = b"Content-Type: text/plain; charset=UTF-8\r\n\r\n" + b"x" * 60000
    m = parse_eml(big + b"\r\n")
    assert m["flags"].get("truncated") is True
    assert len(m["parts"][0]["text"]) <= 50000


def test_choose_body_prefers_substantial_plain():
    from positronic_ai.extract.mail import choose_body
    plain = "p" * 500
    html = "h" * 100
    mime, _text = choose_body([{"mime": "text/plain", "text": plain},
                               {"mime": "text/html", "text": html}])
    assert mime == "text/plain"
    # tiny plain stub next to a real html body -> html wins
    mime, _ = choose_body([{"mime": "text/plain", "text": "view in browser"},
                           {"mime": "text/html", "text": "<p>" + "x" * 400 + "</p>"}])
    assert mime == "text/html"


def test_trim_quotes_depth_signature_disclaimer():
    from positronic_ai.extract.mail import trim_quotes
    src = ("l1 keep\n"
           "> d2 keep\n"
           ">> d2 keep\n"
           ">>> d3 drop\n"
           ">>>> d4 drop\n"
           "-- \n"
           "Old Signature\n"
           "more sig\n"
           "This email is privileged and confidential.\n")
    out = trim_quotes(src)
    assert "l1 keep" in out and "> d2 keep" in out and ">> d2 keep" in out
    assert "d3 drop" not in out and "d4 drop" not in out
    assert "Old Signature" not in out
    assert "privileged" not in out


def test_body_markdown_converts_html_and_trims():
    from positronic_ai.extract.mail import body_markdown
    m = parse_eml(RAW)
    md = body_markdown(m)
    assert "Body here" in md
    assert "<h1>" not in md
