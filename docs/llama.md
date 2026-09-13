# Llama Setup — 3 Tiers (no auto-build of llama.cpp)

> Global constraint: no auto-building `llama.cpp` — docs are copy-paste.

## Tier 1 — Lexical only (0 deps) ✓

No install. `positronic init --embed lexical` uses FTS5 (0.5ms) + recency.
Always works: `positronic doctor` → `lexical: ok`.

```bash
positronic init --embed lexical
positronic doctor
```

## Tier 2 — Embedding endpoint tiers: `local` vs `remote`

A bge-m3 server anywhere on the LAN counts as **`local`** — the tier names the
binding protocol, not the process location. `engine.open_engine` binds
`embed_one` (llama.cpp `/embedding`, served per Tier 3) for brains whose config
says `embed: local`:

```bash
positronic init --brain mail --profile long_term --embed local
positronic config local_url http://<host>:8090    # default http://127.0.0.1:8090
```

`remote` is API-key-style hosted embedding only (`embed.remote_url` +
`embed.remote_key` in `.positronic/config.json`; `config` masks the key without
`--show-secrets`). As of this release no embedder binds for `remote` brains —
they encode FTS-only until an API embedder lands.

Chunking at bind time: `embed_one` pre-splits with `chunk_markdown` to ~1200
tokens (~7200 chars) and mean-pools the pieces into the single `body_embed`
vector. llama.cpp caps requests at 2048 tokens (measured: HTTP 500 "too large
to process"; fitted leaf ~6.2k chars) — oversized pieces are halved-and-resent,
up to 5 levels, then it raises loudly. `embedded: true` in an ingest result
means "embedder bound", not "vector present" (memeng's embedder call is
best-effort).

## Tier 3 — Local BGE-M3 (recommended, 18–35ms) ⭐

### 1) Install llama.cpp

```bash
# apt (if available)
sudo apt install llama.cpp
# or build (HIP/CUDA notes — see link):
git clone https://github.com/ggml-org/llama.cpp && cmake -B build -DGGML_HIP=ON && cmake --build build -j
# verify
llama-server --version
# or shim used on this box:
/home/swong/dls/.tmp/beellama-check/build-hip/bin/llama-server --version
```

See `llama.config:4` pattern: `LLAMA_BIN` + `GGML_CUDA_DISABLE_GRAPHS=1`.

### 2) Model — bge-m3-Q8_0.gguf (606MB)

```bash
mkdir -p /usr/local/devel/models/embedding
curl -L https://huggingface.co/BAAI/bge-m3/resolve/main/bge-m3-Q8_0.gguf \
  -o /usr/local/devel/models/embedding/bge-m3-Q8_0.gguf
sha256sum /usr/local/devel/models/embedding/bge-m3-Q8_0.gguf
# compare with published hash
```

### 3) Service — bge-embed.service

```bash
sudo cp docs/bge-embed.service /etc/systemd/system/bge-embed.service
sudo systemctl daemon-reload
sudo systemctl enable --now bge-embed.service
# check
systemctl status bge-embed --no-pager | head -n 20
```

Proven unit (2026-08-28, 262MB, pooling `cls` not `mean`, `Restart=always`):

```
ExecStart=/home/swong/dls/.tmp/beellama-check/build-hip/bin/llama-server \
  -m /usr/local/devel/models/embedding/bge-m3-Q8_0.gguf \
  --embedding --pooling cls --host 127.0.0.1 --port 8090 -c 8192
Restart=always
RestartSec=3
```

### 4) Verify

```bash
curl -s http://127.0.0.1:8090/health | grep ok && echo "bge up"
curl -s http://127.0.0.1:8090/v1/embeddings -X POST -H 'Content-Type: application/json' \
  -d '{"input":"hello"}' | head -c 80
positronic doctor  # expects { lexical: ok, bge: ok, llama: ok, engram: ok }
python3 -c "import sys; sys.path.insert(0,'positronic-engram/engine/src'); from memeng.store import SQLiteStore; print('engram ok')"
```

### 5) Troubleshoot

```bash
journalctl -u bge-embed -n 50 --no-pager
# pooling cls vs mean warning → use `cls` (this unit does)
# HIP vs CPU → unit runs CPU by default; add `--gpu` flags if ROCm
# port conflict :8090 → ss -tlnp | grep 8090
```

## Doctor

```bash
positronic doctor         # human-readable
positronic doctor --json  # { tiers: { lexical, bge, llama, engram } }
```

<!--
Licensed under the GNU General Public License, version 3 or later (GPL-3.0-or-later).
Copyright (C) 2026 Shing Wong. All Rights Reserved.
See LICENSE for the full license text.
-->
