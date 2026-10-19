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

// Turso (the pure-Rust, SQLite-compatible engine) behind the BrainEngine port.
//
// Its FTS is NOT FTS5. Every line below was verified against
// @tursodatabase/database 0.8.3, the Node build's synchronous `./compat`
// entry, rather than taken from documentation:
//
//   - there is no `fts5` module: `CREATE VIRTUAL TABLE … USING fts5(…)` fails
//     with "no such module: fts5";
//   - the index is `CREATE INDEX <name> ON <table> USING fts (cols…)` and it
//     needs `experimental: ["index_method"]` to be enabled;
//   - the engine maintains that index, so the external-content triggers an
//     FTS5 table needs are unnecessary (and `triggers` is itself experimental);
//   - recall is `fts_match(<cols…>, ?)` — the columns are separate arguments,
//     NOT the index name. Passing the index name parses and returns silently
//     empty, which is a trap worth knowing;
//   - `bm25()` does not exist; the ranking function is `fts_score(<cols…>, ?)`.
//
// Note the binding asymmetry this engine cannot hide: the Node build exposes a
// synchronous API (`./compat`), which is why this file can satisfy the
// synchronous BrainDb port at all. The browser build
// (@tursodatabase/database-wasm) is async-only — it runs its wasm in a worker
// and bridges with Atomics/SharedArrayBuffer — so it cannot back this port.

import type { BrainDb, BrainDialect, BrainEngine, RecallRow } from "./db.js";
import { toRecallRow } from "./engine-sqlite.js";

const TURSO_SCHEMA = `
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
CREATE INDEX IF NOT EXISTS episode_fts ON episode USING fts (subject, body, sender);
CREATE INDEX IF NOT EXISTS episode_mid ON episode(message_id);
CREATE TABLE IF NOT EXISTS _meta (k TEXT PRIMARY KEY, v TEXT NOT NULL);
`;

export const tursoDialect: BrainDialect = {
  id: "turso",
  schema: () => TURSO_SCHEMA,
  recall(db, query, k) {
    const rows = db.selectObjects(
      `SELECT id, subject, body, sender, message_id, threat_tag, tau, wall,
              fts_score(subject, body, sender, ?) AS rank
       FROM episode
       WHERE fts_match(subject, body, sender, ?)
       ORDER BY rank DESC LIMIT ?`,
      [query, query, k],
    );
    return rows.map(toRecallRow);
  },
};

export interface TursoEngineOpts {
  /** Path to the database file. */
  path: string;
  /**
   * Turso features to enable. Defaults to `["index_method"]`, which its FTS
   * index requires; add `"triggers"` only if a host needs triggers.
   */
  experimental?: string[];
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type TursoDatabase = any;

/**
 * The specifier is deliberately not a literal. TypeScript must not try to
 * resolve Turso's package for a build that does not include it, and a bundler
 * must not pull an 11 MB wasm into a browser bundle. It resolves at runtime,
 * where a host that chose this engine has installed it.
 */
const TURSO_SPECIFIER = "@tursodatabase/database/compat";

/** Wrap the synchronous Turso `Database` in the BrainDb port. */
function wrapTurso(db: TursoDatabase): BrainDb {
  return {
    exec(q) {
      if (typeof q === "string") db.exec(q);
      else db.prepare(q.sql).run(...(q.bind ?? []));
    },
    selectValue(sql, bind) {
      const row = db.prepare(sql).get(...(bind ?? []));
      return row ? Object.values(row)[0] : undefined;
    },
    selectObjects(sql, bind) {
      return db.prepare(sql).all(...(bind ?? [])) as Record<string, unknown>[];
    },
    close() {
      db.close();
    },
  };
}

/** A Turso-backed engine. A Node or WASI host opts in explicitly. */
export function tursoEngine(opts: TursoEngineOpts): BrainEngine {
  return {
    id: "turso",
    dialect: tursoDialect,
    async open() {
      const mod = (await import(TURSO_SPECIFIER)) as {
        Database: new (
          path: string,
          o?: { experimental?: string[] },
        ) => TursoDatabase;
      };
      const db = new mod.Database(opts.path, {
        experimental: opts.experimental ?? ["index_method"],
      });
      return { db: wrapTurso(db), backend: "turso" };
    },
  };
}

export type { RecallRow };
