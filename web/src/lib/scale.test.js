import { describe, expect, it } from "vitest";
import {
  SCALE_MODE_LABELS,
  SCALE_MODES,
  buildScaleChanges,
  isSuspiciousDims,
  unitComparison,
} from "./scale.js";

describe("scale helpers", () => {
  it("todo modo tem rótulo pt-BR", () => {
    for (const m of SCALE_MODES) expect(SCALE_MODE_LABELS[m]).toBeTruthy();
  });

  it("buildScaleChanges: unit_convert", () => {
    expect(buildScaleChanges("unit_convert", { fromUnit: "in", toUnit: "mm" })).toEqual({
      scale: { mode: "unit_convert", from_unit: "in", to_unit: "mm" },
    });
  });

  it("buildScaleChanges: uniform coage string e vazio vira 1", () => {
    expect(buildScaleChanges("uniform", { value: "0.5" })).toEqual({
      scale: { mode: "uniform", value: 0.5 },
    });
    expect(buildScaleChanges("uniform", { value: "" })).toEqual({
      scale: { mode: "uniform", value: 1 },
    });
  });

  it("buildScaleChanges: per_axis", () => {
    expect(buildScaleChanges("per_axis", { sx: "1", sy: "2", sz: "" })).toEqual({
      scale: { mode: "per_axis", per_axis: [1, 2, 1] },
    });
  });

  it("buildScaleChanges: fit_dimension", () => {
    expect(buildScaleChanges("fit_dimension", { axis: "x", target: "450" })).toEqual({
      scale: { mode: "fit_dimension", fit: { axis: "x", target_mm: 450 } },
    });
  });

  it("unitComparison monta a comparação humana", () => {
    const c = unitComparison(1000);
    const mm = c.find((x) => x.unit === "mm");
    const pol = c.find((x) => x.unit === "in");
    expect(mm.mm).toBe(1000);
    expect(mm.human).toBe("1,00 m");
    expect(pol.mm).toBeCloseTo(25400);
    expect(pol.human).toBe("25,40 m");
  });

  it("isSuspiciousDims", () => {
    expect(isSuspiciousDims([100, 200, 300])).toBe(false);
    expect(isSuspiciousDims([0.5, 200, 300])).toBe(true);
    expect(isSuspiciousDims([100, 6000, 300])).toBe(true);
    expect(isSuspiciousDims(null)).toBe(false);
  });
});
