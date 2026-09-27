import { describe, expect, it } from "vitest";
import type { Spec } from "../types";
import { MAX_EDIT_TURNS, recordExchange, withTurns } from "./editMemory";

const spec = { schema_version: "1.0", template: "ramp", params: {}, assumed: [], parts: [], rule_checks: [], meta: { contractor_quote_cad: 4000 } } as Spec;

describe("edit memory", () => {
  it("records a user/assistant exchange", () => {
    const turns = recordExchange([], " make it wider ", "How much wider?");
    expect(turns).toEqual([
      { role: "user", text: "make it wider" },
      { role: "model", text: "How much wider?" },
    ]);
  });

  it("keeps only the most recent exchanges", () => {
    let turns = recordExchange([], "u0", "m0");
    for (let i = 1; i < 8; i++) turns = recordExchange(turns, `u${i}`, `m${i}`);
    expect(turns).toHaveLength(MAX_EDIT_TURNS);
    expect(turns[0]).toEqual({ role: "user", text: "u3" });
    expect(turns.at(-1)).toEqual({ role: "model", text: "m7" });
  });

  it("sends the turns in meta without touching the rest of the spec", () => {
    const turns = recordExchange([], "make it wider", "How much wider?");
    const sent = withTurns(spec, turns);
    expect(sent.meta.edit_turns).toEqual(turns);
    expect(sent.meta.contractor_quote_cad).toBe(4000);
    expect(spec.meta).not.toHaveProperty("edit_turns");
    expect(withTurns(spec, [])).toBe(spec);
  });
});
