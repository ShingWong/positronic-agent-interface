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

"""Chunked embedding against llama.cpp bge-m3 (:8090). Single requests cap
at ~7500 tokens (CEIL_TOKENS mirrors the server's physical batch of 8192 —
raising the batch in /etc/llama-bge.config moved the old HTTP 500 'too large
to process' wall from 2048): pre-split into ~1200-token chunks, mean-pool to
one vector (schema keeps single body_embed), halve-and-resend ONLY on the
size-error message, bounded retries, loud failure (never silent — the old
best-effort swallow hid FTS-only episodes).
"""
import json
import urllib.error
import urllib.request

CEIL_TOKENS = 7500
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


# -- embedder profiles -------------------------------------------------------
#
# Which model a brain embeds with is a per-BRAIN decision, not a global one.
# Both the task-prompt style and the native vector dimension differ between
# models, and which one wins is data-sensitive: structured log lines, mail
# prose and CVE summaries are not the same distribution. A single global
# default would be convenient and wrong, so the default here only preserves
# today's behaviour and every brain may override it.
#
# Note the prompts are DERIVED from the model, never configured separately.
# EG2 is trained on a SearchQuery/Document pair: a document embedded without
# `Document:` and a query embedded without `SearchQuery:` land in mismatched
# spaces, and retrieval silently degrades -- the failure looks like a weak
# model rather than a missing prefix. Two independently-set keys would be two
# chances to get that wrong.

EMBED_MODELS: dict[str, dict] = {
    # name -> url config key, task-prompt style, native dimension
    "bge-m3": {"url_key": "local_url", "prompts": "none", "dim": 1024},
    "eg2": {"url_key": "eg2_url", "prompts": "eg2", "dim": 768},
}

DEFAULT_EMBED_MODEL = "bge-m3"

_PROMPT_STYLES: dict[str, dict[str, str]] = {
    "eg2": {"document": "Document: ", "query": "SearchQuery: "},
}


def known_models() -> list[str]:
    return sorted(EMBED_MODELS)


def model_dim(model: str) -> int | None:
    """Native dimension for a model, or None if unconfigured."""
    spec = EMBED_MODELS.get(model)
    return int(spec["dim"]) if spec else None


def prompt_prefix(model: str, role: str) -> str:
    """Task prompt for (model, role); "" when the model takes none."""
    style = EMBED_MODELS.get(model, {}).get("prompts", "none")
    return _PROMPT_STYLES.get(style, {}).get(role, "")


def embed_one(text: str, url: str, *, role: str = "document",
              model: str = DEFAULT_EMBED_MODEL) -> tuple[list[float], int]:
    """Embed one text as `role` under `model`'s task-prompt style.

    `role` is part of the vector's provenance, not cosmetic: it selects the
    task prompt, and a vector embedded with the wrong role is silently
    unqueryable by vectors embedded with the right one.
    """
    from .chunk import chunk_markdown
    prefix = prompt_prefix(model, role)
    chunks = chunk_markdown(text, max_chars=CHUNK_TOKENS * CHARS_PER_TOKEN)
    if prefix:
        # Prefix per chunk: each chunk is embedded as its own document, and
        # an unprefixed chunk would drift out of the pair-trained space.
        chunks = [prefix + c for c in chunks]
    vecs = embed_texts(chunks, url)
    dim = len(vecs[0])
    mean = [sum(v[i] for v in vecs) / len(vecs) for i in range(dim)]
    return mean, len(vecs)


# -- multimodal --------------------------------------------------------------
#
# llama-server's /v1/embeddings accepts an OAI content array when --mmproj is
# loaded, so an image can be embedded into the SAME vector as its text -- no
# OCR bridge, no "extract text and hope it describes the picture". The text
# half still carries the task prompt; the image half does not take one.

_MM_MIMES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
    ".tif": "image/tiff", ".tiff": "image/tiff",
}


def guess_mime(name: str) -> str:
    """Best-effort mime for a filename; png when unknown."""
    ext = "." + str(name).rsplit(".", 1)[-1].lower()
    return _MM_MIMES.get(ext, "image/png")


def text_part(text: str) -> dict:
    return {"type": "text", "text": text}


def image_part(data: bytes, mime: str = "image/png") -> dict:
    """Inline image as an OAI data URL."""
    import base64
    return {"type": "image_url",
            "image_url": {"url": f"data:{mime};base64,"
                                 f"{base64.b64encode(bytes(data)).decode()}"}}


def _post_multimodal(parts: list[dict], url: str,
                     timeout: int = 300) -> list[float]:
    """Embed one content-array item. OAI shape, OAI response."""
    import urllib.error
    import urllib.request
    body = json.dumps({"input": [{"content": parts}]}).encode()
    last_err: Exception | None = None
    for u in _as_url_list(url):
        req = urllib.request.Request(u.rstrip("/") + "/v1/embeddings",
                                     data=body,
                                     headers={"Content-Type":
                                              "application/json"})
        try:
            d = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
            return list(d["data"][0]["embedding"])
        except urllib.error.HTTPError as e:
            msg = e.read()[:300].decode("utf-8", "replace")
            last_err = RuntimeError(f"multimodal embedding HTTP {e.code}: {msg}")
            continue
        except Exception as e:  # noqa: BLE001 (try next URL)
            last_err = e
            continue
    raise RuntimeError(f"multimodal embedding failed on all urls: "
                       f"{last_err}") from None


def embed_with_image(text: str, url: str, *, image: bytes | None = None,
                     mime: str = "image/png", role: str = "document",
                     model: str = DEFAULT_EMBED_MODEL) -> list[float]:
    """One vector for text plus an optional image.

    With no image this is the text path with the same task prompt, so a
    caller can use it unconditionally without the two sides diverging on
    prompt handling.

    Raises with the server's own message when --mmproj is absent, which is
    the expected failure until the EG2 server is started with the projector.
    """
    prefix = prompt_prefix(model, role)
    parts = [text_part(prefix + text if prefix else text)]
    if image:
        parts.append(image_part(image, mime))
    return _post_multimodal(parts, url)
