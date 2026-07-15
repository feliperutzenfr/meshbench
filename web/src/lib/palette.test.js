import { describe, expect, it } from "vitest";
import { GROUP_COLORS, groupColor } from "./palette.js";

describe("groupColor", () => {
  it("é determinística pela ordem dos grupos", () => {
    const groups = ["fixa", "movel"];
    expect(groupColor("fixa", groups)).toBe(GROUP_COLORS[0]);
    expect(groupColor("movel", groups)).toBe(GROUP_COLORS[1]);
  });
  it("grupo desconhecido cai na primeira cor", () => {
    expect(groupColor("fantasma", ["a"])).toBe(GROUP_COLORS[0]);
  });
  it("dá a volta quando há mais grupos que cores", () => {
    const groups = Array.from({ length: GROUP_COLORS.length + 1 }, (_, i) => `g${i}`);
    expect(groupColor(`g${GROUP_COLORS.length}`, groups)).toBe(GROUP_COLORS[0]);
  });
});
