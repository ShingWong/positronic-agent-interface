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

"""S3 WORM archive — immutable copy of every ingested mail + raw attachments.

Config via env (see positronic-server.service EnvironmentFile):
  POSITRONIC_S3_ENDPOINT   (default http://127.0.0.1:9002, minio-archive)
  POSITRONIC_S3_BUCKET     (default mail-archive, Object Lock compliance)
  POSITRONIC_S3_ACCESS_KEY / POSITRONIC_S3_SECRET_KEY (no default)

Bucket default retention (compliance 7y) applies automatically. Every object
we write is read back with head_object and the lock is *verified* — mode
present, retain-until in the future — for the envelope and for every
attachment. ``archived`` is True only when the whole set is proven immutable,
so a bucket without Object Lock can never be reported as a compliance archive.

All errors propagate — the caller ingest endpoint catches everything so
archival never fails an ingest.
"""
import hashlib
import json
import mimetypes
import os
import re
from datetime import datetime, timezone

SAFE = re.compile(r"[^A-Za-z0-9@._-]+")

# Per-attachment and per-mail upload bounds. Archival is best-effort and must
# never turn into an OOM or a long ingest stall, so oversized parts are skipped
# and reported rather than buffered whole.
MAX_ATTACHMENT_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024


def _slug(s: str, limit: int = 120) -> str:
    """Filesystem-safe path segment. Never returns "." or "..".

    S3 keys are opaque strings, but restore/sync tooling (mc cp, s3fs) turns
    them back into paths, so a segment that reads as a traversal token must
    never reach the key. message_id and filenames come from remote senders.
    """
    s = (s or "").strip().strip("<>").strip()
    s = SAFE.sub("_", s).strip("._")[:limit]
    s = s.strip("._")
    return s or "noid"


def _leaf(message_id: str, episode_id: str) -> str:
    """Readable, collision-proof leaf segment.

    _slug truncates, so two long ids sharing a prefix would otherwise land on
    one key and silently overwrite each other. The digest of the full id keeps
    the key readable while making that impossible.
    """
    raw = (message_id or "").strip() or (episode_id or "").strip()
    base = (_slug(message_id, 80) if message_id
            else f"ep-{_slug(episode_id, 48)}")
    if not raw:
        return base
    return f"{base}-{hashlib.sha256(raw.encode('utf-8', 'replace')).hexdigest()[:12]}"


def _period(date: str, fallback: datetime) -> tuple[str, str]:
    """<YYYY>/<MM> from the message's own date when we can parse it.

    Keying on archive time instead would let a re-archive of the same message
    on a later day create a second immutable copy instead of being idempotent.
    """
    if date:
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(date)
            if dt is not None:
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return f"{dt:%Y}", f"{dt:%m}"
        except (TypeError, ValueError, IndexError, OverflowError):
            return f"{fallback:%Y}", f"{fallback:%m}"   # bad Date, not fatal
    return f"{fallback:%Y}", f"{fallback:%m}"


def _client():
    import boto3

    endpoint = os.environ.get("POSITRONIC_S3_ENDPOINT",
                              "http://127.0.0.1:9002")
    access = os.environ.get("POSITRONIC_S3_ACCESS_KEY", "")
    secret = os.environ.get("POSITRONIC_S3_SECRET_KEY", "")
    if not access or not secret:
        raise RuntimeError("s3-unconfigured (need ACCESS_KEY/SECRET_KEY)")
    return boto3.client("s3", endpoint_url=endpoint,
                        aws_access_key_id=access,
                        aws_secret_access_key=secret,
                        region_name="us-east-1"), \
        os.environ.get("POSITRONIC_S3_BUCKET", "mail-archive")


