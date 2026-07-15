export function formatFaces(n) {
  return n.toLocaleString("pt-BR");
}

export function formatDims(dims) {
  if (!dims) return "—";
  return `${dims[0].toFixed(1)} × ${dims[1].toFixed(1)} × ${dims[2].toFixed(1)} mm`;
}

// Semáforo do orçamento de faces (§3.3): verde ≤8k, amarelo ≤15k, vermelho >15k.
export function budgetLevel(faces) {
  if (faces > 15000) return "vermelho";
  if (faces > 8000) return "amarelo";
  return "verde";
}
