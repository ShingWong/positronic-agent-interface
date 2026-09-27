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
# proprietary Commercial License Waiver issued by the copyright 
# holder, completely exempt from the network-use copyleft restrictions of 
# the AGPLv3 Section 13.
#
# This program is distributed in the hope that it will be useful, but 
# WITHOUT ANY WARRANTY; without even the implied warranty of 
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU 
# Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License 
# along with this program. If not, see <https://gnu.org>.
# =====================================================================

# tests/test_archive.py — S3 WORM archive, with a stub client (no SDK/network).
import json
from datetime import datetime, timedelta, timezone

import pytest

from positronic_ai import archive as ar


class StubS3:
    """Records PUTs and replays a scripted lock state per object."""

    def __init__(self, lock=("COMPLIANCE", 365), unlocked_keys=()):
        self.lock = lock
        self.unlocked_keys = set(unlocked_keys)
        self.puts: dict[str, dict] = {}
        self.headed: list[str] = []

    def put_object(self, *, Bucket, Key, Body, **kw):
        self.puts[Key] = {"body": Body, **kw}

    def head_object(self, *, Bucket, Key):
        self.headed.append(Key)
        if Key in self.unlocked_keys or self.lock is None:
            return {"ContentLength": len(self.puts.get(Key, {}).get("body", b""))}
        mode, days = self.lock
        until = datetime.now(timezone.utc) + timedelta(days=days)
        return {"ContentLength": len(self.puts.get(Key, {}).get("body", b"")),
                "ObjectLockMode": mode,
                "ObjectLockRetainUntilDate": until}


@pytest.fixture
def s3(monkeypatch):
    stub = StubS3()
    monkeypatch.setattr(ar, "_client", lambda: (stub, "mail-archive"))
    return stub


def _mail(**kw):
    base = {"brain": "postronic", "message_id": "<m1@example.com>",
            "body": "hello", "date": "Wed, 16 Sep 2026 10:00:00 +0000"}
    base.update(kw)
    return base


# --- the compliance claim: a lock must be proven, not assumed -------------

def test_unlocked_bucket_is_not_reported_as_archived(s3):
    """The bug this guards: archived was hardcoded True, so a bucket with no
    Object Lock looked like a compliance archive."""
    s3.lock = None
    out = ar.archive_mail(**_mail())
    assert out["archived"] is False
    assert out["envelope_locked"] is False
    assert "ObjectLockMode" in out["lock_proof"]


def test_locked_bucket_is_reported_as_archived(s3):
    out = ar.archive_mail(**_mail())
    assert out["archived"] is True
    assert out["lock_mode"] == "COMPLIANCE"
    assert out["envelope_locked"] is True


def test_expired_retention_is_not_immutable(s3):
    s3.lock = ("GOVERNANCE", -1)          # retain-until already in the past
    out = ar.archive_mail(**_mail())
    assert out["archived"] is False
    assert "expired" in out["lock_proof"]


def test_every_attachment_is_lock_proved(s3):
    """Attachments are the payloads the archive exists to preserve; an
    envelope-only proof left them unverified."""
    out = ar.archive_mail(**_mail(attachments=[("a.txt", b"one"),
                                               ("b.txt", b"two")]))
    assert out["archived"] is True
    assert len(out["att_locks"]) == 2
    for key in out["attachments"]:
        assert key in s3.headed, key


def test_unlocked_attachment_fails_the_whole_set(s3):
    """An unlocked attachment must sink the whole set: a partially immutable
    archive is not a compliance archive."""
    probe = ar.archive_mail(**_mail(attachments=[("a.txt", b"one")]))
    att_key = probe["attachments"][0]
    s3.unlocked_keys.add(att_key)          # attachment loses its lock only
    out = ar.archive_mail(**_mail(attachments=[("a.txt", b"one")]))
    assert out["envelope_locked"] is True
    assert out["att_locks"][0]["locked"] is False
    assert out["archived"] is False


def test_attachments_headed_even_when_envelope_locked(s3):
    out = ar.archive_mail(**_mail(attachments=[("a.txt", b"one")]))
    headed = set(s3.headed)
    assert out["key"] in headed
    assert all(k in headed for k in out["attachments"])


