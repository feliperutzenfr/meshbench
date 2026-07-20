// Orientação (§7 do doc): remap por preset (nunca hardcodado), snap de 90°
// como caminho padrão, rotação livre em graus na ordem X→Y→Z.
export const REMAP_LABELS = {
  identidade: "identidade",
  cad_to_promob: "CAD → Promob (x,z,y)",
  z_up_to_y_up: "Z-up → Y-up",
  y_up_to_z_up: "Y-up → Z-up",
  custom: "personalizado",
};

// Append cru — o servidor normaliza (mod 360, funde consecutivas, descarta 0).
export function addRotation(orient, axis, deg) {
  return { ...orient, rotations: [...orient.rotations, { axis, deg }] };
}

export function toggleMirror(orient, axis) {
  const mirror = orient.mirror.includes(axis)
    ? orient.mirror.filter((m) => m !== axis)
    : [...orient.mirror, axis];
  return { ...orient, mirror };
}

export function buildFreeRotation(orient, rx, ry, rz) {
  let out = orient;
  for (const [axis, v] of [["x", rx], ["y", ry], ["z", rz]]) {
    const n = Number(v);
    if (v !== "" && v != null && !Number.isNaN(n) && n !== 0) {
      out = addRotation(out, axis, n);
    }
  }
  return out;
}

// Arrasto do gizmo com TODOS os eixos abaixo deste limiar é ruído de mouse
// (ex.: 1px de tremor num anel) — não deve virar uma mutação na receita nem
// disparar um reprocesso. Um arrasto deliberado que passe do limiar em pelo
// menos um eixo mantém seus eixos secundários pequenos (rotação composta).
const MIN_GIZMO_DEG = 0.5;

// Gizmo → receita: a nossa lista [x, y, z] aplicada em sequência (cada rotação
// em torno do eixo do MUNDO, a última multiplica à esquerda) equivale ao Euler
// 'ZYX' do three.js — decompor com 'XYZ' daria o resultado ERRADO. Radianos →
// graus arredondados a 0,1°; zeros descartados (o servidor normaliza o resto).
export function eulerToRotations(ex, ey, ez) {
  const rots = [];
  for (const [axis, rad] of [["x", ex], ["y", ey], ["z", ez]]) {
    const deg = Math.round(((rad * 180) / Math.PI) * 10) / 10;
    if (deg !== 0) rots.push({ axis, deg });
  }
  if (!rots.some((r) => Math.abs(r.deg) >= MIN_GIZMO_DEG)) return [];
  return rots;
}
