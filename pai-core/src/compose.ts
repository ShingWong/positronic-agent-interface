// pai-core compose — prefetch context for drafting email.
//
// Drafting needs facts BEFORE writing: who the correspondent is (dossier)
// and what the thread already said (episodes). The `compose_context' tool
// does that retrieval; the model then writes the body and `compose_email`
// creates the draft. Same retrieve-then-act order as the mail search loop.

import { formatEpisodes, type PositronicEpisode, type PositronicToolDef } from "./skill.js";

export const COMPOSE_SKILL = `You are drafting email as the user.
You NEVER invent facts about the correspondent or the thread. Before
calling compose_email, call compose_context with every recipient and,
for replies, the message being answered. Every claim in the draft
(commitments, amounts, dates, names) must come from the prefetched
dossier or thread episodes. Match the thread's tone. If prefetch returns
nothing, say so in the draft-free reply and ask the user — do not guess.
Sending is a separate, user-confirmed step; composing never sends.`;

export const COMPOSE_CONTEXT_TOOL_DEF: PositronicToolDef = {
  id: "compose-context",
  name: "compose_context",
  description:
    "Prefetch correspondent dossiers and thread episodes before drafting. Call before compose_email.",
  parameters: [
    {
      name: "to",
      type: "array",
      description: "Recipient emails or names (array of strings)",
      required: true,
    },
    {
      name: "inReplyTo",
      type: "string",
      description: "Message/episode reference being replied to, if any",
      required: false,
    },
  ],
  returns: { type: "string", description: "Dossier + thread context block for drafting" },
  isActive: true,
};

/** Host-provided retrieval. Hosts implement fetch; core formats. */
export interface ComposeContextDeps {
  dossier(ref: string): Promise<string>;
  thread(ref: string): Promise<PositronicEpisode[]>;
}

export interface ComposeContext {
  block: string;
  sources: string[];
}

/** Pure assembly: dossiers per recipient plus thread episodes for replies. */
export async function prefetchComposeContext(
  to: string[],
  inReplyTo: string | null,
  deps: ComposeContextDeps,
): Promise<ComposeContext> {
  const parts: string[] = [];
  const sources: string[] = [];
  for (const ref of to) {
    const d = await deps.dossier(ref);
    parts.push(`[Correspondent: ${ref}]\n${d}`);
    if (d !== "No object found.") sources.push(ref);
  }
  if (inReplyTo) {
    const eps = await deps.thread(inReplyTo);
    const { text, sources: ts } = formatEpisodes(eps);
    parts.push(`[Thread: ${inReplyTo}]\n${text}`);
    for (const s of ts) if (!sources.includes(s)) sources.push(s);
  }
  const block = parts.join("\n\n") || "(no correspondent or thread context found)";
  return { block, sources };
}

/** Registry handler for compose_context. Returns the context block. */
export function createComposeContextHandler(
  deps: ComposeContextDeps & { onSources?(labels: string[]): void },
): (params: Record<string, unknown>) => Promise<string> {
  return async (params) => {
    const raw = params.to;
    const to = Array.isArray(raw) ? raw.map(String) : raw ? [String(raw)] : [];
    const inReplyTo = params.inReplyTo ? String(params.inReplyTo) : null;
    const { block, sources } = await prefetchComposeContext(to, inReplyTo, deps);
    if (sources.length) deps.onSources?.(sources);
    return block;
  };
}

// Contact, compose/send, folder, and audit tool defs. Same duck-typed
// ToolDefinition shape as POSITRONIC_TOOL_DEFS: hosts register these with
// their own backend deps (Thunderbird compose/messages APIs, audit store).

export const READ_CONTACTS_TOOL_DEF: PositronicToolDef = {
  id: "read-contacts",
  name: "read_contacts",
  description:
    "Search address-book contacts by name or email. On-demand only; results are never stored.",
  parameters: [
    { name: "query", type: "string", description: "Name or email fragment", required: true },
    { name: "k", type: "number", description: "Max results (default 5)", required: false },
  ],
  returns: { type: "string", description: "Name/email pairs, one per line" },
  isActive: true,
};

