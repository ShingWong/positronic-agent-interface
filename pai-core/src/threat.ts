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

// PAI core — threat-tagging heuristics for mail.
// Port of positronic_ai/threat.py. Pure function, no DB access.
// Tags: phishing > scam > spam > clean.

const URL_RE = /https?:\/\/[^\s<>'"]+/gi;
const CRED_RE = /\b(login|log in|sign in|verify|password|credential|2fa|one-time)\b/i;
const BRANDS = ["adobe", "microsoft", "apple", "google", "amazon", "paypal", "dhl", "fedex"];

const SCAM_RE =
  /\b(beneficiar|inheritance|advance fee|overdue invoice|wire transfer|gift ?cards?|crypto wallet|private key|recovery phrase|nigerian|prince)\b/i;
const SPAM_RE =
  /\b(enlargement|viagra|cialis|crypto giveaway|double your|lottery (win|prize)|miracle (cure|pills?))\b/i;

export type ThreatTag = "clean" | "spam" | "phishing" | "scam";

function senderDomain(sender: string): string {
  const m = /@([\w.\-]+)/.exec(sender || "");
  return m ? m[1].toLowerCase() : "";
}

function hostnameOf(url: string): string {
  try {
    return new URL(url).hostname || "";
  } catch {
    return "";
  }
}

export function scoreThreat(
  sender = "",
  subject = "",
  body = "",
  senderHistoryCount = 0,
): { tag: ThreatTag; reasons: string[] } {
  const reasons: string[] = [];
  const text = `${subject || ""}\n${body || ""}`;
  const sdom = senderDomain(sender);
  const urls = body ? body.match(URL_RE) || [] : [];
  const hosts = urls.map(hostnameOf).filter(Boolean);

  if (senderHistoryCount <= 0) reasons.push("isolation:new-sender");
  const low = text.toLowerCase();
  for (const brand of BRANDS) {
    if (low.includes(brand) && !sdom.includes(brand)) {
      reasons.push(`fake-context:${brand}`);
      break;
    }
  }
  const cred = CRED_RE.test(text);
  for (const h of hosts) {
    const hl = h.toLowerCase();
    if (hl !== sdom && sdom && hl) {
      reasons.push(cred ? `credential-link:${hl}` : `foreign-link:${hl}`);
    }
    if (/^\d+\.\d+\.\d+\.\d+$/.test(hl)) reasons.push("ip-link");
    if (hl.startsWith("xn--")) reasons.push("punycode-link");
  }

  let tag: ThreatTag = "clean";
  if (
    reasons.some((r) =>
      ["credential-link", "ip-link", "punycode-link"].some((p) => r.startsWith(p)),
    )
  ) {
    tag = "phishing";
  } else if (SCAM_RE.test(text) && senderHistoryCount <= 0) {
    tag = "scam";
    reasons.push("scam-lexicon");
  } else if (SPAM_RE.test(text)) {
    tag = "spam";
    reasons.push("spam-lexicon");
  }
  return { tag, reasons };
}
