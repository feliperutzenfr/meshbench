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