export const COMPOSE_EMAIL_TOOL_DEF: PositronicToolDef = {
  id: "compose-email",
  name: "compose_email",
  description:
    "Create a draft (new mail or reply). Creates only — never sends. Use compose_context first.",
  parameters: [
    { name: "to", type: "array", description: "Recipient emails (array of strings)", required: true },
    { name: "subject", type: "string", description: "Subject line", required: true },
    { name: "body", type: "string", description: "Plain-text body, grounded in prefetch results", required: true },
    { name: "cc", type: "array", description: "CC emails (array of strings)", required: false },
    { name: "bcc", type: "array", description: "BCC emails (array of strings)", required: false },
    { name: "inReplyTo", type: "string", description: "Message reference being replied to", required: false },
  ],
  returns: { type: "string", description: "Draft identity for the origin-context store" },
  isActive: true,
};

export const SEND_EMAIL_TOOL_DEF: PositronicToolDef = {
  id: "send-email",
  name: "send_email",
  description:
    "Send a draft. Requires confirmed:true AND an in-handler user confirm dialog. Refuses otherwise.",
  parameters: [
    { name: "draftId", type: "string", description: "Draft identity from compose_email", required: true },
    { name: "confirmed", type: "boolean", description: "User explicitly approved this send", required: true },
  ],
  returns: { type: "string", description: "Send receipt or refusal" },
  isActive: true,
};

export const LIST_FOLDERS_TOOL_DEF: PositronicToolDef = {
  id: "list-folders",
  name: "list_folders",
  description: "List account folder paths (read-only).",
  parameters: [],
  returns: { type: "string", description: "Folder paths, one per line" },
  isActive: true,
};

export const SEARCH_MESSAGES_TOOL_DEF: PositronicToolDef = {
  id: "search-messages",
  name: "search_messages",
  description:
    "Capped candidate search over mail (read-only). Every bulk flow starts here; report the count first.",
  parameters: [
    { name: "folder", type: "string", description: "Folder path to search", required: false },
    { name: "query", type: "string", description: "Subject/sender keywords", required: false },
    { name: "olderThanDays", type: "number", description: "Only messages older than N days", required: false },
    { name: "limit", type: "number", description: "Max candidates (default 50, hard cap 500)", required: false },
  ],
  returns: { type: "string", description: "Candidate list plus total count" },
  isActive: true,
};

export const MOVE_MESSAGES_TOOL_DEF: PositronicToolDef = {
  id: "move-messages",
  name: "move_messages",
  description:
    "Move messages by id to a folder (Trash = delete). Single rule-matched moves are auto; bulk sets need confirmed:true plus a user dialog.",
  parameters: [
    { name: "messageIds", type: "array", description: "Message ids from search_messages", required: true },
    { name: "destination", type: "string", description: "Target folder path", required: true },
    { name: "confirmed", type: "boolean", description: "User approved this exact set", required: false },
  ],
  returns: { type: "string", description: "Move receipt" },
  isActive: true,
};

export const EMPTY_FOLDER_TOOL_DEF: PositronicToolDef = {
  id: "empty-folder",
  name: "empty_folder",
  description:
    "Delete every message in a folder. Confirm always with the count shown. Inbox/Archive additionally require the typed folder name.",
  parameters: [
    { name: "folder", type: "string", description: "Folder path to empty", required: true },
    { name: "confirmed", type: "boolean", description: "User approved after seeing the count", required: false },
    { name: "typedName", type: "string", description: "Folder name retyped (Inbox/Archive only)", required: false },
  ],
  returns: { type: "string", description: "Count-only preview or delete receipt" },
  isActive: true,
};

export const QUERY_AUDIT_TOOL_DEF: PositronicToolDef = {
  id: "query-audit",
  name: "query_audit",
  description:
    "Read-only history of agent side effects (moves, drafts, sends, quarantines). Answers 'what happened to X'.",
  parameters: [
    { name: "who", type: "string", description: "Correspondent name or email fragment", required: false },
    { name: "when", type: "string", description: "Day reference, e.g. 'yesterday' or YYYY-MM-DD", required: false },
    { name: "action", type: "string", description: "Action type: move, draft, send, quarantine, webhook, empty", required: false },
  ],
  returns: { type: "string", description: "Matching audit entries, newest first" },
  isActive: true,
};

