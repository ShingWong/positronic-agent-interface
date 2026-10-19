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

// The default engine: sqlite-wasm, OPFS when available, FTS5 for recall.
// This is the behaviour LocalBrain shipped with, moved unchanged behind the
// BrainEngine port in db.ts.

import type { BrainDb, BrainDialect, BrainEngine, BrainOpenOpts, RecallRow } from "./db.js";

const SCHEMA = `
CREATE TABLE IF NOT EXISTS episode (
  id TEXT PRIMARY KEY,
  subject TEXT NOT NULL DEFAULT '',
  body TEXT NOT NULL DEFAULT '',
  sender TEXT NOT NULL DEFAULT '',
  message_id TEXT NOT NULL DEFAULT '',
  threat_tag TEXT NOT NULL DEFAULT 'clean',
  threat_reasons TEXT NOT NULL DEFAULT '[]',
  vision_restructured INTEGER NOT NULL DEFAULT 0,
  table_sig TEXT NOT NULL DEFAULT '{}',
  features_json TEXT NOT NULL DEFAULT '{}',
  tau REAL NOT NULL DEFAULT 0,
  wall TEXT NOT NULL DEFAULT ''
);
CREATE VIRTUAL TABLE IF NOT EXISTS episode_fts USING fts5(
  subject, body, sender, content='episode', content_rowid='rowid'
);
CREATE TRIGGER IF NOT EXISTS episode_ai AFTER INSERT ON episode BEGIN
  INSERT INTO episode_fts(rowid, subject, body, sender)
  VALUES (new.rowid, new.subject, new.body, new.sender);
END;
CREATE TRIGGER IF NOT EXISTS episode_ad AFTER DELETE ON episode BEGIN
  INSERT INTO episode_fts(episode_fts, rowid, subject, body, sender)
  VALUES ('delete', old.rowid, old.subject, old.body, old.sender);
END;
CREATE INDEX IF NOT EXISTS episode_mid ON episode(message_id);
CREATE TABLE IF NOT EXISTS _meta (k TEXT PRIMARY KEY, v TEXT NOT NULL);
`;

/** Coerce one raw row into a RecallRow. Shared by every dialect. */
export function toRecallRow(r: Record<string, unknown>): RecallRow {
  return {
    id: String(r.id),
    subject: String(r.subject || ""),
    body: String(r.body || ""),
    sender: String(r.sender || ""),
    message_id: String(r.message_id || ""),
    threat_tag: String(r.threat_tag || "clean"),
    tau: Number(r.tau),
    wall: String(r.wall || ""),
  };
}

export const sqliteWasmDialect: BrainDialect = {
  id: "sqlite-wasm",
  schema: () => SCHEMA,
  recall(db, query, k) {
    const rows = db.selectObjects(
      `SELECT e.id, e.subject, e.body, e.sender, e.message_id,
              e.threat_tag, e.tau, e.wall,
              bm25(episode_fts) AS rank
       FROM episode_fts f JOIN episode e ON e.rowid = f.rowid
       WHERE episode_fts MATCH ? ORDER BY rank LIMIT ?`,
      [query, k],
    );
    return rows.map(toRecallRow);
  },
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function defaultLoad(wasmUrl?: string): Promise<any> {
  try {
    const mod = await import(/* @vite-ignore */ wasmUrl || "@sqlite.org/sqlite-wasm");
    return mod.default ? await mod.default() : mod;
  } catch {
    return null;
  }
}

export const sqliteWasmEngine: BrainEngine = {
  id: "sqlite-wasm",
  dialect: sqliteWasmDialect,
  async open(name, opts: BrainOpenOpts = {}) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const sqlite3: any = await (opts.load ?? defaultLoad)(opts.wasmUrl);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let db: any = null;
    let backend = "none";
    if (sqlite3 && "opfs" in sqlite3) {
      try {
        db = new sqlite3.opfs.OpfsDb(`/${name}.db`);
        backend = "opfs";
      } catch {
        db = null;
      }
    }
    if (!db && sqlite3) {
      db = new sqlite3.oo1.DB(`/${name}.db`, "c");
      backend = "memory";
    }
    if (!db) throw new Error("sqlite-wasm unavailable");
    return { db: db as BrainDb, backend };
  },
};
