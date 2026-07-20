import { describe, expect, it } from "vitest";
import { ANCHOR_OPTIONS, MODE_EXPLAIN, addSnapOffset } from "./origin.js";

describe("ANCHOR_OPTIONS", () => {
  it("tem 9 âncoras (bbox_min + centro + 7 cantos) sem duplicar corner_000", () => {
    const values = ANCHOR_OPTIONS.map((o) => o.value);
    expect(values).toHaveLength(9);
    expect(values).toContain("bbox_min");
    expect(values).toContain("center");
    expect(values).toContain("corner_111");
    expect(values).not.toContain("corner_000"); // ≡ bbox_min
    expect(new Set(values).size).toBe(9);
  });

  it("todo option tem rótulo pt-BR não vazio", () => {
    for (const o of ANCHOR_OPTIONS) expect(o.label.length).toBeGreaterThan(0);
  });
});

describe("MODE_EXPLAIN", () => {
  it("explica os dois modos em uma frase", () => {
    expect(MODE_EXPLAIN.common).toMatch(/encaixad/);
    expect(MODE_EXPLAIN.per_group).toMatch(/pr[óo]prio/);
  });
});

describe("addSnapOffset", () => {
  it("soma o ponto clicado ao offset e arredonda a 0,01 mm", () => {
    expect(addSnapOffset({ offset: [1, 2, 3] }, [0.01, -1, 10.126])).toEqual({
      offset: [1.01, 1, 13.13],
    });
  });

  it("offset ausente conta como [0,0,0]", () => {
    expect(addSnapOffset({}, [1.5, 0, -2])).toEqual({ offset: [1.5, 0, -2] });
  });
});