export const RUN_WEBHOOK_TOOL_DEF: PositronicToolDef = {
  id: "run-webhook",
  name: "run_webhook",
  description:
    "POST a rule's webhook for a queued analysis item. URL comes only from the queued rule (exact match, never free-form); payload keys filtered to the rule's field allowlist.",
  parameters: [
    { name: "pendingId", type: "string", description: "Queue id from get_pending/run_pending", required: true },
    { name: "payload", type: "object", description: "JSON payload (filtered to allowlisted fields)", required: true },
  ],
  returns: { type: "string", description: "Delivery receipt with HTTP status" },
  isActive: true,
};

/** All v0.6 action defs in registration order. */
export const ACTION_TOOL_DEFS: PositronicToolDef[] = [
  READ_CONTACTS_TOOL_DEF,
  COMPOSE_EMAIL_TOOL_DEF,
  SEND_EMAIL_TOOL_DEF,
  LIST_FOLDERS_TOOL_DEF,
  SEARCH_MESSAGES_TOOL_DEF,
  MOVE_MESSAGES_TOOL_DEF,
  EMPTY_FOLDER_TOOL_DEF,
  QUERY_AUDIT_TOOL_DEF,
  RUN_WEBHOOK_TOOL_DEF,
];

/** Keep a webhook payload inside the rule's field allowlist. */
export function filterWebhookPayload(
  payload: Record<string, unknown>,
  fields: string[] | undefined,
): Record<string, unknown> {
  if (!fields || !fields.length) return payload;
  const allow = new Set(fields);
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(payload)) {
    if (allow.has(k)) out[k] = v;
  }
  return out;
}

/** Example-only SSRF guard for rule webhook URLs (user-configured, so
 * loopback is allowed; cloud metadata and non-http schemes are not). */
export function assertSafeWebhookUrl(url: string): void {
  let u: URL;
  try {
    u = new URL(url);
  } catch {
    throw new Error("Invalid webhook URL.");
  }
  if (u.protocol !== "http:" && u.protocol !== "https:") {
    throw new Error("Webhook URL must be http(s).");
  }
  if (u.hostname === "169.254.169.254" || u.hostname === "metadata.google.internal") {
    throw new Error("Webhook host blocked.");
  }
}

/** Shared safety validators — hosts enforce these in handlers AND dialogs. */
export function validateCompose(params: Record<string, unknown>): { ok: boolean; reason?: string } {
  const to = Array.isArray(params.to) ? params.to : [];
  if (!to.length) return { ok: false, reason: "No recipients." };
  if (to.length > 50) return { ok: false, reason: "Recipient cap is 50." };
  if (!String(params.subject || "").trim()) return { ok: false, reason: "Subject is empty." };
  if (!String(params.body || "").trim()) return { ok: false, reason: "Body is empty — say the mail says nothing instead of sending air." };
  return { ok: true };
}

export function validateMove(
  count: number,
  confirmed: unknown,
  bulkThreshold: number,
): { ok: boolean; reason?: string } {
  if (!count) return { ok: false, reason: "(no matches — nothing to move)" };
  if (count > bulkThreshold && confirmed !== true) {
    return { ok: false, reason: `Bulk set (${count}). Report the count and ask for confirmation first.` };
  }
  return { ok: true };
}

export function validateEmpty(
  folder: string,
  count: number,
  confirmed: unknown,
  typedName: unknown,
): { ok: boolean; reason?: string } {
  const base = folder.split("/").pop() || folder;
  if (confirmed !== true) return { ok: false, reason: `"${folder}" holds ${count} — confirm explicitly to empty it.` };
  if ((base === "Inbox" || base === "Archive") && typedName !== base) {
    return { ok: false, reason: `Retype "${base}" to empty it.` };
  }
  return { ok: true };
}
