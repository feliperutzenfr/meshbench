# MeshBench Fase 4 — Escala e Unidades Interativas — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expor na UI os quatro modos de escala do motor (conversão de unidade, fator uniforme, por eixo, ajustar dimensão-alvo), com detecção/confirmação de unidade quando ambígua e validador visual de dimensões — critério de aceite da Fase 4 (§14): "Detecção, conversão, fit-to-dimension, validador".

**Architecture:** O backend ganha `PATCH /api/scale` (session_ops.update_scale valida → aplica → reprocessa → rollback em falha, mesmo padrão do update_component) e o estado passa a expor `source_dims` (extents da malha crua, para a comparação de unidades). O frontend ganha uma barra ESCALA (linha entre o viewport e a barra de status, como no layout §11), com formulário por modo, banner de ambiguidade com botões de confirmação rápida ("é mm / é polegada / é cm"), e o validador §5.4: dimensões resultantes grandes e em vermelho quando suspeitas (<1 mm ou >5000 mm).

**Tech Stack:** FastAPI · React 19 · vitest · pytest

## Global Constraints

- Branch: `fase-4-escala` a partir da `main`.
- **Nada é automático**: a heurística de unidade só sugere (§5.2); a conversão SÓ acontece no botão Aplicar ou nos botões explícitos do banner de ambiguidade. Sempre mostrar o resultado em unidade humana para o erro saltar aos olhos.
- Escala continua sendo a PRIMEIRA etapa do pipeline; o match de componentes por (faces, vértices) + tolerância de bbox já sobrevive a mudanças de fator (fix da Fase 2) — teste deve confirmar que os componentes não somem após uma conversão in→mm.
- ⚠ obrigatório na UI: escala por eixo distorce raios de tubo/perfil (§5.3).
- Validador §5.4: dimensões < 1 mm ou > 5000 mm em vermelho (mesmos limiares do warning "confira a unidade" do pipeline).
- Mutações sob `session.lock` com rollback em falha do reprocesso; validar TUDO antes de atribuir qualquer coisa (nada meio-editado).
- Reprocesso nunca relê o fonte (usa `session.raw_mesh`); revision incrementa a cada mutação (invalida GLB cache e o cache do navegador).
- UI pt-BR; identificadores de código em inglês; Conventional Commits; TDD com RED real.
- Gate por task: `.venv/Scripts/python -m pytest -q` + `npm --prefix web test` + `npm --prefix web run build` verdes.

---

### Task 1: Backend — `update_scale` + `PATCH /api/scale` + `source_dims`

**Files:**
- Modify: `src/meshbench/api/session_ops.py` (novas funções `_validated_scale`, `update_scale`)
- Modify: `src/meshbench/api/server.py` (rota PATCH /api/scale; `source_dims` em `_project_state`)
- Test: `tests/test_api_scale.py`

**Interfaces:**
- Consumes: `reprocess(session)`, `session.lock`, `UNIT_MM` (de `meshbench.core.analyze.units`), `_project_state`.
- Produces:
  - `session_ops.update_scale(session, changes)` — `changes` com chaves opcionais:
    - `"scale"`: dict com `mode` em `{"unit_convert","uniform","per_axis","fit_dimension"}` e os campos do modo; validação completa ANTES de atribuir (ValueError pt-BR); o dict gravado tem sempre o shape completo (`mode/from_unit/to_unit/value/per_axis/fit/factor`).
    - `"units"`: confirmação da unidade do arquivo pelo usuário — grava `source["units"]` e `source["units_confirmed"] = True`.
    - Rollback de `scale` + `units` + `units_confirmed` se o reprocesso falhar.
  - Rota `PATCH /api/scale` → 200 com estado completo; 422 ValueError.
  - `_project_state` ganha `"source_dims"`: extents da malha crua (lista de 3 floats) ou None.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_api_scale.py`:
```python
import pytest
from fastapi.testclient import TestClient

from meshbench.api.server import create_app, load_session
from meshbench.api.session_ops import update_scale


def _client(tmp_path, box):
    p = tmp_path / "caixa.stl"
    box.export(str(p))
    session = load_session(p)
    return TestClient(create_app(session)), session


def test_source_dims_no_estado(tmp_path, box):
    client, _ = _client(tmp_path, box)
    state = client.get("/api/project").json()
    assert state["source_dims"] == pytest.approx([10.0, 20.0, 30.0])


