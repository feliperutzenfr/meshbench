// Operações do motor e seus parâmetros — todos expostos na UI (§6 do doc).
export const OP_TYPES = ["keep", "remove", "decimate", "hull", "tube", "reextrude"];

export const OP_LABELS = {
  keep: "manter",
  remove: "remover",
  decimate: "decimar",
  hull: "casco convexo",
  tube: "tubo",
  reextrude: "re-extrudar",
};

// Defaults iguais aos do core (ops/basic.py, ops/tube.py, ops/reextrude.py).
export function opDefaults(type) {
  if (type === "decimate") return { percent: 25 };
  if (type === "tube") return { sides: 8, bin_mm: 3.0, radius: "" };
  if (type === "reextrude") return { axis: "auto", n_probe: 25, tol: 0.4 };
  return {};
}

// Converte params do formulário (strings) para o corpo do PATCH/preview.
export function coerceParams(type, params) {
  const out = {};
  if (type === "decimate") {
    if (params.face_count) out.face_count = Math.round(Number(params.face_count));
    else out.percent = Number(params.percent ?? 25);
  } else if (type === "tube") {
    out.sides = Math.round(Number(params.sides ?? 8));
    out.bin_mm = Number(params.bin_mm ?? 3.0);
    if (params.radius !== "" && params.radius != null) out.radius = Number(params.radius);
  } else if (type === "reextrude") {
    if (params.axis && params.axis !== "auto") out.axis = { x: 0, y: 1, z: 2 }[params.axis];
    out.n_probe = Math.round(Number(params.n_probe ?? 25));
    out.tol = Number(params.tol ?? 0.4);
  }
  return out;
}
