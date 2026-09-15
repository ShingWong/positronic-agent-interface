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

"""Chunked embedding against llama.cpp bge-m3 (:8090). Single requests cap
at ~2048 tokens (measured HTTP 500 'too large to process'): pre-split into
~1200-token chunks, mean-pool to one vector (schema keeps single body_embed),
halve-and-resend ONLY on the size-error message, bounded retries, loud
failure (never silent — the old best-effort swallow hid FTS-only episodes).
"""
import json
import urllib.error
import urllib.request

CEIL_TOKENS = 2048
CHUNK_TOKENS = 1200
CHARS_PER_TOKEN = 6
MAX_HALVINGS = 4
_SIZE_ERR = "too large to process"


class _TooLarge(Exception):
    pass


def _post_embedding(text: str, url: str, timeout: int = 180) -> list[float]:
    body = json.dumps({"content": text}).encode()
    last_err: Exception | None = None
    for u in _as_url_list(url):
        req = urllib.request.Request(u.rstrip("/") + "/embedding", data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            d = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
            emb = d[0]["embedding"]
            return emb[0] if isinstance(emb[0], list) else emb
        except urllib.error.HTTPError as e:
            msg = e.read()[:300].decode("utf-8", "replace")
            if e.code == 500 and _SIZE_ERR in msg:
                raise _TooLarge(msg) from None
            last_err = RuntimeError(f"embedding HTTP {e.code}: {msg}")
            continue
        except Exception as e:  # noqa: BLE001 (try next URL)
            last_err = e
            continue
    raise RuntimeError(f"embedding failed on all urls: {last_err}") from None


def _as_url_list(url) -> list[str]:
    """Accept one URL or a list; split strings on comma/space."""
    if isinstance(url, (list, tuple)):
        return [str(u).strip() for u in url if str(u).strip()]
    return [u for u in str(url).replace(",", " ").split() if u]


def _halve(text: str) -> tuple[str, str]:
    cut = len(text) // 2
    cut = text.rfind(" ", 0, cut)
    cut = cut if cut > 0 else len(text) // 2
    return text[:cut], text[cut:].strip()


def _embed_halving(text: str, url: str, timeout: int = 180) -> list[float]:
    queue, vecs = [(text, 0)], []
    while queue:
        t, depth = queue.pop(0)
        try:
            vecs.append(_post_embedding(t, url, timeout))
        except _TooLarge:
            a, b = _halve(t)
            if depth > MAX_HALVINGS or len(a) < 200 or len(b) < 200:
                raise RuntimeError(
                    f"embedding still too large after {depth + 1} halvings") from None
            queue = [(a, depth + 1), (b, depth + 1)] + queue
    dim = len(vecs[0])
    return [sum(v[i] for v in vecs) / len(vecs) for i in range(dim)]


def embed_texts(texts: list[str], url: str) -> list[list[float]]:
    return [_embed_halving(t, url) for t in texts]


def embed_one(text: str, url: str) -> tuple[list[float], int]:
    from .chunk import chunk_markdown
    chunks = chunk_markdown(text, max_chars=CHUNK_TOKENS * CHARS_PER_TOKEN)
    vecs = embed_texts(chunks, url)
    dim = len(vecs[0])
    mean = [sum(v[i] for v in vecs) / len(vecs) for i in range(dim)]
    return mean, len(vecs)
