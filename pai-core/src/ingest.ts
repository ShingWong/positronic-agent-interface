// pai-core ingest — one ingestion pipeline for every host.
//
// Port of positronic_ai/ops/ingest.py. Hosts inject capabilities the core
// cannot portably do (HTML conversion needs pandoc, attachment extraction
// needs native tools, vision needs an LLM endpoint). Everything else —
// Message-ID normalize + dedup check shape, table-signal telemetry,
// vision routing decision, threat verdict, feature assembly — lives here
// exactly once. The Python server implements the same flow and parity
// tests keep them honest.
//
// Why TypeScript, not WASM bytecode: the hosts ARE JavaScript runtimes
// (Gecko, WebView2). TS core runs natively with zero bridge cost. A Rust
// rewrite for wasm32 would cost months to re-prove what the parity suite
// already guarantees. The only true WASM in the stack is sqlite-wasm
// (storage). "Same code" means same TypeScript, not same bytecode.

import { normalizeMessageId } from "./messageId.js";
import { scoreThreat, type ThreatTag } from "./threat.js";
import { detectTable, type TableSignals } from "./tables.js";

export interface IngestAttachment {
  filename: string;
  contentType: string;
  /** Extracted markdown text (host already ran its native extractors). */
  text: string;
}

export interface IngestInput {
  body: string;
  subject?: string;
  sender?: string;
  date?: string;
  messageId?: string;
  isHtml?: boolean;
  attachments?: IngestAttachment[];
}

export interface IngestCapabilities {
  /** Convert HTML body to plain text (pandoc-plain on server). */
  convertHtml?: (html: string) => string;
  /** Restructure a detected table (vision LLM). Returns markdown or throws. */
  restructureTable?: (text: string) => Promise<string> | string;
  /** Prior message count from this sender (isolation signal). */
  senderHistoryCount?: (sender: string) => number;
}

/** Minimum table size routed to vision (small tables stay on bge). */
export const VISION_MIN_ROWS = 8;

export interface IngestPlan {
  /** Final body text to store (converted + attachments appended). */
  body: string;
  bodyConvert: string;
  subject: string;
  messageId: string;
  tableSig: TableSignals;
  routeToVision: boolean;
  threat: { tag: ThreatTag; reasons: string[] };
  attachmentNames: string[];
  features: Record<string, unknown>;
}

/** Pure planning step: decide everything, touch nothing. Hosts execute
 * (dedup lookup, vision call, DB write) then call assemble(). */
export function planIngest(
  input: IngestInput,
  caps: IngestCapabilities = {},
): IngestPlan {
  let body = (input.body || "").trim();
  let bodyConvert = "plain";
  if (input.isHtml && body) {
    if (caps.convertHtml) {
      try {
        body = caps.convertHtml(body).trim();
        bodyConvert = "pandoc-plain";
      } catch {
        body = body.replace(/<[^>]*>/g, " ").trim();
        bodyConvert = "regex-fallback";
      }
    } else {
      body = body.replace(/<[^>]*>/g, " ").trim();
      bodyConvert = "regex-fallback";
    }
  }

  const attachmentNames: string[] = [];
  let attachText = "";
  for (const att of (input.attachments || []).slice(0, 3)) {
    if (att.text && att.text.trim()) {
      attachmentNames.push(att.filename);
      attachText += `\n\n[Attachment: ${att.filename}]\n${att.text.trim()}`;
    }
  }
  if (attachText) {
    body = (body + "\n" + attachText.trim()).trim();
    bodyConvert += "+attach";
  }

  const mid = normalizeMessageId(input.messageId);
  const subj = (input.subject || "").trim() || body.slice(0, 80);
  const [visionCandidate, tableSig] = detectTable(body, VISION_MIN_ROWS);
  const routeToVision = visionCandidate && !!caps.restructureTable;

  const sender = input.sender || "";
  const history = sender && caps.senderHistoryCount
    ? caps.senderHistoryCount(sender)
    : 0;
  const verdict = sender
    ? scoreThreat(sender, subj, body, history)
    : { tag: "clean" as ThreatTag, reasons: [] as string[] };

  const features: Record<string, unknown> = {
    subject_norm: subj,
    body_text: body,
    sender,
    message_id: mid,
    threat_tag: verdict.tag,
    threat_reasons: verdict.reasons,
    table_sig: tableSig,
  };
  if (input.date) features["date"] = input.date;
  if (attachmentNames.length) features["attachments"] = attachmentNames;

  return {
    body, bodyConvert, subject: subj, messageId: mid,
    tableSig, routeToVision, threat: verdict,
    attachmentNames, features,
  };
}

/** Fold a vision restructure back into the plan (host calls after LLM). */
export function applyVision(plan: IngestPlan, restructured: string): IngestPlan {
  const clean = (restructured || "").trim();
  if (!clean) return plan; // empty guard: never overwrite good text with nothing
  const features = {
    ...plan.features,
    body_text: clean,
    body_raw: plan.body,
    vision_restructured: true,
  };
  return { ...plan, body: clean, features };
}
