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

// pai-core skill — the positronic agent skill for tool-capable LLMs.
// Replaces regex intent-parsing (wantAll/wantCount/coreference patterns):
// the model decides what to retrieve, executes tools, and answers from
// what comes back. Same skill ships Thunderbird, Outlook, Personabot.

export const POSITRONIC_SKILL = `You are Positronic AI, a mail-brain assistant.
You NEVER answer from general knowledge. Every factual claim must come from
a tool result. Cite sources like [1] using the subject names returned.

Tools:
- recall_brain(query, k?, exhaustive?, threat?): ranked mail search.
  Use exhaustive=true when the user says all/every/complete list — it
  returns every FTS match newest-first instead of top-k. Use threat
  "flagged" (or a tag name) for flagged-mail reviews. Default k=12.
- query_brain_sql(sql): full episode bodies (SELECT id, features_json
  FROM episode WHERE ...). Use when snippets lack detail (amounts, line
  items, attachments). IDs must match /^[0-9a-f-]{8,60}$/i.
  Snippets truncate past ~250 chars: NEVER declare an amount, date, or
  code absent until query_brain_sql has returned the full body.
- ask_brain(object): dossier on a remembered person/thread/topic.

Rules:
- "All X" means exhaustive=true, then report every match.
- "Top N most recent" means exhaustive=true, sort by tau desc, take N.
- Otherwise report top-k ranked hits and say so ("top 12 of 34").
- Follow-ups ("that invoice", "amounts?") refer to prior tool results —
  re-query with the resolved terms, do not re-ask the user.
- If tools return nothing relevant, say so. Never invent mail.
- One episode's figures never transfer to another: an amount, date, or
  confirmation code belongs only to the episode that states it. If the
  number is not in the retrieved text, say so — do not borrow it from
  a same-amount hit on a different subject.
- Keep answers short; tables for lists with amounts.`;

export interface ToolSchema {
  type: "function";
  function: {
    name: string;
    description: string;
    parameters: Record<string, unknown>;
  };
}