def test_unit_convert_in_para_mm(tmp_path, box):
    client, session = _client(tmp_path, box)
    rev0 = client.get("/api/project").json()["revision"]
    r = client.patch(
        "/api/scale",
        json={"scale": {"mode": "unit_convert", "from_unit": "in", "to_unit": "mm"}},
    )
    assert r.status_code == 200
    state = r.json()
    assert state["dims_mm"] == pytest.approx([254.0, 508.0, 762.0])
    assert state["scale"]["factor"] == pytest.approx([25.4, 25.4, 25.4])
    assert state["revision"] == rev0 + 1
    # o match por tolerância sobrevive à conversão: o componente não some
    assert sum(state["group_faces"].values()) == 12


def test_fit_dimension(tmp_path, box):
    client, _ = _client(tmp_path, box)
    r = client.patch(
        "/api/scale",
        json={"scale": {"mode": "fit_dimension", "fit": {"axis": "x", "target_mm": 450}}},
    )
    assert r.status_code == 200
    assert r.json()["dims_mm"][0] == pytest.approx(450.0)


def test_uniform_e_per_axis(tmp_path, box):
    client, _ = _client(tmp_path, box)
    r = client.patch("/api/scale", json={"scale": {"mode": "uniform", "value": 2}})
    assert r.json()["dims_mm"] == pytest.approx([20.0, 40.0, 60.0])
    r = client.patch(
        "/api/scale", json={"scale": {"mode": "per_axis", "per_axis": [1, 2, 3]}}
    )
    assert r.json()["dims_mm"] == pytest.approx([10.0, 40.0, 90.0])


def test_confirmacao_de_unidade(tmp_path, box):
    client, _ = _client(tmp_path, box)
    r = client.patch("/api/scale", json={"units": "in"})
    assert r.status_code == 200
    src = r.json()["source"]
    assert src["units"] == "in"
    assert src["units_confirmed"] is True


def test_validacoes_422(tmp_path, box):
    client, _ = _client(tmp_path, box)
    casos = [
        ({"scale": {"mode": "magico"}}, "modo de escala"),
        ({"scale": {"mode": "unit_convert", "from_unit": "jardas"}}, "unidade"),
        ({"scale": {"mode": "uniform", "value": -2}}, "positivo"),
        ({"scale": {"mode": "per_axis", "per_axis": [1, 2]}}, "per_axis"),
        ({"scale": {"mode": "fit_dimension", "fit": {"axis": "w", "target_mm": 10}}}, "fit.axis"),
        ({"units": "jardas"}, "unidade"),
    ]
    for body, trecho in casos:
        r = client.patch("/api/scale", json=body)
        assert r.status_code == 422, body
        assert trecho in r.json()["detail"], body


