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
