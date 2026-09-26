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

// store tests: in-memory sqlite via better-sqlite3-shaped mock is overkill;
// exercise LocalBrain against a minimal oo1-compatible fake.
import { describe, expect, it } from "vitest";
import { LocalBrain } from "../src/store.js";

function makeFakeDb() {
  const rows: Record<string, unknown>[] = [];
  return {
    exec(_q: unknown) {},
    selectValue(sql: string, params?: unknown[]) {
      if (sql.startsWith("SELECT MAX(tau)")) {
        return rows.reduce((m, r) => Math.max(m, r.tau as number), 0);
      }
      if (sql.startsWith("SELECT id FROM episode WHERE message_id")) {
        const hit = rows.find((r) => r.message_id === (params as string[])[0]);
        return hit ? hit.id : undefined;
      }
      if (sql.startsWith("SELECT COUNT(*) FROM episode WHERE sender")) {
        return rows.filter((r) => r.sender === (params as string[])[0]).length;
      }
      if (sql.startsWith("SELECT COUNT(*) FROM episode")) return rows.length;
      return 0;
    },
    selectObjects() {
      return rows.map((r) => ({ ...r, rank: -1 }));
    },
    close() {},
    __rows: rows,
  };
}

class TestBrain extends LocalBrain {
  fake = makeFakeDb();
  protected override async loadWasm(): Promise<unknown> {
    const fake = this.fake;
    return {
      oo1: {
        DB: class {
          exec(q: unknown) {
            const sql = typeof q === "string" ? q : (q as { sql: string }).sql;
            if (sql.trimStart().startsWith("INSERT INTO episode")) {
              const bind = (q as { bind: unknown[] }).bind;
              const [id, subject, body, sender, message_id, threat_tag,
                threat_reasons, vision_restructured, table_sig,
                features_json, tau, wall] = bind as unknown[];
              fake.__rows.push({
                id, subject, body, sender, message_id, threat_tag,
                threat_reasons, vision_restructured, table_sig,
                features_json, tau, wall,
              });
            }
          }
          selectValue(sql: string, params?: unknown[]) {
            return fake.selectValue(sql, params);
          }
          selectObjects() {
            return fake.selectObjects();
          }
          close() {
            fake.close();
          }
        },
      },
    };
  }
}

describe("store", () => {
  it("ingests, dedups by message-id, recalls", async () => {
    const b = new TestBrain();
    expect(await b.open("test")).toBe("memory");
    const r1 = b.ingest("Hello team, lunch tomorrow?", {
      subject: "lunch?",
      sender: "sam@example.com",
      messageId: "<abc@x.com>",
    });
    expect(r1.duplicate).toBe(false);
    const r2 = b.ingest("Hello team, lunch tomorrow?", {
      sender: "sam@example.com",
      messageId: "<abc@x.com>",
    });
    expect(r2.duplicate).toBe(true);
    expect(r2.episode_id).toBe(r1.episode_id);
    expect(b.count()).toBe(1);
    const hits = b.recall("lunch");
    expect(hits.results.length).toBe(1);
    expect(hits.results[0].message_id).toBe("abc@x.com");
    b.close();
  });

  it("tags phishing via core scorer", async () => {
    const b = new TestBrain();
    await b.open("t2");
    const r = b.ingest("Click https://evil.com/login to verify your password", {
      subject: "Verify Adobe login",
      sender: "clerk@mycompany.com",
    });
    expect(r.threat).toBe("phishing");
    b.close();
  });
});
