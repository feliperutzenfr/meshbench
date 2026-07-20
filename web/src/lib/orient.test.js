import { describe, expect, it } from "vitest";
import { REMAP_LABELS, addRotation, buildFreeRotation, toggleMirror, eulerToRotations } from "./orient.js";

const base = { axis_remap: "identidade", custom_remap: null, rotations: [], mirror: [] };

describe("orient helpers", () => {
  it("rótulos pt-BR para todos os presets + custom", () => {
    for (const k of ["identidade", "cad_to_promob", "z_up_to_y_up", "y_up_to_z_up", "custom"])
      expect(REMAP_LABELS[k]).toBeTruthy();
  });

  it("addRotation é imutável e acumula", () => {
    const o1 = addRotation(base, "x", 90);
    expect(o1.rotations).toEqual([{ axis: "x", deg: 90 }]);
    expect(base.rotations).toEqual([]);
    const o2 = addRotation(o1, "z", -90);
    expect(o2.rotations).toEqual([
      { axis: "x", deg: 90 },
      { axis: "z", deg: -90 },
    ]);
  });

  it("toggleMirror liga e desliga", () => {
    const on = toggleMirror(base, "x");
    expect(on.mirror).toEqual(["x"]);
    expect(toggleMirror(on, "x").mirror).toEqual([]);
    expect(base.mirror).toEqual([]);
  });

  it("buildFreeRotation na ordem x→y→z, ignorando zeros e lixo", () => {
    const o = buildFreeRotation(base, "45", "", "abc");
    expect(o.rotations).toEqual([{ axis: "x", deg: 45 }]);
    const o2 = buildFreeRotation(base, "10", "20", "30");
    expect(o2.rotations).toEqual([
      { axis: "x", deg: 10 },
      { axis: "y", deg: 20 },
      { axis: "z", deg: 30 },
    ]);
  });
});

describe("eulerToRotations", () => {
  it("converte radianos para a lista x→y→z em graus", () => {
    expect(eulerToRotations(Math.PI / 2, 0, -Math.PI)).toEqual([
      { axis: "x", deg: 90 },
      { axis: "z", deg: -180 },
    ]);
  });

  it("descarta ângulos que arredondam para 0,0°", () => {
    expect(eulerToRotations(0.0001, 0, 0)).toEqual([]);
  });
});