def _lock_proof(head: dict, now: datetime | None = None) -> tuple[bool, str]:
    """Is this object actually under an unexpired Object Lock?

    A bucket without Object Lock simply omits the lock fields, so a HEAD that
    "succeeded" proves nothing. Both a mode and a future retain-until date are
    required before we call an object immutable.
    """
    mode = head.get("ObjectLockMode")
    if not mode:
        return False, "no ObjectLockMode: bucket is not Object-Lock enabled"
    until = head.get("ObjectLockRetainUntilDate")
    if until is None:
        return False, "no ObjectLockRetainUntilDate: nothing retains this object"
    if not isinstance(until, datetime):
        return False, f"unparsable ObjectLockRetainUntilDate: {until!r}"
    now = now or datetime.now(timezone.utc)
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    if until <= now:
        return False, f"retention expired at {until.isoformat()}: object is mutable"
    return True, f"{mode} until {until.isoformat()}"


def archive_mail(*, brain: str, message_id: str = "", sender: str = "",
                 subject: str = "", date: str = "", body: str = "",
                 episode_id: str = "", tau=None,
                 attachments: list | None = None) -> dict:
    """PUT envelope + raw attachments, then prove every object is locked.

    Returns bucket/keys/retention proof. ``archived`` is True only when the
    envelope and every attachment came back with a verified, unexpired lock.
    """
    s3, bucket = _client()
    now = datetime.now(timezone.utc)
    year, month = _period(date, now)
    base = f"{_slug(brain, 40)}/{year}/{month}/{_leaf(message_id, episode_id)}"
    att_keys: list[str] = []
    att_digests: list[str] = []
    skipped: list[dict] = []
    total = 0
    for i, (fname, data) in enumerate(attachments or []):
        if data is None:
            continue
        size = len(data)
        if size > MAX_ATTACHMENT_BYTES or total + size > MAX_TOTAL_BYTES:
            skipped.append({"name": _slug(str(fname), 80), "bytes": size,
                            "reason": "over cap"})
            continue
        key = f"{base}/attachments/{i:02d}-{_slug(str(fname), 80)}"
        ctype, _ = mimetypes.guess_type(str(fname))
        s3.put_object(Bucket=bucket, Key=key, Body=bytes(data),
                      ContentType=ctype or "application/octet-stream",
                      # Metadata rides in an HTTP header, so it must be ASCII:
                      # botocore rejects a non-ASCII value outright, which would
                      # cost us the whole archival. The key is already slugged;
                      # the full value is preserved in the envelope.
                      Metadata={"brain": _slug(brain, 40),
                                "message-id": _slug(message_id, 256)})
        att_keys.append(key)
        att_digests.append(hashlib.sha256(bytes(data)).hexdigest())
        total += size
    envelope = {
        "brain": brain, "message_id": message_id, "sender": sender,
        "subject": subject, "date": date, "episode_id": episode_id,
        "tau": tau, "archived_at": now.isoformat(),
        "body_chars": len(body or ""), "body": body or "",
        "attachments": att_keys,
        "att_digests": att_digests,
        "skipped": skipped,
        "sha256": hashlib.sha256((body or "").encode("utf-8")).hexdigest(),
    }
    env_key = f"{base}/envelope.json"
    s3.put_object(Bucket=bucket, Key=env_key,
                  Body=json.dumps(envelope, ensure_ascii=False).encode("utf-8"),
                  ContentType="application/json")
    head = s3.head_object(Bucket=bucket, Key=env_key)
    env_locked, env_why = _lock_proof(head, now)
    att_locks = []
    for key in att_keys:
        ok, why = _lock_proof(s3.head_object(Bucket=bucket, Key=key), now)
        att_locks.append({"key": key, "locked": ok, "why": why})
    all_locked = env_locked and all(a["locked"] for a in att_locks)
    return {"archived": all_locked,
            "bucket": bucket, "key": env_key,
            "attachments": att_keys,
            "att_digests": att_digests,
            "skipped": skipped,
            "envelope_locked": env_locked,
            "lock_proof": env_why,
            "att_locks": att_locks,
            "lock_mode": head.get("ObjectLockMode"),
            "retain_until": str(head.get("ObjectLockRetainUntilDate", ""))}
