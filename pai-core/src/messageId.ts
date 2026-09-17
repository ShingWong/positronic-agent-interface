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
