import { describe, expect, it } from "vitest";
import { budgetLevel, formatDims, formatFaces } from "./format.js";

describe("formatFaces", () => {
  it("usa separador de milhar pt-BR", () => {
    expect(formatFaces(4978)).toBe("4.978");
  });
});

describe("formatDims", () => {
  it("formata mm com 1 casa", () => {
    expect(formatDims([450, 234, 457.31])).toBe("450.0 × 234.0 × 457.3 mm");
  });
  it("null vira travessão", () => {
    expect(formatDims(null)).toBe("—");
  });
});

describe("budgetLevel", () => {
  it("verde até 8k, amarelo até 15k, vermelho acima", () => {
    expect(budgetLevel(2000)).toBe("verde");
    expect(budgetLevel(12000)).toBe("amarelo");
    expect(budgetLevel(15001)).toBe("vermelho");
  });
});
