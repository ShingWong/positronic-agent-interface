# S3 WORM Archive — ops runbook (ai-test, 2026-09-24)

MinIO holds the immutable mail copy; the brain holds the searchable copy.
Postgres (web2 `archive_volumes`) holds only the endpoint registry —
no credentials there.

## Topology

| Instance | API | Console | Data bind | Size | Bucket | Retention |
|---|---|---|---|---|---|---|
| `minio-test` | `:9000` | `:9001` | `/srv/s3-test/minio` | 2.0T (`/dev/sdc`) | `mail-archive-test` | GOVERNANCE 30d |
| `minio-archive` | `:9002` | `:9003` | `/srv/s3-archive/minio` | 4.0T (`/dev/sda1`) | `mail-archive` | COMPLIANCE 7y |

- Docker containers (image `quay.io/minio/minio:latest`,
  `restart unless-stopped`, `server /data --console-address :9001`).
  Data survives container recreate (bind mounts).
- Both buckets: Object Lock enabled at creation + versioning on.
  Lock can only be set at `mb --with-lock` time — to change mode,
  empty the bucket, `rb`, re-`mb`.

## Credentials

- Root user `minioadmin`. Password: `/home/swong/.minio-root-pw`
  (mode 600, ai-test only). Rotated 2026-09-22 (was `CHANGE-ME-...`).
- PAI runtime copy: `~/.config/positronic-s3.env` (mode 600),
  loaded via `EnvironmentFile=` in `positronic-server.service`:
  `POSITRONIC_S3_ENDPOINT` (= `http://127.0.0.1:9002`),
  `POSITRONIC_S3_BUCKET` (= `mail-archive`),
  `POSITRONIC_S3_ACCESS_KEY` / `POSITRONIC_S3_SECRET_KEY`.
- `mc` = apt `minio-client` + symlink `/usr/local/bin/mc`
  (dl.min.io is dead — HTTP 410, do not use).
  Aliases `minio-test` (`:9000`) and `minio-archive` (`:9002`).

## Write path (PAI ingest → S3)

- `positronic_ai/archive.py::archive_mail` — PUTs `envelope.json`
  (sender/subject/date/body/sha256/episode/tau/attachment keys) plus
  raw attachment bytes. Bucket default retention applies automatically;
  lock mode is read back via `head_object` as proof.
- `server/app.py` `/ingest` — collects raw bytes in the existing
  decode loop, archives after a successful brain write. Duplicates and
  `live=false` skip. Every exception is caught: archival never fails
  an ingest; failures surface as `archive: {archived:false, error}`.
- Key layout: `<brain>/<YYYY>/<MM>/<message-id>/envelope.json` and
  `.../attachments/<nn>-<filename>`. Requires `boto3`
  (`pip install --user --break-system-packages boto3`).

## Procedures

- Health: `curl http://localhost:9000/minio/health/live` (`:9002` likewise);
  from web2 use `http://10.0.0.19:9000|9002/...`. Anonymous bucket
  listing returns 403 (expected — auth on).
- Verify lock: `mc stat <alias>/<bucket>` (LockConfiguration) and
  `mc retention info <alias>/<bucket>/<key>` per object.
- Rotate root: new pw to `~/.minio-root-pw`, then per container
  `docker stop/rm`, `docker run` with same ports/binds +
  `-e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=...`,
  refresh `mc alias set`, update `positronic-s3.env`, restart service.
- WORM proof (2026-09-22): plain `mc rm` on a locked object only
  writes a delete marker — versions retained; `envelope.json`
  reported `COMPLIANCE, expiring in 2556 days`.

## Warnings

- `mail-archive` is COMPLIANCE: not even root can delete before 2033.
  Prove new code against `mail-archive-test` first. The 2026-09-22
  proof objects (`s3-proof-001@local`, ~554B) are locked to 2033 —
  leave them as the permanent WORM demo.
- Historical backfill (729 episodes in `sam_sersargroup_com`) is NOT
  done — only new ingests archive. Backfill writes to compliance are
  forever; review the batch before running.
