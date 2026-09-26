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

// ingest parity: TS planIngest must decide like positronic_ai/ops/ingest.py.
import { describe, expect, it } from "vitest";
import { planIngest, applyVision } from "../src/ingest.js";

describe("ingest plan", () => {
  it("normalizes message-id and scores a clean mail", () => {
    const p = planIngest(
      { body: "Want lunch tomorrow?", subject: "lunch?", sender: "sam@example.com", messageId: "  <abc@x.com> " },
      { senderHistoryCount: () => 10 },
    );
    expect(p.messageId).toBe("abc@x.com");
    expect(p.threat.tag).toBe("clean");
    expect(p.routeToVision).toBe(false);
    expect(p.bodyConvert).toBe("plain");
  });

  it("converts html when capable, regex-falls-back otherwise", () => {
    const withCap = planIngest(
      { body: "<p>Hi</p>", isHtml: true }, { convertHtml: () => "Hi" });
    expect(withCap.body).toBe("Hi");
    expect(withCap.bodyConvert).toBe("pandoc-plain");
    const bare = planIngest({ body: "<p>Hi</p>", isHtml: true });
    expect(bare.body).toBe("Hi");
    expect(bare.bodyConvert).toBe("regex-fallback");
  });

  it("routes big tables to vision only when capable", () => {
    const rows = ["| A | B | $1.00 |"];
    for (let i = 0; i < 10; i++) rows.push(`| r${i} | x | $${i}.00 |`);
    const t = rows.join("\n");
    expect(planIngest({ body: t }).routeToVision).toBe(false);
    expect(planIngest({ body: t }, { restructureTable: (x) => x }).routeToVision).toBe(true);
  });

  it("appends attachments with filename headers", () => {
    const p = planIngest({
      body: "see attached",
      attachments: [{ filename: "inv.pdf", contentType: "application/pdf", text: "Total $950" }],
    });
    expect(p.body).toContain("[Attachment: inv.pdf]");
    expect(p.body).toContain("Total $950");
    expect(p.bodyConvert).toBe("plain+attach");
    expect(p.features["attachments"]).toEqual(["inv.pdf"]);
  });

  it("applyVision keeps raw on empty restructure", () => {
    const p = planIngest({ body: "plain mail" });
    expect(applyVision(p, "   ").body).toBe("plain mail");
    const q = applyVision(p, "| A |\n|---|");
    expect(q.body).toBe("| A |\n|---|");
    expect(q.features["vision_restructured"]).toBe(true);
    expect(q.features["body_raw"]).toBe("plain mail");
  });
});
