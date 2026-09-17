import { describe, expect, it } from "vitest";
import {
  COMPOSE_SKILL,
  COMPOSE_CONTEXT_TOOL_DEF,
  ACTION_TOOL_DEFS,
  prefetchComposeContext,
  createComposeContextHandler,
  validateCompose,
  validateMove,
  validateEmpty,
  filterWebhookPayload,
  assertSafeWebhookUrl,
} from "../src/compose.js";

const deps = {
  dossier: async (ref: string) =>
    ref === "sam@sersargroup.com" ? "Sam, client. Sightings: invoice $950." : "No object found.",
  thread: async () => [
    { subject: "Re: Invoice", sender: "sam@sersargroup.com", tau: 3, threat_tag: "clean", snippet: "Please send total" },
  ],
};

describe("compose context", () => {
  it("skill text states the prefetch contract", () => {
    expect(COMPOSE_SKILL).toContain("compose_context");
    expect(COMPOSE_SKILL).toContain("NEVER invent facts");
  });
  it("tool def names compose_context with recipients", () => {
    expect(COMPOSE_CONTEXT_TOOL_DEF.name).toBe("compose_context");
    expect(COMPOSE_CONTEXT_TOOL_DEF.parameters.map((p) => p.name)).toEqual(["to", "inReplyTo"]);
  });
  it("prefetches dossier plus thread for replies", async () => {
    const { block, sources } = await prefetchComposeContext(
      ["sam@sersargroup.com"], "msg-1", deps,
    );
    expect(block).toContain("Sam, client");
    expect(block).toContain("Please send total");
    expect(sources).toContain("sam@sersargroup.com");
  });
  it("new mail without reply skips the thread", async () => {
    const { block } = await prefetchComposeContext(["nobody@x.com"], null, deps);
    expect(block).toContain("No object found.");
    expect(block).not.toContain("[Thread:");
  });
  it("handler returns the block and reports sources", async () => {
    const seen: string[] = [];
    const h = createComposeContextHandler({ ...deps, onSources: (l) => seen.push(...l) });
    const text = await h({ to: ["sam@sersargroup.com"], inReplyTo: "msg-1" });
    expect(text).toContain("[Correspondent:");
    expect(seen).toContain("sam@sersargroup.com");
  });
  it("action defs are nine active tools with unique names", () => {
    expect(ACTION_TOOL_DEFS).toHaveLength(9);
    const names = ACTION_TOOL_DEFS.map((d) => d.name);
    expect(new Set(names).size).toBe(9);
    for (const d of ACTION_TOOL_DEFS) expect(d.isActive).toBe(true);
    expect(names).toContain("query_audit");
    expect(names).toContain("run_webhook");
  });
  it("validators refuse empty drafts, unconfirmed bulk, untyped inbox empty", () => {
    expect(validateCompose({ to: [], subject: "s", body: "b" }).ok).toBe(false);
    expect(validateCompose({ to: ["a@b"], subject: "s", body: "  " }).ok).toBe(false);
    expect(validateCompose({ to: ["a@b"], subject: "s", body: "b" }).ok).toBe(true);
    expect(validateMove(100, false, 10).ok).toBe(false);
    expect(validateMove(100, true, 10).ok).toBe(true);
    expect(validateMove(3, false, 10).ok).toBe(true);
    expect(validateEmpty("Spam", 5, false, null).ok).toBe(false);
    expect(validateEmpty("Inbox", 5, true, "Inbox").ok).toBe(true);
    expect(validateEmpty("Inbox", 5, true, "Spam").ok).toBe(false);
  });
  it("webhook helpers filter fields and block metadata hosts", () => {
    expect(filterWebhookPayload({ a: 1, body: "secret" }, ["a"])).toEqual({ a: 1 });
    expect(filterWebhookPayload({ a: 1 }, [])).toEqual({ a: 1 });
    expect(() => assertSafeWebhookUrl("ftp://x/y")).toThrow();
    expect(() => assertSafeWebhookUrl("http://169.254.169.254/x")).toThrow();
    expect(() => assertSafeWebhookUrl("http://localhost:9/hook")).not.toThrow();
  });
});
