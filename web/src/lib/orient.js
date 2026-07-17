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
