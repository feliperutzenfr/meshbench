// Origem (§8 do doc): âncora no bbox (8 cantos + centro), modo comum/por grupo
// e snap por clique. O clique NÃO grava snap_point: vira ajuste de offset
// (novo = velho + ponto do mundo) — reprodutível e funciona nos dois modos.
const SIGN = { 0: "−", 1: "+" };

// bbox_min ≡ corner_000 — mostramos bbox_min (o default da receita) e omitimos o duplicado
export const ANCHOR_OPTIONS = [
  { value: "bbox_min", label: "canto mínimo (X− Y− Z−)" },
  { value: "center", label: "centro" },
  ...["001", "010", "011", "100", "101", "110", "111"].map((bits) => ({
    value: `corner_${bits}`,
    label: `canto X${SIGN[bits[0]]} Y${SIGN[bits[1]]} Z${SIGN[bits[2]]}`,
  })),
];

// §8.2: a consequência da troca não é óbvia — explicar em uma frase na UI
export const MODE_EXPLAIN = {
  common: "arquivos exportados caem encaixados no destino (mesmo referencial)",
  per_group: "cada arquivo zera no próprio canto — você posiciona no destino",
};

export function addSnapOffset(origin, point) {
  const offset = (origin.offset || [0, 0, 0]).map(
    (o, i) => Math.round((o + point[i]) * 100) / 100,
  );
  return { offset };
}
