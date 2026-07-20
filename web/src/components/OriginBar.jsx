import { useEffect, useState } from "react";
import { patchOrigin } from "../lib/client.js";
import { ANCHOR_OPTIONS, MODE_EXPLAIN, addSnapOffset } from "../lib/origin.js";

const FLOAT_LIMIT_MM = 50; // §8.3 — mesmo limiar do backend

export default function OriginBar({
  state,
  onStateChange,
  snapArmed,
  onToggleSnap,
  picked,
  onPickConsumed,
}) {
  const origin = state.origin;
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const [off, setOff] = useState(["", "", ""]);

  // sincroniza os campos de offset com a receita vigente (PATCH, undo/redo, snap);
  // keyed no conteúdo para não descartar edição em andamento em mutações não relacionadas
  const originJson = JSON.stringify(origin);
  useEffect(() => {
    setOff((origin.offset || [0, 0, 0]).map((v) => String(v)));
  }, [originJson]); // eslint-disable-line react-hooks/exhaustive-deps

  const send = async (changes) => {
    setBusy(true);
    setMsg(null);
    try {
      onStateChange(await patchOrigin(changes));
      setMsg("aplicado ✓");
    } catch (e) {
      setMsg(`erro: ${e.message}`);
    }
    setBusy(false);
  };

  // consumo do snap por clique: o Viewport entregou um ponto do mundo
  useEffect(() => {
    if (!snapArmed || !picked) return;
    onToggleSnap(false);
    onPickConsumed();
    send(addSnapOffset(origin, picked.point));
  }, [picked]); // eslint-disable-line react-hooks/exhaustive-deps

  const aplicarOffset = () => {
    const nums = off.map((v) => Number(v === "" ? 0 : v));
    if (nums.some((n) => Number.isNaN(n))) {
      setMsg("erro: offset deve ser numérico");
      return;
    }
    send({ offset: nums });
  };

  // receita editada à mão pode trazer corner_000 (≡ bbox_min, que o select mostra)
  const anchorValue = origin.anchor === "corner_000" ? "bbox_min" : origin.anchor;
  const dist = state.origin_distance_mm;
  const flutuando = dist != null && dist > FLOAT_LIMIT_MM;
  const temOffset = (origin.offset || []).some((v) => v !== 0);

  return (
    <div className="originbar">
      <span className="rotulo">ORIGEM</span>
      <label className="campo-inline">
        <span>modo</span>
        <select
          value={origin.mode}
          disabled={busy}
          onChange={(e) => send({ mode: e.target.value })}
        >
          <option value="common">comum</option>
          <option value="per_group">por grupo</option>
        </select>
      </label>
      <span className="explica-modo">{MODE_EXPLAIN[origin.mode]}</span>
      <label className="campo-inline">
        <span>âncora</span>
        <select
          value={anchorValue}
          disabled={busy}
          onChange={(e) => send({ anchor: e.target.value })}
        >
          {ANCHOR_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>
      <button
        className={"btn mini" + (snapArmed ? " ativo" : "")}
        disabled={busy}
        onClick={() => onToggleSnap(!snapArmed)}
        title="clique num ponto da peça no viewport para levar a origem até lá"
      >
        ⊕ snap por clique
      </button>
      <span className="grupo-offset">
        offset
        {["x", "y", "z"].map((k, i) => (
          <input
            key={k}
            type="number"
            placeholder={k}
            value={off[i]}
            onChange={(e) =>
              setOff((o) => o.map((v, j) => (j === i ? e.target.value : v)))
            }
          />
        ))}
        <button className="btn mini" disabled={busy} onClick={aplicarOffset}>
          aplicar
        </button>
        {temOffset && (
          <button
            className="btn mini"
            disabled={busy}
            onClick={() => send({ offset: [0, 0, 0] })}
          >
            zerar
          </button>
        )}
      </span>
      {dist != null && (
        <span className={"dist-origem" + (flutuando ? " suspeito" : "")}>
          origem → geometria: {dist.toFixed(1)} mm
          {flutuando ? " ⚠ origem flutuando" : ""}
        </span>
      )}
      {msg && <span className={"msg" + (msg.startsWith("erro") ? " erro" : "")}>{msg}</span>}
    </div>
  );
}
