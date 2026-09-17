import { describe, expect, it } from "vitest";
import {
  POSITRONIC_SKILL,
  POSITRONIC_TOOLS,
  POSITRONIC_TOOL_DEFS,
  createPositronicHandlers,
  AGENT_MAX_ROUNDS,
} from "../src/skill.js";

describe("skill", () => {
  it("names all three tools with required params", () => {
    const names = POSITRONIC_TOOLS.map((t) => t.function.name);
    expect(names).toEqual(["recall_brain", "query_brain_sql", "ask_brain"]);
    for (const t of POSITRONIC_TOOLS) {
      expect(t.type).toBe("function");
      expect(t.function.parameters.type).toBe("object");
    }
  });
  it("skill text states the grounding contract", () => {
    expect(POSITRONIC_SKILL).toContain("NEVER answer from general knowledge");
    expect(POSITRONIC_SKILL).toContain("exhaustive=true");
  });
  it("bounds the loop", () => {
    expect(AGENT_MAX_ROUNDS).toBeGreaterThanOrEqual(1);
    expect(AGENT_MAX_ROUNDS).toBeLessThanOrEqual(10);
  });
  it("tool defs mirror the OpenAI schemas by name", () => {
    expect(POSITRONIC_TOOL_DEFS.map((d) => d.name)).toEqual(
      POSITRONIC_TOOLS.map((t) => t.function.name),
    );
    for (const d of POSITRONIC_TOOL_DEFS) expect(d.isActive).toBe(true);
  });
  it("handlers recall, guard SQL, and report sources", async () => {
    const seen: string[] = [];
    const h = createPositronicHandlers({
      recall: async () => [
        { subject: "Invoice", sender: "a@b", tau: 2, threat_tag: "clean", snippet: "Total $950" },
      ],
      querySql: async () => [],
      ask: async () => "No object found.",
      onSources: (l) => seen.push(...l),
    });
    const text = await h.recall_brain({ query: "invoice" });
    expect(text).toContain("[1] Invoice");
    expect(text).toContain("$950");
    expect(seen).toEqual(["Invoice"]);
    expect(await h.query_brain_sql({ sql: "DELETE FROM episode" })).toContain("read-only");
    expect(await h.ask_brain({ object: "Sam" })).toBe("No object found.");
  });
});
