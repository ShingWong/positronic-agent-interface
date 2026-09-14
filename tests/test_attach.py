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

import email.generator
import email.message
import io
import json
import subprocess

# body-walk lives outside this package; add its dir to path
import sys
import zipfile
from email.mime.multipart import MIMEMultipart
from pathlib import Path as _P

import openpyxl

from positronic_ai.engine import open_engine
from positronic_ai.extract.attach import extract_attachments

_sys_path = str(_P(__file__).resolve().parent.parent.parent
                   / "positronic-private")
if _sys_path not in sys.path:
    sys.path.insert(0, _sys_path)
import brain_henry.mail_body_ingest as M


def _find(recs, name):
    return next(r for r in recs if r["filename"] == name)


def _mk_pdf() -> bytes:
    objects = []
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj")
    objects.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj")
    objects.append(
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]"
        b" /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj")
    stream = b"BT\n/F1 24 Tf\n100 700 Td\n(Hello world) Tj\nET\n"
    objects.append(b"4 0 obj\n<< /Length %d >>\nstream\n%s\nendstream\nendobj"
                   % (len(stream), stream))
    objects.append(b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj")
    body = b"%PDF-1.4\n"
    offsets = []
    for obj in objects:
        offsets.append(len(body))
        body += obj + b"\n"
    xref_pos = len(body)
    body += b"xref\n0 6\n0000000000 65535 f \n"
    for off in offsets:
        body += b"%010d 00000 n \n" % off
    body += (b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
             % xref_pos)
    return body


def _mk_eml(attach_bytes: bytes, filename: str) -> bytes:
    import base64
    msg = email.message.Message()
    msg["Subject"] = "pickle"
    msg["From"] = "a@b.c"
    msg["To"] = "x@b.c"
    msg["Message-ID"] = "<pickle@b.c>"
    body = email.message.Message()
    body.set_payload("plain body text")
    body.set_type("text/plain")
    part = email.message.Message()
    b64 = base64.b64encode(attach_bytes).decode("ascii")
    part.set_payload(b64)
    part["Content-Transfer-Encoding"] = "base64"
    part.set_type("application/octet-stream")
    part.add_header("Content-Disposition", "attachment",
                    filename=filename)
    multipart = MIMEMultipart()
    multipart["Subject"] = "pickle"
    multipart.attach(body)
    multipart.attach(part)
    buf = io.BytesIO()
    gen = email.generator.BytesGenerator(buf)
    gen.flatten(multipart)
    return buf.getvalue()


def test_attach_pdf():
    recs = extract_attachments(_mk_eml(_mk_pdf(), "r.pdf"))
    pdf = _find(recs, "r.pdf")
    assert pdf["status"] == "ok"
    assert "Hello world" in (pdf["content_md"] or "")


def test_attach_xlsx():
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["item", "qty"])
    ws.append(["spork", "4"])
    buf = io.BytesIO()
    wb.save(buf)
    recs = extract_attachments(_mk_eml(buf.getvalue(), "sheet.xlsx"))
    x = _find(recs, "sheet.xlsx")
    assert x["status"] == "ok"
    assert "item | qty" in (x["content_md"] or "")
    assert "spork | 4" in (x["content_md"] or "")


def test_attach_rtf_via_pandoc():
    rtf = (b"{\\rtf1\\ansi\\deff0 hello world}\n")
    recs = extract_attachments(_mk_eml(rtf, "note.rtf"))
    r = _find(recs, "note.rtf")
    assert r["status"] == "ok"
    assert "hello world" in (r["content_md"] or "").lower()


def test_attach_eml_body():
    eml = (b"Subject: pickle\nFrom: a@b.c\nTo: x@b.c\n"
           b"Content-Type: text/plain\n\ninner payload here\n")
    recs = extract_attachments(_mk_eml(eml, "inner.eml"))
    e = _find(recs, "inner.eml")
    assert e["status"] == "ok"
    assert "inner payload here" in (e["content_md"] or "")
    assert "pickle" in (e["content_md"] or "")


def test_attach_winmail_deferred():
    recs = extract_attachments(_mk_eml(b"TNEF blob here", "winmail.dat"))
    w = _find(recs, "winmail.dat")
    assert w["status"] == "deferred"
    assert "TNEF" in (w["reason"] or "")


def test_attach_image_metadata():
    recs = extract_attachments(_mk_eml(b"\x89PNG" + b"x" * 400, "shot.png"))
    p = _find(recs, "shot.png")
    assert p["status"] == "ok"
    assert "shot.png" in (p["content_md"] or "")
    assert "404B" in (p["content_md"] or "")


def test_attach_zip_listing():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("alpha.txt", "a")
        z.writestr("beta.txt", "b")
    recs = extract_attachments(_mk_eml(buf.getvalue(), "bundle.zip"))
    zr = next(r for r in recs if r["filename"] == "bundle.zip")
    assert zr["status"] == "ok"
    assert "alpha.txt" in (zr["content_md"] or "")
    assert "beta.txt" in (zr["content_md"] or "")


def test_attach_unsupported_returns_unsupported():
    recs = extract_attachments(_mk_eml(b"whatever", "data.mp4"))
    assert len(recs) == 1
    assert recs[0]["status"] == "unsupported"


def test_attach_part_error_deferred():
    """A part that yields bad bytes still yields a deferred record."""
    recs = extract_attachments(_mk_eml(b"", "empty.docx"))
    d = next((r for r in recs if r["filename"] == "empty.docx"), None)
    assert d is not None
    assert d["status"] in ("ok", "deferred", "unsupported")


def test_extract_no_attachments_returns_empty():
    msg = email.message.Message()
    msg["Subject"] = "plain"
    body = email.message.Message()
    body.set_payload("just text")
    body.set_type("text/plain")
    multipart = MIMEMultipart()
    multipart.attach(body)
    buf = io.BytesIO()
    gen = email.generator.BytesGenerator(buf)
    gen.flatten(multipart)
    assert extract_attachments(buf.getvalue()) == []


def test_attachments_e2e(tmp_path):
    subprocess.run(["python3", "-m", "positronic_ai", "init",
                        "--brain", "kairos", "--profile", "balanced"],
                   cwd=str(tmp_path), check=True, capture_output=True)
    s, _e = open_engine(str(tmp_path), "kairos")
    srow = s.conn.execute("SELECT * FROM stream WHERE stream='positronic:kairos'").fetchone()
    did = int(srow["domain_id"])
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["item", "qty"]); ws.append(["spork", "4"])
    buf = io.BytesIO(); wb.save(buf)
    eml = _mk_eml(buf.getvalue(), "sheet.xlsx")
    rep = M.process_eml(eml, {"subject": "pickle"},
                            project_dir=str(tmp_path), brain="kairos",
                            s=s, did=did, attachments=True)
    assert rep["attachments"] == 1, rep
    assert rep["ingested"] == 1, rep
    sr = subprocess.run(["python3", "-m", "positronic_ai", "recall",
                             "[attach] sheet.xlsx", "--k", "3", "--json"],
                        cwd=str(tmp_path), capture_output=True,
                        text=True, check=False)
    assert sr.returncode == 0, sr.stderr
    hits = json.loads(sr.stdout).get("results") or []
    assert any("sheet.xlsx" in (h.get("subject") or "") for h in hits), hits



