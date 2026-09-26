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

// PAI core — RFC Message-ID normalization + dedup helpers.
// Port of normalize_message_id (positronic_ai/ops/ingest.py).

/** Normalize an RFC Message-ID for dedup: strip whitespace and <>. */
export function normalizeMessageId(raw: unknown): string {
  if (!raw) return "";
  let mid = String(raw).trim();
  if (mid.startsWith("<") && mid.endsWith(">") && mid.length > 2) {
    mid = mid.slice(1, -1).trim();
  }
  return mid;
}

export interface EpisodeRef {
  episodeId: string;
  messageId?: string;
  subject?: string;
}
