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

// @positronic/pai-core — portable PAI logic. One core, many hosts.
export { chunkMarkdown } from "./chunk.js";
export { scoreThreat, type ThreatTag } from "./threat.js";
export { detectTable, looksLikeTable, type TableSignals } from "./tables.js";
export { normalizeMessageId, type EpisodeRef } from "./messageId.js";
export {
  planIngest,
  applyVision,
  VISION_MIN_ROWS,
  type IngestAttachment,
  type IngestInput,
  type IngestCapabilities,
  type IngestPlan,
} from "./ingest.js";
export {
  POSITRONIC_SKILL,
  POSITRONIC_TOOLS,
  POSITRONIC_TOOL_DEFS,
  createPositronicHandlers,
  formatEpisodes,
  formatFullBodies,
  AGENT_MAX_ROUNDS,
  type ToolSchema,
  type PositronicToolDef,
  type PositronicToolParameter,
  type PositronicToolDeps,
  type PositronicEpisode,
} from "./skill.js";
export { LocalBrain, type LocalEpisode, type RecallHit } from "./store.js";
export {
  COMPOSE_SKILL,
  COMPOSE_CONTEXT_TOOL_DEF,
  ACTION_TOOL_DEFS,
  READ_CONTACTS_TOOL_DEF,
  COMPOSE_EMAIL_TOOL_DEF,
  SEND_EMAIL_TOOL_DEF,
  LIST_FOLDERS_TOOL_DEF,
  SEARCH_MESSAGES_TOOL_DEF,
  MOVE_MESSAGES_TOOL_DEF,
  EMPTY_FOLDER_TOOL_DEF,
  QUERY_AUDIT_TOOL_DEF,
  RUN_WEBHOOK_TOOL_DEF,
  prefetchComposeContext,
  createComposeContextHandler,
  validateCompose,
  validateMove,
  validateEmpty,
  filterWebhookPayload,
  assertSafeWebhookUrl,
  type ComposeContext,
  type ComposeContextDeps,
} from "./compose.js";