export const POSITRONIC_TOOLS: ToolSchema[] = [
  {
    type: "function",
    function: {
      name: "recall_brain",
      description: "Ranked search over ingested mail. Returns episodes with subject, snippet, sender, threat tag, tau.",
      parameters: {
        type: "object",
        properties: {
          query: { type: "string", description: "Search keywords" },
          k: { type: "integer", description: "Max hits (default 12)" },
          exhaustive: { type: "boolean", description: "True for all/every requests: every FTS match, newest-first" },
          threat: { type: "string", description: "'flagged' or a tag name; bypasses lexical ranking" },
        },
        required: ["query"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "query_brain_sql",
      description: "Full episode bodies via SQL (SELECT id, features_json FROM episode WHERE ...). For amounts, line items, attachment text.",
      parameters: {
        type: "object",
        properties: {
          sql: { type: "string", description: "Read-only SELECT over episode" },
        },
        required: ["sql"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "ask_brain",
      description: "Dossier on a remembered person, thread, or topic (all sightings, oldest first).",
      parameters: {
        type: "object",
        properties: {
          object: { type: "string", description: "Person, thread, or topic name" },
        },
        required: ["object"],
      },
    },
  },
];

export const AGENT_MAX_ROUNDS = 5;

// sure-gentic ToolDefinition-shaped defs for the same three tools.
// Duck-typed (no import) so pai-core stays zero-dep: pass these straight to
// ToolRegistryService.register(). POSITRONIC_TOOLS above stays as the raw
// OpenAI-schema export for hosts that build requests by hand.
export interface PositronicToolParameter {
  name: string;
  type: "string" | "number" | "boolean" | "array" | "object";
  description: string;
  required: boolean;
}

export interface PositronicToolDef {
  id: string;
  name: string;
  description: string;
  parameters: PositronicToolParameter[];
  returns: { type: string; description: string };
  isActive: boolean;
}

export const POSITRONIC_TOOL_DEFS: PositronicToolDef[] = [
  {
    id: "recall-brain",
    name: "recall_brain",
    description:
      "Ranked search over ingested mail. Returns episodes with subject, snippet, sender, threat tag, tau.",
    parameters: [
      { name: "query", type: "string", description: "Search keywords", required: true },
      { name: "k", type: "number", description: "Max hits (default 12)", required: false },
      {
        name: "exhaustive",
        type: "boolean",
        description: "True for all/every requests: every FTS match, newest-first",
        required: false,
      },
      {
        name: "threat",
        type: "string",
        description: "'flagged' or a tag name; bypasses lexical ranking",
        required: false,
      },
    ],
    returns: { type: "string", description: "Formatted episode hits with [n] citations" },
    isActive: true,
  },
  {
    id: "query-brain-sql",
    name: "query_brain_sql",
    description:
      "Full episode bodies via SQL (SELECT id, features_json FROM episode WHERE ...). For amounts, line items, attachment text.",
    parameters: [
      { name: "sql", type: "string", description: "Read-only SELECT over episode", required: true },
    ],
    returns: { type: "string", description: "Formatted full bodies" },
    isActive: true,
  },
  {
    id: "ask-brain",
    name: "ask_brain",
    description: "Dossier on a remembered person, thread, or topic (all sightings, oldest first).",
    parameters: [
      { name: "object", type: "string", description: "Person, thread, or topic name", required: true },
    ],
    returns: { type: "string", description: "Dossier or 'No object found.'" },
    isActive: true,
  },
];

export interface PositronicEpisode {
  subject?: string;
  title?: string;
  episode_id?: string;
  snippet?: string;
  body?: string;
  sender?: string;
  tau?: number;
  threat_tag?: string;
  kind?: string;
}

/** Host-provided backend access. Hosts implement fetch/filter; core formats. */
export interface PositronicToolDeps {
  recall(
    query: string,
    k: number,
    exhaustive: boolean,
    threat: string | null,
  ): Promise<PositronicEpisode[]>;
  querySql(sql: string): Promise<Record<string, string>[]>;
  ask(object: string): Promise<string>;
  onSources?(labels: string[]): void;
}

export function formatEpisodes(eps: PositronicEpisode[]): { text: string; sources: string[] } {
  const sources: string[] = [];
  const text =
    eps.slice(0, 30).map((ep, i) => {
      const subj = ep.subject || ep.title || "(no subject)";
      const label = subj.slice(0, 60);
      if (!sources.includes(label)) sources.push(label);
      // Attachment episodes are dense extraction text (line items live
      // past the normal window), so give them the wider slice; chat-size
      // mail keeps 500 chars to bound context on small models.
      const window = ep.kind === "attachment" ? 2000 : 500;
      const body = (ep.snippet || ep.body || "").slice(0, window);
      const threat = ep.threat_tag && ep.threat_tag !== "clean" ? ", " + ep.threat_tag : "";
      const tau = ep.tau != null ? ", tau=" + Number(ep.tau).toFixed(1) : "";
      return `[${i + 1}] ${subj} (${ep.sender || "unknown"}${tau}${threat}): ${body}`;
    }).join("\n") || "(no matches)";
  return { text, sources };
}

export function formatFullBodies(rows: Record<string, string>[]): { text: string; sources: string[] } {
  const sources: string[] = [];
  const text =
    rows.slice(0, 4).map((r, i) => {
      try {
        const f = JSON.parse(r.features_json || "{}");
        const body = String(f.body_text || "").slice(0, 2500);
        const subj = String(f.subject_norm || "").slice(0, 60);
        if (subj && !sources.includes(subj)) sources.push(subj);
        return `[full ${i + 1}] ${subj}: ${body}`;
      } catch {
        return `[full ${i + 1}] (unparseable)`;
      }
    }).join("\n") || "(no rows)";
  return { text, sources };
}

/**
 * Registry handlers for the three positronic tools. Returns name -> handler
 * (params, ctx) => string. Register each with its POSITRONIC_TOOL_DEFS entry.
 * The SQL guard (single read-only SELECT) lives here, once, for every host.
 */
export function createPositronicHandlers(
  deps: PositronicToolDeps,
): Record<string, (params: Record<string, unknown>) => Promise<string>> {
  return {
    recall_brain: async (params) => {
      const query = String(params.query || "");
      const k = Math.min(Number(params.k) || 12, 200);
      const threat = params.threat ? String(params.threat) : null;
      const exhaustive = !!params.exhaustive;
      const eps = await deps.recall(query, k, exhaustive, threat);
      const { text, sources } = formatEpisodes(eps);
      if (sources.length) deps.onSources?.(sources);
      return text;
    },
    query_brain_sql: async (params) => {
      const sql = String(params.sql || "");
      if (!/^\s*select\b/i.test(sql) || /;.*\S/.test(sql.replace(/;\s*$/, ""))) {
        return "Only single read-only SELECT statements allowed.";
      }
      const rows = await deps.querySql(sql);
      const { text, sources } = formatFullBodies(rows);
      if (sources.length) deps.onSources?.(sources);
      return text;
    },
    ask_brain: async (params) => {
      return deps.ask(String(params.object || ""));
    },
  };
}
