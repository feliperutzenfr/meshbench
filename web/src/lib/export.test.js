import { describe, expect, it } from "vitest";
import {
  FORMAT_LABELS,
  budgetClass,
  namingForFormat,
  validNaming,
} from "./export.js";

describe("FORMAT_LABELS", () => {
  it("cobre os 3 formatos e destaca o alvo Promob", () => {
    expect(Object.keys(FORMAT_LABELS)).toEqual(["dxf_r12", "stl", "obj"]);
    expect(FORMAT_LABELS.dxf_r12).toMatch(/Promob/);
  });
});

describe("budgetClass", () => {
  it("semáforo: verde ≤8k, amarelo ≤15k, vermelho acima", () => {
    expect(budgetClass(2000, 15000)).toBe("verde");
    expect(budgetClass(8000, 15000)).toBe("verde");
    expect(budgetClass(8001, 15000)).toBe("amarelo");
    expect(budgetClass(15000, 15000)).toBe("amarelo");
    expect(budgetClass(15001, 15000)).toBe("vermelho");
  });
});

describe("namingForFormat", () => {
  it("troca a extensão do nome para casar com o formato", () => {
    expect(namingForFormat("{project}_{group}.dxf", "stl")).toBe("{project}_{group}.stl");
    expect(namingForFormat("{group}.stl", "dxf_r12")).toBe("{group}.dxf");
    expect(namingForFormat("{group}.obj", "obj")).toBe("{group}.obj");
  });

  it("não confunde os pontos dos placeholders com a extensão", () => {
    // sem extensão real: acrescenta a do formato em vez de mexer no {group}
    expect(namingForFormat("{group}", "stl")).toBe("{group}.stl");
  });
});

describe("validNaming", () => {
  it("exige o placeholder {group}", () => {
    expect(validNaming("{project}_{group}.dxf")).toBe(true);
    expect(validNaming("fixo.dxf")).toBe(false);
    expect(validNaming(null)).toBe(false);
  });
});
