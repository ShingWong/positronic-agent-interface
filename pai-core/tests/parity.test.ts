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

// Parity tests: TS core must agree with the Python originals.
// Vectors double as the port spec — any divergence fails here.
import { describe, expect, it } from "vitest";
import { chunkMarkdown } from "../src/chunk.js";
import { scoreThreat } from "../src/threat.js";
import { detectTable, looksLikeTable } from "../src/tables.js";
import { normalizeMessageId } from "../src/messageId.js";

describe("chunk", () => {
  it("splits paragraphs and merges to budget", () => {
    const out = chunkMarkdown("Hello world. This is fine.\n\nSecond para here.", "subj", 50);
    expect(out.length).toBeGreaterThanOrEqual(1);
    expect(out[0].startsWith("Subject: subj")).toBe(true);
  });
  it("keeps table rows whole", () => {
    const out = chunkMarkdown("| A | B |\n| 1 | 2 |", "", 7000);
    expect(out.join("\n")).toContain("| A | B |");
  });
  it("returns [] for empty input", () => {
    expect(chunkMarkdown("", "", 7000)).toEqual([]);
  });
});

describe("threat", () => {
  it("flags phishing on credential link from foreign host", () => {
    const r = scoreThreat(
      "clerk@mycompany.com",
      "Verify your Adobe login",
      "Click https://evil-portal.com/login to verify your password",
      5,
    );
    expect(r.tag).toBe("phishing");
  });
  it("flags scam lexicon from new sender", () => {
    const r = scoreThreat("x@y.com", "inheritance claim", "You are the beneficiary of a large inheritance.", 0);
    expect(r.tag).toBe("scam");
  });
  it("flags spam lexicon", () => {
    const r = scoreThreat("x@y.com", "hi", "Crypto giveaway, double your coins!", 5);
    expect(r.tag).toBe("spam");
  });
  it("passes clean mail", () => {
    const r = scoreThreat("sam@sersargroup.com", "lunch?", "Want lunch tomorrow?", 10);
    expect(r.tag).toBe("clean");
  });
});

describe("tables", () => {
  it("fires on pipe tables with data", () => {
    const t = "| Q | A |\n| Q1 | $5.00 |\n| Q2 | $7.00 |\n| Q3 | $9.00 |";
    expect(looksLikeTable(t)).toBe(true);
  });
  it("ignores plain prose", () => {
    expect(looksLikeTable("Hello world, normal email here.")).toBe(false);
  });
  it("ignores CSS dumps", () => {
    const css = ".darkmode { color:#231f20 !important; }\n".repeat(10) + "Hi there friend.";
    const [fire, sig] = detectTable(css);
    expect(fire).toBe(false);
    expect(sig.cssLines).toBeGreaterThan(5);
  });
  it("holds small tables below the gate", () => {
    const t = "| A | $1.00 |\n| B | $2.00 |";
    const [fire, sig] = detectTable(t, 8);
    expect(sig.tableLike).toBe(true);
    expect(fire).toBe(false);
  });
});

describe("messageId", () => {
  it("strips brackets and whitespace", () => {
    expect(normalizeMessageId("  <abc@x.com> ")).toBe("abc@x.com");
  });
  it("empties falsy input", () => {
    expect(normalizeMessageId(null)).toBe("");
    expect(normalizeMessageId("")).toBe("");
  });
});
