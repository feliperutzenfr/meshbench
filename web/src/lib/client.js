// Cliente HTTP da API local. Erros HTTP viram Error com o detail do backend.
async function checkOk(r) {
  if (!r.ok) {
    let detail = "";
    try {
      detail = (await r.json()).detail || "";
    } catch {
      /* corpo não-JSON */
    }
    throw new Error(detail || `HTTP ${r.status}`);
  }
  return r;
}

export async function fetchProject() {
  const r = await checkOk(await fetch("/api/project"));
  return r.json();
}

export async function patchComponent(id, changes) {
  const r = await checkOk(
    await fetch(`/api/component/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changes),
    }),
  );
  return r.json();
}

export async function patchScale(changes) {
  const r = await checkOk(
    await fetch("/api/scale", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changes),
    }),
  );
  return r.json();
}

export async function previewComponent(id, operation) {
  const r = await checkOk(
    await fetch(`/api/preview/${id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ operation }),
    }),
  );
  const blob = await r.blob();
  return {
    url: URL.createObjectURL(blob),
    facesBefore: Number(r.headers.get("X-Faces-Before")),
    facesAfter: Number(r.headers.get("X-Faces-After")),
  };
}

export async function saveRecipe() {
  const r = await checkOk(await fetch("/api/project/save", { method: "POST" }));
  return r.json();
}

export async function patchOrient(changes) {
  const r = await checkOk(
    await fetch("/api/orient", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changes),
    }),
  );
  return r.json();
}

export async function postUndo() {
  const r = await checkOk(await fetch("/api/undo", { method: "POST" }));
  return r.json();
}

export async function postRedo() {
  const r = await checkOk(await fetch("/api/redo", { method: "POST" }));
  return r.json();
}

export async function patchOrigin(changes) {
  const r = await checkOk(
    await fetch("/api/origin", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changes),
    }),
  );
  return r.json();
}

// rev na query só para furar cache do navegador quando a sessão muda
export function geometryUrl(revision) {
  return `/api/project/geometry?rev=${revision ?? 0}`;
}
