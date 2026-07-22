// Export (§10 do doc): DXF R12 (3DFACE) é o alvo Promob; STL/OBJ para outros usos.
// O semáforo de faces reflete o orçamento empírico do Promob (§ orçamento).
export const FORMAT_LABELS = {
  dxf_r12: "DXF R12 (3DFACE) — Promob",
  stl: "STL",
  obj: "OBJ",
};

export const FORMAT_EXT = { dxf_r12: "dxf", stl: "stl", obj: "obj" };

// semáforo: verde até 8000 (fixo, conforme o doc); o parâmetro `budget` (15000)
// controla só a fronteira amarelo/vermelho.
export function budgetClass(faces, budget = 15000) {
  if (faces <= 8000) return "verde";
  if (faces <= budget) return "amarelo";
  return "vermelho";
}

// troca só a extensão FINAL do nome; um segmento final sem ponto (ex.: "{group}")
// recebe a extensão do formato acrescentada. Não toca nos pontos dos placeholders.
export function namingForFormat(naming, format) {
  const ext = FORMAT_EXT[format] || "dxf";
  if (/\.[a-z0-9]+$/i.test(naming)) return naming.replace(/\.[a-z0-9]+$/i, "." + ext);
  return naming + "." + ext;
}

// {group} só é obrigatório com 2+ grupos (2+ arquivos de saída): aí grupos
// diferentes precisam de nomes diferentes, senão um sobrescreve o arquivo do
// outro. Com um grupo só não há colisão possível, então o nome pode ser livre
// (só não pode ser vazio).
export function validNaming(naming, groupCount = 0) {
  if (typeof naming !== "string" || !naming.trim()) return false;
  if (groupCount >= 2) return naming.includes("{group}");
  return true;
}
