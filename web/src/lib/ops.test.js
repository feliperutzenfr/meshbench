import { describe, expect, it } from "vitest";
import { OP_LABELS, OP_TYPES, coerceParams, opDefaults } from "./ops.js";

describe("ops", () => {
  it("todo tipo tem rótulo pt-BR", () => {
    for (const t of OP_TYPES) expect(OP_LABELS[t]).toBeTruthy();
  });

  it("defaults por operação", () => {
    expect(opDefaults("decimate")).toEqual({ percent: 25 });
    expect(opDefaults("tube")).toEqual({ sides: 8, bin_mm: 3.0, radius: "" });
    expect(opDefaults("reextrude")).toEqual({ axis: "auto", n_probe: 25, tol: 0.4 });
    expect(opDefaults("keep")).toEqual({});
  });

  it("coerceParams: decimate com face_count tem precedência", () => {
    expect(coerceParams("decimate", { percent: "25", face_count: "80" })).toEqual({
      face_count: 80,
    });
    expect(coerceParams("decimate", { percent: "10" })).toEqual({ percent: 10 });
  });

  it("coerceParams: tube omite radius vazio", () => {
    expect(coerceParams("tube", { sides: "8", bin_mm: "3", radius: "" })).toEqual({
      sides: 8,
      bin_mm: 3,
    });
    expect(coerceParams("tube", { sides: "6", bin_mm: "2.5", radius: "4" })).toEqual({
      sides: 6,
      bin_mm: 2.5,
      radius: 4,
    });
  });

  it("coerceParams: reextrude converte eixo e omite auto", () => {
    expect(coerceParams("reextrude", { axis: "auto", n_probe: "25", tol: "0.4" })).toEqual({
      n_probe: 25,
      tol: 0.4,
    });
    expect(coerceParams("reextrude", { axis: "z", n_probe: "10", tol: "1.5" })).toEqual({
      axis: 2,
      n_probe: 10,
      tol: 1.5,
    });
  });

  it("coerceParams: keep/remove/hull sem params", () => {
    expect(coerceParams("keep", {})).toEqual({});
    expect(coerceParams("hull", { lixo: 1 })).toEqual({});
  });

  it("coerceParams: campos numéricos vazios caem nos defaults (não em 0)", () => {
    expect(coerceParams("decimate", { percent: "" })).toEqual({ percent: 25 });
    expect(coerceParams("tube", { sides: "", bin_mm: "", radius: "" })).toEqual({
      sides: 8,
      bin_mm: 3.0,
    });
    expect(coerceParams("reextrude", { axis: "auto", n_probe: "", tol: "" })).toEqual({
      n_probe: 25,
      tol: 0.4,
    });
  });

  it("coerceParams: face_count inválido cai no percent", () => {
    expect(coerceParams("decimate", { percent: "10", face_count: "abc" })).toEqual({
      percent: 10,
    });
    expect(coerceParams("decimate", { percent: "", face_count: "" })).toEqual({ percent: 25 });
  });
});
