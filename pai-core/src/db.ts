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

// The storage port.
//
// pai-core's stated contract is "hosts provide storage (sqlite-wasm + OPFS)";
// this is that seam made real. Exactly two things are engine-specific:
//
//   1. the schema — SQLite uses an FTS5 external-content table kept in sync by
//      triggers; Turso has no fts5 module and maintains its own index;
//   2. the recall query — SQLite is `MATCH` + `bm25()`; Turso is
//      `fts_match(<cols>, ?)` + `fts_score(<cols>, ?)`.
//
// Everything else — the insert, message-id dedup, the counts, the `_meta` row
// — is common SQL and stays in LocalBrain.

/** The handle LocalBrain drives. Four methods: its whole surface. */
export interface BrainDb {
  exec(sql: string | { sql: string; bind?: unknown[] }): void;
  selectValue(sql: string, bind?: unknown[]): unknown;
  selectObjects(sql: string, bind?: unknown[]): Record<string, unknown>[];
  close(): void;
}

/** One recall row, before LocalBrain derives its rrf_score from the order. */
export interface RecallRow {
  id: string;
  subject: string;
  body: string;
  sender: string;
  message_id: string;
  threat_tag: string;
  tau: number;
  wall: string;
}

export interface BrainDialect {
  readonly id: string;
  /** DDL for the base table and this engine's search index. */
  schema(): string;
  /** Recall, best-first. */
  recall(db: BrainDb, query: string, k: number): RecallRow[];
}

export interface BrainOpenOpts {
  wasmUrl?: string;
  /** Loader hook, so tests can inject a fake sqlite-wasm build. */
  load?: (wasmUrl?: string) => Promise<unknown>;
}

export interface BrainEngine {
  readonly id: string;
  readonly dialect: BrainDialect;
  open(name: string, opts?: BrainOpenOpts): Promise<{ db: BrainDb; backend: string }>;
}
