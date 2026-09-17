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