def test_rollback_se_reprocesso_falha(tmp_path, box, monkeypatch):
    _, session = _client(tmp_path, box)
    scale_antes = session.project.scale
    units_antes = session.project.source.get("units")
    rev_antes = session.revision

    import meshbench.api.session_ops as so

    def explode(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(so, "process", explode)
    with pytest.raises(RuntimeError):
        update_scale(
            session,
            {"scale": {"mode": "uniform", "value": 2}, "units": "in"},
        )
    assert session.project.scale == scale_antes
    assert session.project.source.get("units") == units_antes
    assert "units_confirmed" not in session.project.source
    assert session.revision == rev_antes
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_api_scale.py -v`
Expected: FAIL — `source_dims` ausente / 404 na rota / ImportError de `update_scale`

- [ ] **Step 3: Implementar em session_ops.py**

Acrescentar o import no topo de `src/meshbench/api/session_ops.py`:
```python
from meshbench.core.analyze.units import UNIT_MM
```
E as funções (depois de `update_component`):
```python
_SCALE_MODES = ("unit_convert", "uniform", "per_axis", "fit_dimension")


def _validated_scale(spec):
    """Valida e normaliza o spec de escala vindo da UI. Levanta ValueError pt-BR."""
    if not isinstance(spec, dict):
        raise ValueError("corpo sem 'scale' — envie {\"scale\": {...}}")
    mode = spec.get("mode")
    if mode not in _SCALE_MODES:
        raise ValueError(
            f"modo de escala '{mode}' desconhecido (disponíveis: {sorted(_SCALE_MODES)})"
        )
    out = {
        "mode": mode,
        "from_unit": "mm",
        "to_unit": "mm",
        "value": None,
        "per_axis": None,
        "fit": None,
        "factor": [1, 1, 1],
    }
    if mode == "unit_convert":
        from_unit = spec.get("from_unit")
        to_unit = spec.get("to_unit", "mm")
        if from_unit not in UNIT_MM or to_unit not in UNIT_MM:
            raise ValueError(f"unidade inválida (aceitas: {sorted(UNIT_MM)})")
        out["from_unit"], out["to_unit"] = from_unit, to_unit
    elif mode == "uniform":
        value = spec.get("value")
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
            raise ValueError("fator uniforme deve ser um número positivo")
        out["value"] = float(value)
    elif mode == "per_axis":
        per_axis = spec.get("per_axis")
        if (
            not isinstance(per_axis, list)
            or len(per_axis) != 3
            or not all(
                isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0
                for x in per_axis
            )
        ):
            raise ValueError("per_axis deve ser uma lista de 3 números positivos")
        out["per_axis"] = [float(x) for x in per_axis]
    else:  # fit_dimension
        fit = spec.get("fit") or {}
        axis = fit.get("axis")
        target = fit.get("target_mm")
        if axis not in ("x", "y", "z"):
            raise ValueError("fit.axis deve ser x, y ou z")
        if not isinstance(target, (int, float)) or isinstance(target, bool) or target <= 0:
            raise ValueError("fit.target_mm deve ser um número positivo")
        out["fit"] = {"axis": axis, "target_mm": float(target)}
    return out


def update_scale(session, changes):
    """Aplica mudança de escala e/ou confirmação de unidade e reprocessa.

    Valida TUDO antes de atribuir qualquer coisa; rollback completo se o
    reprocesso falhar — nada fica meio-editado.
    """
    with session.lock:
        new_scale = None
        new_units = None
        if "scale" in changes:
            new_scale = _validated_scale(changes["scale"])
        if "units" in changes:
            new_units = changes["units"]
            if new_units not in UNIT_MM:
                raise ValueError(f"unidade '{new_units}' inválida (aceitas: {sorted(UNIT_MM)})")

        source = session.project.source
        snapshot = (
            session.project.scale,
            source.get("units"),
            "units_confirmed" in source,
            source.get("units_confirmed"),
        )
        if new_scale is not None:
            session.project.scale = new_scale
        if new_units is not None:
            source["units"] = new_units
            source["units_confirmed"] = True
        try:
            reprocess(session)
        except Exception:
            session.project.scale = snapshot[0]
            source["units"] = snapshot[1]
            if snapshot[2]:
                source["units_confirmed"] = snapshot[3]
            else:
                source.pop("units_confirmed", None)
            raise
```

- [ ] **Step 4: Implementar em server.py**

Import: trocar a linha de imports do session_ops por:
```python
from meshbench.api.session_ops import (
    preview_op,
    save_recipe,
    update_component,
    update_scale,
)
```
Em `_project_state`, acrescentar ao dict retornado (junto de `dims_mm`):
```python
            "source_dims": (
                [float(x) for x in session.raw_mesh.extents]
                if session.raw_mesh is not None
                else None
            ),
```
Nova rota, junto das outras (antes do mount estático):
```python
    @app.patch("/api/scale")
    def patch_scale(changes: dict):
        try:
            update_scale(session, changes)
        except ValueError as e:
            return JSONResponse(status_code=422, content={"detail": str(e)})
        return JSONResponse(_project_state(session))
```

- [ ] **Step 5: Rodar para ver passar + suíte inteira**

Run: `.venv/Scripts/python -m pytest tests/test_api_scale.py -v && .venv/Scripts/python -m pytest -q`
Expected: 7 novos passam; suíte toda verde (127+7)

- [ ] **Step 6: Commit**

```bash
git add src/meshbench/api/session_ops.py src/meshbench/api/server.py tests/test_api_scale.py
git commit -m "feat: PATCH /api/scale — modos de escala, confirmação de unidade e source_dims"
```

---

### Task 2: Frontend — helpers `lib/scale.js` + `patchScale` no client

**Files:**
- Create: `web/src/lib/scale.js`
- Create: `web/src/lib/scale.test.js`
- Modify: `web/src/lib/client.js` (patchScale)

**Interfaces:**
- Produces (scale.js):
  - `UNIT_MM_JS = { mm: 1, cm: 10, m: 1000, in: 25.4, ft: 304.8 }` e `UNIT_LABELS` pt-BR (`mm: "milímetros"`, `cm: "centímetros"`, `m: "metros"`, `in: "polegadas"`, `ft: "pés"`).
  - `SCALE_MODES = ["unit_convert", "uniform", "per_axis", "fit_dimension"]` e `SCALE_MODE_LABELS` pt-BR (`unit_convert: "conversão de unidade"`, `uniform: "fator uniforme"`, `per_axis: "fator por eixo"`, `fit_dimension: "ajustar dimensão"`).
  - `buildScaleChanges(mode, fields) -> object` — monta o corpo do PATCH a partir dos campos do formulário (strings); campos vazios/ inválidos caem nos defaults (1 para fatores, "mm" para unidades, "x"/0 para fit — 0 deixará o backend responder 422, que a UI mostra).
  - `unitComparison(maxDim) -> [{unit, label, mm, human}]` — para o banner §5.2: o que a maior dimensão vira em mm se o arquivo estiver em mm/cm/in/m, com `human` formatado ("25,40 m" quando ≥1000 mm, senão "450,0 mm").
  - `isSuspiciousDims(dims) -> bool` — `true` quando alguma dimensão < 1 mm ou > 5000 mm (§5.4; mesmos limiares do warning do pipeline).
- Produces (client.js): `patchScale(changes) -> state` (PATCH /api/scale, mesmo tratamento de erro dos demais).

- [ ] **Step 1: Escrever os testes que falham**

`web/src/lib/scale.test.js`:
```js
import { describe, expect, it } from "vitest";
import {
  SCALE_MODE_LABELS,
  SCALE_MODES,
  buildScaleChanges,
  isSuspiciousDims,
  unitComparison,
} from "./scale.js";

describe("scale helpers", () => {
  it("todo modo tem rótulo pt-BR", () => {
    for (const m of SCALE_MODES) expect(SCALE_MODE_LABELS[m]).toBeTruthy();
  });

  it("buildScaleChanges: unit_convert", () => {
    expect(buildScaleChanges("unit_convert", { fromUnit: "in", toUnit: "mm" })).toEqual({
      scale: { mode: "unit_convert", from_unit: "in", to_unit: "mm" },
    });
  });

  it("buildScaleChanges: uniform coage string e vazio vira 1", () => {
    expect(buildScaleChanges("uniform", { value: "0.5" })).toEqual({
      scale: { mode: "uniform", value: 0.5 },
    });
    expect(buildScaleChanges("uniform", { value: "" })).toEqual({
      scale: { mode: "uniform", value: 1 },
    });
  });

  it("buildScaleChanges: per_axis", () => {
    expect(buildScaleChanges("per_axis", { sx: "1", sy: "2", sz: "" })).toEqual({
      scale: { mode: "per_axis", per_axis: [1, 2, 1] },
    });
  });

  it("buildScaleChanges: fit_dimension", () => {
    expect(buildScaleChanges("fit_dimension", { axis: "x", target: "450" })).toEqual({
      scale: { mode: "fit_dimension", fit: { axis: "x", target_mm: 450 } },
    });
  });

  it("unitComparison monta a comparação humana", () => {
    const c = unitComparison(1000);
    const mm = c.find((x) => x.unit === "mm");
    const pol = c.find((x) => x.unit === "in");
    expect(mm.mm).toBe(1000);
    expect(mm.human).toBe("1,00 m");
    expect(pol.mm).toBeCloseTo(25400);
    expect(pol.human).toBe("25,40 m");
  });

  it("isSuspiciousDims", () => {
    expect(isSuspiciousDims([100, 200, 300])).toBe(false);
    expect(isSuspiciousDims([0.5, 200, 300])).toBe(true);
    expect(isSuspiciousDims([100, 6000, 300])).toBe(true);
    expect(isSuspiciousDims(null)).toBe(false);
  });
});
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `npm --prefix web test`
Expected: FAIL — módulo `./scale.js` não existe

- [ ] **Step 3: Implementar scale.js**

`web/src/lib/scale.js`:
```js
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
```

- [ ] **Step 4: patchScale no client.js**

Acrescentar em `web/src/lib/client.js` (junto de patchComponent):
```js
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
```

- [ ] **Step 5: Rodar para ver passar**

Run: `npm --prefix web test && npm --prefix web run build && .venv/Scripts/python -m pytest -q`
Expected: vitest 22 (15 + 7 novos), build OK, pytest verde

- [ ] **Step 6: Commit**

```bash
git add web/src/lib/scale.js web/src/lib/scale.test.js web/src/lib/client.js
git commit -m "feat: helpers de escala/unidades e patchScale no frontend"
```

---

### Task 3: Frontend — barra ESCALA + banner de ambiguidade + validador visual

**Files:**
- Create: `web/src/components/ScaleBar.jsx`
- Modify: `web/src/App.jsx` (renderizar ScaleBar)
- Modify: `web/src/components/StatusBar.jsx` (dims em vermelho quando suspeitas)
- Modify: `web/src/styles.css` (linha scalebar no grid + estilos)

**Interfaces:**
- Consumes: `patchScale`, `buildScaleChanges`, `unitComparison`, `isSuspiciousDims`, `SCALE_MODES`, `SCALE_MODE_LABELS`, `UNIT_LABELS`, `UNIT_MM_JS` (Task 2); `formatDims` (format.js); `state.source` (`detected_units`, `detection_note`, `units`, `units_confirmed`), `state.source_dims`, `state.scale`, `state.dims_mm`.
- Produces: `ScaleBar {state, onStateChange}` — formulário por modo + Aplicar; banner de ambiguidade quando `detection_note` contém "ambíguo" e `!source.units_confirmed`, com botões "é mm"/"é cm"/"é polegada" que fazem PATCH `{units: X, scale: {mode: "unit_convert", from_unit: X, to_unit: "mm"}}`; resultado "→ L × A × P mm" com classe `suspeito` quando `isSuspiciousDims`.

- [ ] **Step 1: Criar ScaleBar.jsx**

`web/src/components/ScaleBar.jsx`:
```jsx
import { useEffect, useState } from "react";
import { patchScale } from "../lib/client.js";
import { formatDims } from "../lib/format.js";
import {
  SCALE_MODE_LABELS,
  SCALE_MODES,
  UNIT_LABELS,
  buildScaleChanges,
  isSuspiciousDims,
  unitComparison,
} from "../lib/scale.js";

function CampoNum({ nome, valor, step, onChange }) {
  return (
    <label className="campo-inline">
      <span>{nome}</span>
      <input
        type="number"
        step={step ?? 0.1}
        value={valor ?? ""}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}

export default function ScaleBar({ state, onStateChange }) {
  const [mode, setMode] = useState("unit_convert");
  const [fields, setFields] = useState({ fromUnit: "mm", toUnit: "mm" });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);

  // sincroniza o formulário com a escala vigente da receita
  useEffect(() => {
    const s = state.scale || {};
    setMode(s.mode || "unit_convert");
    setFields({
      fromUnit: s.from_unit || "mm",
      toUnit: s.to_unit || "mm",
      value: s.value ?? "",
      sx: s.per_axis?.[0] ?? "",
      sy: s.per_axis?.[1] ?? "",
      sz: s.per_axis?.[2] ?? "",
      axis: s.fit?.axis || "x",
      target: s.fit?.target_mm ?? "",
    });
    setMsg(null);
  }, [state.revision]); // eslint-disable-line react-hooks/exhaustive-deps

  const setField = (k, v) => setFields((f) => ({ ...f, [k]: v }));

  const aplicar = async (changes) => {
    setBusy(true);
    setMsg(null);
    try {
      onStateChange(await patchScale(changes));
    } catch (e) {
      setMsg(`erro: ${e.message}`);
    }
    setBusy(false);
  };

  const source = state.source || {};
  const ambigua =
    (source.detection_note || "").includes("ambíguo") && !source.units_confirmed;
  const maxDim = state.source_dims ? Math.max(...state.source_dims) : null;

  return (
    <div className="scalebar">
      {ambigua && maxDim != null && (
        <div className="banner-unidade">
          <span>
            ⚠ unidade ambígua — maior dimensão do arquivo: {maxDim.toFixed(1)}.{" "}
            {unitComparison(maxDim)
              .slice(0, 3)
              .map((c) => `se ${UNIT_LABELS[c.unit]} → ${c.human}`)
              .join("; ")}
          </span>
          {["mm", "cm", "in"].map((u) => (
            <button
              key={u}
              className="btn mini"
              disabled={busy}
              onClick={() =>
                aplicar({
                  units: u,
                  scale: { mode: "unit_convert", from_unit: u, to_unit: "mm" },
                })
              }
            >
              é {UNIT_LABELS[u]}
            </button>
          ))}
        </div>
      )}
      <div className="scalebar-linha">
        <span className="rotulo">ESCALA</span>
        <select value={mode} onChange={(e) => setMode(e.target.value)}>
          {SCALE_MODES.map((m) => (
            <option key={m} value={m}>
              {SCALE_MODE_LABELS[m]}
            </option>
          ))}
        </select>

        {mode === "unit_convert" && (
          <>
            <label className="campo-inline">
              <span>de</span>
              <select
                value={fields.fromUnit}
                onChange={(e) => setField("fromUnit", e.target.value)}
              >
                {Object.keys(UNIT_LABELS).map((u) => (
                  <option key={u} value={u}>
                    {UNIT_LABELS[u]}
                  </option>
                ))}
              </select>
            </label>
            <label className="campo-inline">
              <span>para</span>
              <select
                value={fields.toUnit}
                onChange={(e) => setField("toUnit", e.target.value)}
              >
                {Object.keys(UNIT_LABELS).map((u) => (
                  <option key={u} value={u}>
                    {UNIT_LABELS[u]}
                  </option>
                ))}
              </select>
            </label>
          </>
        )}
        {mode === "uniform" && (
          <CampoNum nome="fator" valor={fields.value} onChange={(v) => setField("value", v)} />
        )}
        {mode === "per_axis" && (
          <>
            <CampoNum nome="sx" valor={fields.sx} onChange={(v) => setField("sx", v)} />
            <CampoNum nome="sy" valor={fields.sy} onChange={(v) => setField("sy", v)} />
            <CampoNum nome="sz" valor={fields.sz} onChange={(v) => setField("sz", v)} />
            <span className="alerta-inline">⚠ distorce raios de tubo/perfil</span>
          </>
        )}
        {mode === "fit_dimension" && (
          <>
            <label className="campo-inline">
              <span>eixo</span>
              <select value={fields.axis} onChange={(e) => setField("axis", e.target.value)}>
                <option value="x">x (largura)</option>
                <option value="y">y (profundidade)</option>
                <option value="z">z (altura)</option>
              </select>
            </label>
            <CampoNum
              nome="alvo (mm)"
              step={1}
              valor={fields.target}
              onChange={(v) => setField("target", v)}
            />
          </>
        )}

        <button
          className="btn primario"
          disabled={busy}
          onClick={() => aplicar(buildScaleChanges(mode, fields))}
        >
          Aplicar
        </button>
        <span className={"dims-resultado" + (isSuspiciousDims(state.dims_mm) ? " suspeito" : "")}>
          → {formatDims(state.dims_mm)}
        </span>
        {msg && <span className="msg">{msg}</span>}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Renderizar no App.jsx**

Em `web/src/App.jsx`: importar `import ScaleBar from "./components/ScaleBar.jsx";` e, no JSX, entre `</main>`+`<Inspector …/>` e `<StatusBar …/>`, acrescentar:
```jsx
      <ScaleBar state={state} onStateChange={handleStateChange} />
```

- [ ] **Step 3: Dims suspeitas na StatusBar**

Em `web/src/components/StatusBar.jsx`: importar `import { isSuspiciousDims } from "../lib/scale.js";` e trocar a linha das dims por:
```jsx
      <span className={"dims" + (isSuspiciousDims(state.dims_mm) ? " suspeito" : "")}>
        {formatDims(state.dims_mm)}
      </span>
```

- [ ] **Step 4: CSS**

Em `web/src/styles.css`, trocar a regra `.app` por:
```css
.app {
  display: grid;
  grid-template-columns: 300px 1fr 280px;
  grid-template-rows: 1fr auto auto;
  grid-template-areas:
    "sidebar viewport inspector"
    "sidebar scalebar scalebar"
    "sidebar statusbar statusbar";
  height: 100%;
}
```
E acrescentar ao final:
```css
.scalebar { grid-area: scalebar; background: #1e1e24; border-top: 1px solid #2c2c34; padding: 8px 14px; display: flex; flex-direction: column; gap: 6px; }
.scalebar-linha { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.scalebar .rotulo { font-size: 0.75rem; letter-spacing: 0.06em; color: #9a9aa5; }
.scalebar select, .scalebar input { background: #16161a; color: #e8e8ec; border: 1px solid #2c2c34; border-radius: 6px; padding: 4px 6px; font-size: 0.82rem; }
.campo-inline { display: flex; align-items: center; gap: 5px; font-size: 0.78rem; color: #9a9aa5; }
.campo-inline input { width: 70px; }
.banner-unidade { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 0.82rem; color: #f2b84b; }
.alerta-inline { font-size: 0.75rem; color: #f2b84b; }
.dims-resultado { font-weight: 600; font-size: 0.95rem; }
.dims.suspeito, .dims-resultado.suspeito { color: #e15759; }
.scalebar .msg { font-size: 0.78rem; color: #e15759; }
```

- [ ] **Step 5: Verificar**

Run: `npm --prefix web test && npm --prefix web run build && .venv/Scripts/python -m pytest -q`
Expected: tudo verde

- [ ] **Step 6: Commit**

```bash
git add web/src/components/ScaleBar.jsx web/src/App.jsx web/src/components/StatusBar.jsx web/src/styles.css
git commit -m "feat: barra de escala com banner de unidade ambígua e validador visual"
```

---

### Task 4: Verificação e2e + documentação

> **Nota de execução:** Steps 1-3 são do CONTROLADOR (browser visível); o
> subagente faz só os passos de documentação (Steps 4-5) e o gate final.

- [ ] **Step 1 (controlador): Cena ambígua**

STL sintético com maior dimensão ~30 (faixa ambígua 5–100 do §5.2), ex.: a caixa
10×20×30 dos fixtures. `meshbench serve` → o banner "unidade ambígua" deve
aparecer com as comparações humanas; clicar "é polegadas" → PATCH aplicado,
dims viram 254×508×762 mm, banner some (units_confirmed), semáforo/status
atualizam, componentes não somem da lista.

- [ ] **Step 2 (controlador): Modos e validador**

- "ajustar dimensão" x→450 → dims_mm[0] = 450 ao vivo.
- "fator por eixo" mostra o ⚠ de distorção.
- Forçar dimensão suspeita (fator uniforme 1000) → dims em vermelho na barra
  de escala E na barra de status + warning "confira a unidade" visível.
- Console limpo em todo o fluxo; câmera não reseta nos Aplicar (viewport persistente).

- [ ] **Step 3 (controlador): Encerrar servidor**

- [ ] **Step 4: README.md**

Acrescentar depois da seção "## Viewport 3D (Fases 2–3)" (renomear o título para "## Viewport 3D (Fases 2–4)"):
```markdown
### Escala e unidades (Fase 4)

A barra ESCALA converte unidades (pol/cm/m → mm), aplica fator uniforme ou por
eixo, e ajusta uma dimensão-alvo ("quero largura = 450 mm"). Quando o arquivo
tem unidade ambígua (STL não guarda unidade), um banner compara as
possibilidades em tamanho humano e pede confirmação. Dimensões suspeitas
(< 1 mm ou > 5 m) ficam em vermelho.
```

- [ ] **Step 5: CLAUDE.md**

Trocar "Phases 1 (core+CLI), 2 (viewport) and 3 (selection + interactive ops + preview + save) are implemented. Phases 4+ (interactive scale/orient/origin, export UI, gizmos) are not yet." por:
```markdown
Phases 1 (core+CLI), 2 (viewport), 3 (selection/ops/preview/save) and 4 (interactive scale & units) are implemented. Phases 5+ (interactive orient/origin gizmos, export UI, re-import UI) are not yet.
```

- [ ] **Step 6: Gate final e commit**

Run: `.venv/Scripts/python -m pytest -q && npm --prefix web test && npm --prefix web run build`
Expected: tudo verde

```bash
git add README.md CLAUDE.md
git commit -m "docs: fase 4 — escala e unidades interativas documentadas"
```
