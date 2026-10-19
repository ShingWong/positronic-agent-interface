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

// Conformance: the same behaviours, against every engine, for real.
//
// store.test.ts drives LocalBrain over a fake oo1 handle, which covers the
// store logic but none of the SQL. This suite runs the behaviours against the
// actual engines instead — including Turso, whose dialect differs most (no
// fts5 module, fts_match/fts_score instead of MATCH/bm25, an engine-maintained
// index). The point is that an engine is pass/fail, not hope.
//
// The Turso case is skipped when @tursodatabase/database is not installed, so
// the package still tests clean without it.
import { describe, expect, it } from "vitest";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { LocalBrain } from "../src/store.js";
import { sqliteWasmEngine } from "../src/engine-sqlite.js";
import { tursoEngine } from "../src/engine-turso.js";

// Deliberately not a literal — see the note in engine-turso.ts.
const TURSO_SPECIFIER = "@tursodatabase/database/compat";
let tursoAvailable = true;
try {
  await import(TURSO_SPECIFIER);
} catch {
  tursoAvailable = false;
}

interface Harness {
  brain: LocalBrain;
  /** The store name to open. */
  name: string;
  /** A fresh LocalBrain over the same store. */
  reopen(): LocalBrain;
}

interface EngineCase {
  label: string;
  /** What LocalBrain.open() should report. */
  backend: string;
  /** Whether a reopened handle sees the same store. */
  durable: boolean;
  make(): Harness;
}

const cases: EngineCase[] = [
  {
    label: "sqlite-wasm",
    backend: "memory", // no OPFS under Node; the wasm FS is in-process
    // The Emscripten factory returns a fresh module (and so a fresh FS) per
    // open, so reopening is not meaningful here. The browser host caches the
    // module and this does persist.
    durable: false,
    make() {
      return {
        name: `conformance-${Math.random().toString(36).slice(2)}`,
        brain: new LocalBrain(sqliteWasmEngine),
        reopen: () => new LocalBrain(sqliteWasmEngine),
      };
    },
  },
];

if (tursoAvailable) {
  cases.push({
    label: "turso",
    backend: "turso",
    durable: true,
    make() {
      const path = join(mkdtempSync(join(tmpdir(), "pai-core-conformance-")), "brain.db");
      return {
        name: "brain",
        brain: new LocalBrain(tursoEngine({ path })),
        reopen: () => new LocalBrain(tursoEngine({ path })),
      };
    },
  });
}

for (const c of cases) {
  describe(`store conformance — ${c.label}`, () => {
    it("opens with its own backend", async () => {
      const h = c.make();
      expect(await h.brain.open(h.name)).toBe(c.backend);
      h.brain.close();
    });

    it("ingests, dedups by message-id, counts", async () => {
      const h = c.make();
      await h.brain.open(h.name);
      const r1 = h.brain.ingest("Hello team, lunch tomorrow?", {
        subject: "lunch?",
        sender: "sam@example.com",
        messageId: "<abc@x.com>",
      });
      expect(r1.duplicate).toBe(false);
      const r2 = h.brain.ingest("Hello team, lunch tomorrow?", {
        sender: "sam@example.com",
        messageId: "<abc@x.com>",
      });
      expect(r2.duplicate).toBe(true);
      expect(r2.episode_id).toBe(r1.episode_id);
      expect(h.brain.count()).toBe(1);
      h.brain.close();
    });

    it("recalls across the whole indexed column set", async () => {
      const h = c.make();
      await h.brain.open(h.name);
      h.brain.ingest("Hello team, lunch tomorrow?", {
        subject: "lunch?",
        sender: "sam@example.com",
      });
      h.brain.ingest("Your invoice for the catering is attached", {
        subject: "invoice",
        sender: "billing@vendor.com",
      });
      // subject hit
      expect(h.brain.recall("invoice").results[0].sender).toBe("billing@vendor.com");
      // body-only hit — "catering" is in no subject
      expect(h.brain.recall("catering").results.map((x) => x.sender)).toContain(
        "billing@vendor.com",
      );
      // sender hit — "sam" is in no subject or body
      expect(h.brain.recall("sam").results.map((x) => x.sender)).toContain(
        "sam@example.com",
      );
      h.brain.close();
    });

    it("tags phishing via the shared scorer", async () => {
      const h = c.make();
      await h.brain.open(h.name);
      const r = h.brain.ingest("Click https://evil.com/login to verify your password", {
        subject: "Verify Adobe login",
        sender: "clerk@mycompany.com",
      });
      expect(r.threat).toBe("phishing");
      h.brain.close();
    });

    it.skipIf(!c.durable)("reopens with the same identity and monotonic tau", async () => {
      const h = c.make();
      await h.brain.open(h.name);
      h.brain.ingest("first", { subject: "one" });
      const uuid = h.brain.uuid;
      h.brain.close();

      const again = h.reopen();
      await again.open(h.name);
      expect(again.uuid).toBe(uuid);
      expect(again.count()).toBe(1);
      expect(again.ingest("second", { subject: "two" }).tau).toBeGreaterThan(0.1);
      again.close();
    });
  });
}
