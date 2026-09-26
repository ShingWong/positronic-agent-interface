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

Bucket default retention (compliance 7y) applies automatically; we read
it back via head_object as proof. All errors propagate — the caller
ingest endpoint catches everything so archival never fails an ingest.
"""
import hashlib
import json
import mimetypes
import os
import re
from datetime import datetime, timezone

SAFE = re.compile(r"[^A-Za-z0-9@._-]+")


def _slug(s: str, limit: int = 120) -> str:
    s = (s or "").strip().strip("<>").strip()
    return SAFE.sub("_", s).strip("_")[:limit] or "noid"


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


def archive_mail(*, brain: str, message_id: str = "", sender: str = "",
                 subject: str = "", date: str = "", body: str = "",
                 episode_id: str = "", tau=None,
                 attachments: list | None = None) -> dict:
    """PUT envelope + raw attachments. Returns bucket/keys/retention proof."""
    s3, bucket = _client()
    now = datetime.now(timezone.utc)
    leaf = _slug(message_id) if message_id else f"ep-{_slug(episode_id, 60)}"
    base = f"{_slug(brain, 40)}/{now:%Y}/{now:%m}/{leaf}"
    att_keys: list[str] = []
    for i, (fname, data) in enumerate(attachments or []):
        if not data:
            continue
        key = f"{base}/attachments/{i:02d}-{_slug(str(fname), 80)}"
        ctype, _ = mimetypes.guess_type(str(fname))
        s3.put_object(Bucket=bucket, Key=key, Body=bytes(data),
                      ContentType=ctype or "application/octet-stream",
                      Metadata={"brain": _slug(brain, 40),
                                "message-id": (message_id or "")[:256]})
        att_keys.append(key)
    envelope = {
        "brain": brain, "message_id": message_id, "sender": sender,
        "subject": subject, "date": date, "episode_id": episode_id,
        "tau": tau, "archived_at": now.isoformat(),
        "body_chars": len(body or ""), "body": body or "",
        "attachments": att_keys,
        "sha256": hashlib.sha256((body or "").encode("utf-8")).hexdigest(),
    }
    env_key = f"{base}/envelope.json"
    s3.put_object(Bucket=bucket, Key=env_key,
                  Body=json.dumps(envelope, ensure_ascii=False).encode("utf-8"),
                  ContentType="application/json")
    head = s3.head_object(Bucket=bucket, Key=env_key)
    return {"archived": True, "bucket": bucket, "key": env_key,
            "attachments": att_keys,
            "lock_mode": head.get("ObjectLockMode"),
            "retain_until": str(head.get("ObjectLockRetainUntilDate", ""))}
