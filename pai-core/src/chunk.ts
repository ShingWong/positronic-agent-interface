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

// PAI core — sentence-aware markdown chunking.
// Port of positronic_ai/chunk.py. Pure function, no deps.

const SENT = /(?<=[.!?])\s+(?=[A-Z0-9"'])/;
const BLOCK = /^(#{1,6}\s+.*|[-*]\s+.*|\|.*\||>.*)$/;

function sentences(text: string): string[] {
  return text.split(SENT).map((s) => s.trim()).filter(Boolean);
}

export function chunkMarkdown(
  md: string,
  subject = "",
  maxChars = 7000,
  overlapSents = 1,
): string[] {
  const prefix = subject.trim() ? `Subject: ${subject.trim()}\n` : "";
  const units: string[] = [];
  for (const para of md.split(/\n{2,}/)) {
    const p = para.trim();
    if (!p) continue;
    if (BLOCK.test(p)) {
      units.push(p);
      continue;
    }
    const sents = sentences(p);
    units.push(...(sents.length ? sents : [p]));
  }
  const chunks: string[] = [];
  let cur = "";
  for (const u of units) {
    if (cur && cur.length + 2 + u.length > maxChars) {
      chunks.push(cur);
      const tail = overlapSents ? sentences(cur).slice(-overlapSents).join(" ") : "";
      cur = tail ? `${tail} ${u}`.trim() : u;
    } else {
      cur = cur ? `${cur}  ${u}`.trim() : u;
    }
  }
  if (cur) chunks.push(cur);
  // pathological: single unit over budget with no sentence end — word cut
  const fixed: string[] = [];
  for (let c of chunks) {
    while (c.length > maxChars * 2) {
      let cut = c.lastIndexOf(" ", maxChars);
      if (cut <= 0) cut = maxChars;
      fixed.push(c.slice(0, cut));
      c = c.slice(cut).trim();
    }
    fixed.push(c);
  }
  const out = fixed.filter((c) => c.trim()).map((c) => prefix + c);
  return out.length ? out : prefix.trim() ? [prefix.trim()] : [];
}
