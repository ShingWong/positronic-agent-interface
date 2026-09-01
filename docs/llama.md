# Llama Setup — 3 Tiers (no auto-build of llama.cpp)

> Global constraint: no auto-building `llama.cpp` — docs are copy-paste.

## Tier 1 — Lexical only (0 deps) ✓

No install. `positronic init --embed lexical` uses FTS5 (0.5ms) + recency.
Always works: `positronic doctor` → `lexical: ok`.

```bash
positronic init --embed lexical
positronic doctor
```

## Tier 2 — Remote API (30ms, no local build)

Set hosted embedding endpoint + key, then init:

```bash
export OPENAI_API_KEY=sk-...
# or hosted BGE-M3 / nomic
export REMOTE_EMBED_URL=https://api.openai.com/v1
positronic init --embed remote --base-url $REMOTE_EMBED_URL
# config: .positronic/config.json → embed.remote_url / remote_key
```

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
