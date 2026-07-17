// Escala e unidades (§5 do doc). A heurística só sugere — o usuário confirma.
export const UNIT_MM_JS = { mm: 1, cm: 10, m: 1000, in: 25.4, ft: 304.8 };

export const UNIT_LABELS = {
  mm: "milímetros",
  cm: "centímetros",
  m: "metros",
  in: "polegadas",
  ft: "pés",
};

export const SCALE_MODES = ["unit_convert", "uniform", "per_axis", "fit_dimension"];

export const SCALE_MODE_LABELS = {
  unit_convert: "conversão de unidade",
  uniform: "fator uniforme",
  per_axis: "fator por eixo",
  fit_dimension: "ajustar dimensão",
};

function num(v, d) {
  if (v === "" || v == null) return d;
  const n = Number(v);
  return Number.isNaN(n) ? d : n;
}

// Monta o corpo do PATCH /api/scale a partir dos campos (strings) do formulário.
export function buildScaleChanges(mode, f) {
  if (mode === "unit_convert") {
    return {
      scale: {
        mode,
        from_unit: f.fromUnit || "mm",
        to_unit: f.toUnit || "mm",
      },
    };
  }
  if (mode === "uniform") {
    return { scale: { mode, value: num(f.value, 1) } };
  }
  if (mode === "per_axis") {
    return {
      scale: { mode, per_axis: [num(f.sx, 1), num(f.sy, 1), num(f.sz, 1)] },
    };
  }
  return {
    scale: {
      mode: "fit_dimension",
      fit: { axis: f.axis || "x", target_mm: num(f.target, 0) },
    },
  };
}

function humanMm(mm) {
  if (mm >= 1000) return `${(mm / 1000).toFixed(2).replace(".", ",")} m`;
  return `${mm.toFixed(1).replace(".", ",")} mm`;
}

// §5.2: "Maior dimensão: X. Se for mm → …; se for polegadas → …" — sempre em
// unidade humana, para o erro de escala saltar aos olhos.
export function unitComparison(maxDim) {
  return ["mm", "cm", "in", "m"].map((unit) => {
    const mm = maxDim * UNIT_MM_JS[unit];
    return { unit, label: UNIT_LABELS[unit], mm, human: humanMm(mm) };
  });
}

// §5.4: dimensão absurda (< 1 mm ou > 5000 mm) — mesmos limiares do pipeline.
export function isSuspiciousDims(dims) {
  if (!dims) return false;
  return dims.some((d) => d < 1 || d > 5000);
}