# --- key hygiene: attacker-controlled ids and filenames --------------------

@pytest.mark.parametrize("raw", ["..", ".", "../..", "a/../b", "..."])
def test_slug_is_never_a_traversal_token(raw):
    slug = ar._slug(raw)
    assert slug not in (".", "..")
    assert "/" not in slug and "\\" not in slug


def test_traversal_message_id_cannot_escape_the_brain_prefix(s3):
    out = ar.archive_mail(**_mail(message_id=".."))
    assert ".." not in out["key"].split("/")
    assert out["key"].startswith("postronic/")


def test_metadata_is_ascii_only(s3):
    """botocore raises ParamValidationError on non-ASCII metadata, which cost
    us the entire archival (the caller swallows all errors)."""
    ar.archive_mail(**_mail(message_id="<wärter-Ünïcode@example.com>"),
                    attachments=[("résumé.pdf", b"%PDF-1.4")])
    for put in s3.puts.values():
        for value in (put.get("Metadata") or {}).values():
            value.encode("ascii")          # raises if not ASCII


def test_truncated_slugs_cannot_collide(s3):
    """Two ids sharing a 120-char prefix used to land on one key."""
    a = ar.archive_mail(**_mail(message_id="A" * 200 + "-one"))
    b = ar.archive_mail(**_mail(message_id="A" * 200 + "-two"))
    assert a["key"] != b["key"]


def test_key_period_comes_from_the_message_date(s3):
    out = ar.archive_mail(**_mail(date="Wed, 16 Sep 2026 10:00:00 +0000"))
    assert "/2026/09/" in out["key"]
    # a re-archive of the same mail is idempotent, not a second copy
    again = ar.archive_mail(**_mail(date="Wed, 16 Sep 2026 23:00:00 +0000"))
    assert again["key"] == out["key"]


def test_unparsable_date_falls_back_to_archive_time(s3):
    out = ar.archive_mail(**_mail(date="not a date"))
    assert out["key"].startswith("postronic/")
    assert len(out["key"].split("/")) == 5


# --- content fidelity ------------------------------------------------------

def test_zero_byte_attachment_is_archived(s3):
    """`if not data` used to drop a legitimate empty file while still
    reporting the attachment list as complete."""
    out = ar.archive_mail(**_mail(attachments=[("empty.txt", b"")]))
    assert len(out["attachments"]) == 1
    assert out["archived"] is True
    env = json.loads(s3.puts[out["key"]]["body"])
    assert len(env["attachments"]) == 1


def test_oversized_attachment_is_skipped_and_reported(s3, monkeypatch):
    monkeypatch.setattr(ar, "MAX_ATTACHMENT_BYTES", 16)
    monkeypatch.setattr(ar, "MAX_TOTAL_BYTES", 32)
    out = ar.archive_mail(**_mail(attachments=[("big.bin", b"x" * 64),
                                               ("ok.txt", b"small")]))
    assert [s["reason"] for s in out["skipped"]] == ["over cap"]
    assert len(out["attachments"]) == 1


def test_attachment_digests_are_recorded(s3):
    import hashlib
    out = ar.archive_mail(**_mail(attachments=[("a.txt", b"one")]))
    env = json.loads(s3.puts[out["key"]]["body"])
    assert env["att_digests"] == [hashlib.sha256(b"one").hexdigest()]
    assert env["att_digests"] == out["att_digests"]


def test_envelope_hashes_the_body(s3):
    import hashlib
    out = ar.archive_mail(**_mail(body="hello"))
    env = json.loads(s3.puts[out["key"]]["body"])
    assert env["sha256"] == hashlib.sha256(b"hello").hexdigest()


# --- configuration ---------------------------------------------------------

def test_missing_credentials_raise(monkeypatch):
    monkeypatch.delenv("POSITRONIC_S3_ACCESS_KEY", raising=False)
    monkeypatch.delenv("POSITRONIC_S3_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError):
        ar._client()
