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

// PAI core — table-structure detector with telemetry signals.
// Port of positronic_ai/vision.py detect_table (v2: CSS/header/link
// exclusions + data-density gate). Pure function, no network.

export interface TableSignals {
  pipeRows: number;
  alignedLines: number;
  maxRun: number;
  totalLines: number;
  cssLines: number;
  hdrLines: number;
  linkLines: number;
  dataLines: number;
  minRows: number;
  tableLike: boolean;
  bigEnough: boolean;
}

const CSS_RE =
  /(!important|@[a-z-]+|\{[^{}]*[;:])|^\s*[.#][\w-]+\s*[{,]|:\s*#[0-9a-fA-F]{3,6}|\b\d+px\b|\bcolor\s*:|\bmargin\b|\bpadding\b|\bfont-/i;
const HDR_RE =
  /^(Received|Authentication-Results|X-[\w-]+|Return-Path|DKIM-Signature|ARC-|Message-ID|From|To|Cc|Date|Subject|MIME-|Content-|smtp\.|cipher=):?/i;
const DATA_RE =
  /[$€£¥]\s?[\d,]+\.?\d*|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d+\.\d{2}\b|\b\d{1,3}(,\d{3})+|\b\d+\s?%|\b[A-Z]{2}\s?\d{3,4}\b|\b(Q[1-4]|FY\d{2,4}|Total|Subtotal|Balance|Amount)\b/i;
const ALIGN_RE = / {2,}\S/g;

function isCss(line: string): boolean {
  return CSS_RE.test(line);
}

function isLinky(line: string): boolean {
  const s = line.trim();
  if (!s) return false;
  if (s.startsWith("<http") || s.startsWith("http")) return true;
  const brackets = (s.match(/\[[^\]]*\]/g) || []).length;
  const words = s.split(/\s+/).length;
  return brackets >= 2 && brackets >= words / 2;
}

export function detectTable(text: string, minRows = 8): [boolean, TableSignals] {
  const sig: TableSignals = {
    pipeRows: 0,
    alignedLines: 0,
    maxRun: 0,
    totalLines: 0,
    cssLines: 0,
    hdrLines: 0,
    linkLines: 0,
    dataLines: 0,
    minRows,
    tableLike: false,
    bigEnough: false,
  };
  if (!text) return [false, sig];
  const nonEmpty = text.split("\n").filter((l) => l.trim());
  sig.totalLines = nonEmpty.length;
  if (nonEmpty.length < 2) return [false, sig];
  const content = nonEmpty.filter((l) => !isCss(l));
  sig.cssLines = nonEmpty.length - content.length;
  const noHdr = content.filter((l) => !HDR_RE.test(l.trim()));
  sig.hdrLines = content.length - noHdr.length;
  const struct = noHdr.filter((l) => !isLinky(l));
  sig.linkLines = noHdr.length - struct.length;
  if (!struct.length) return [false, sig];

  sig.pipeRows = struct.filter((l) => (l.match(/\|/g) || []).length >= 2).length;
  sig.alignedLines = struct.filter((l) => (l.match(ALIGN_RE) || []).length >= 2).length;
  let run = 0;
  let best = 0;
  for (const l of struct) {
    run = (l.match(/\|/g) || []).length >= 2 ? run + 1 : 0;
    if (run > best) best = run;
  }
  sig.maxRun = best;
  sig.dataLines = struct.filter((l) => DATA_RE.test(l)).length;

  const structRows = Math.max(sig.pipeRows, sig.alignedLines, best);
  const tableLike = structRows >= 2 && sig.dataLines >= 2;
  const bigEnough = structRows >= minRows && sig.dataLines >= minRows / 2;
  sig.tableLike = tableLike;
  sig.bigEnough = bigEnough;
  return [tableLike && bigEnough, sig];
}

export function looksLikeTable(text: string, minRows = 2): boolean {
  return detectTable(text, minRows)[0];
}
