// =====================================================================
// Project Positronic — Polytemporal Cognitive Engram Memory Substrate
// Copyright (C) 2026 Shing Wong. All Rights Reserved.
// =====================================================================
// This program is DUAL-LICENSED. You may redistribute and/or modify it 
// under the terms of the GNU Affero General Public License as published by the 
// Free Software Foundation, either version 3 of the License, or (at your 
// option) any later version.
//
// Alternatively, commercial entities, multi-tenant instances, and Managed 
// Service Providers (MSPs) may utilize this program under a separate, 
// proprietary Commercial License Waiver issued directly by the copyright 
// holder, completely exempt from the network-use copyleft restrictions of 
// the AGPLv3 Section 13.
//
// This program is distributed in the hope that it will be useful, but 
// WITHOUT ANY WARRANTY; without even the implied warranty of 
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU 
// Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License 
// along with this program. If not, see <https://gnu.org>.
// =====================================================================

// PAI core — local brain store.
//
// The storage engine is a port (see db.ts). The default is sqlite-wasm with
// FTS5; a host may supply another — engine-turso.ts is the worked example —
// which is what pai-core's "hosts provide storage" contract has always meant.
//
// OPFS persistence when available (worker + sync handle), in-memory fallback
// otherwise. One writer: callers serialize writes through a single worker
// (OPFS exclusive-lock constraint).
//
// Schema mirrors the server brain at query time: episodes carry
// subject/snippet/body/threat/message_id/sender/tau/wall as columns,
// features_json kept for forward-compat with server-shaped hits.

import type { ThreatTag } from "./threat.js";
import { normalizeMessageId } from "./messageId.js";
import { scoreThreat } from "./threat.js";
import { detectTable } from "./tables.js";
import type { BrainDb, BrainEngine } from "./db.js";
import { sqliteWasmEngine } from "./engine-sqlite.js";

export interface LocalEpisode {
  episodeId: string;
  subject: string;
  body: string;
  sender?: string;
  messageId?: string;
  threatTag: ThreatTag;
  threatReasons?: string;
  visionRestructured?: boolean;
  tableSig?: string;
  tau: number;
  wall: string;
}

export interface RecallHit {
  episode_id: string;
  subject: string;
  snippet: string;
  message_id: string;
  sender: string;
  threat_tag: ThreatTag;
  tau: number;
  wall: string;
  rrf_score: number;
}

function uuid(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

export class LocalBrain {
  private db: BrainDb | null = null;
  private tau = 0;
  uuid = "";
  readonly backend: string = "none";
  private readonly engine: BrainEngine;

  constructor(engine: BrainEngine = sqliteWasmEngine) {
    this.engine = engine;
  }

  /** Open the brain. Call once. Default engine: sqlite-wasm (OPFS if available). */
  async open(name = "positronic", wasmUrl?: string): Promise<string> {
    const { db, backend } = await this.engine.open(name, {
      wasmUrl,
      load: (u) => this.loadWasm(u),
    });
    this.db = db;
    (this as { backend: string }).backend = backend;
    this.db.exec(this.engine.dialect.schema());
    const row = this.db.selectValue("SELECT MAX(tau) FROM episode");
    this.tau = typeof row === "number" ? row : 0;
    // Stable brain identity, same contract as the server (meta.brain_uuid).
    let id = null;
    try {
      id = this.db.selectValue("SELECT v FROM _meta WHERE k='brain_uuid'");
    } catch {
      id = null;
    }
    if (!id) {
      id = uuid();
      this.db.exec({
        sql: "INSERT OR IGNORE INTO _meta(k, v) VALUES('brain_uuid', ?)",
        bind: [id],
      });
    }
    this.uuid = String(id);
    return this.backend;
  }

  // Overridden in tests to inject a mock; the default loads the wasm bundle.
  // The specifier is resolved by the host: bundlers rewrite it, the
  // Thunderbird adapter substitutes the vendored build (see pai-local.js).
  // Only the sqlite-wasm engine calls this (see engine-sqlite.ts).
  protected async loadWasm(wasmUrl?: string): Promise<unknown> {
    try {
      const mod = await import(
        /* @vite-ignore */ wasmUrl || "@sqlite.org/sqlite-wasm"
      );
      return mod.default ? await mod.default() : mod;
    } catch {
      return null;
    }
  }

  close(): void {
    try {
      this.db?.close();
    } catch {
      /* already closed */
    }
    this.db = null;
  }

  private nextTau(): number {
    this.tau = Math.round((this.tau + 0.1) * 10) / 10;
    return this.tau;
  }

  ingest(
    text: string,
    opts: {
      subject?: string;
      sender?: string;
      date?: string;
      messageId?: string;
      visionBody?: string;
      visionUsed?: boolean;
    } = {},
  ): { episode_id: string; tau: number; duplicate: boolean; threat: ThreatTag } {
    if (!this.db) throw new Error("brain not open");
    const mid = normalizeMessageId(opts.messageId);
    if (mid) {
      const dup = this.db.selectValue("SELECT id FROM episode WHERE message_id = ? LIMIT 1", [mid]);
      if (dup) return { episode_id: String(dup), tau: 0, duplicate: true, threat: "clean" };
    }
    const subj = opts.subject || text.slice(0, 80);
    const body = opts.visionBody ?? text;
    const verdict = opts.sender
      ? scoreThreat(opts.sender, subj, body, this.senderCount(opts.sender))
      : { tag: "clean" as ThreatTag, reasons: [] as string[] };
    const [, sig] = detectTable(text);
    const id = uuid();
    const tau = this.nextTau();
    const wall = new Date().toISOString();
    const features = {
      subject_norm: subj,
      body_text: body,
      sender: opts.sender || "",
      message_id: mid,
      threat_tag: verdict.tag,
      threat_reasons: verdict.reasons,
      table_sig: sig,
      ...(opts.visionUsed ? { vision_restructured: true, body_raw: text } : {}),
    };
    this.db.exec({
      sql: `INSERT INTO episode
        (id, subject, body, sender, message_id, threat_tag, threat_reasons,
         vision_restructured, table_sig, features_json, tau, wall)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)`,
      bind: [
        id, subj, body, opts.sender || "", mid, verdict.tag,
        JSON.stringify(verdict.reasons), opts.visionUsed ? 1 : 0,
        JSON.stringify(sig), JSON.stringify(features), tau, wall,
      ],
    });
    return { episode_id: id, tau, duplicate: false, threat: verdict.tag };
  }

  recall(queryText: string, k = 10): { results: RecallHit[] } {
    if (!this.db) throw new Error("brain not open");
    const q = queryText.replace(/["*]/g, " ").trim();
    if (!q) return { results: [] };
    return {
      results: this.engine.dialect.recall(this.db, q, k).map((r, i) => ({
        episode_id: r.id,
        subject: r.subject,
        snippet: r.body.slice(0, 200),
        message_id: r.message_id,
        sender: r.sender,
        threat_tag: (r.threat_tag as ThreatTag) || "clean",
        tau: r.tau,
        wall: r.wall,
        rrf_score: Math.round((1 / (60 + i + 1)) * 10000) / 10000,
      })),
    };
  }

  count(): number {
    if (!this.db) return 0;
    return Number(this.db.selectValue("SELECT COUNT(*) FROM episode")) || 0;
  }

  private senderCount(sender: string): number {
    try {
      return (
        Number(
          this.db?.selectValue("SELECT COUNT(*) FROM episode WHERE sender = ?", [sender]),
        ) || 0
      );
    } catch {
      return 0;
    }
  }
}
