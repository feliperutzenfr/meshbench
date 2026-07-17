import { useState } from "react";
import { patchOrient, postRedo, postUndo } from "../lib/client.js";
import {
  REMAP_LABELS,
  addRotation,
  buildFreeRotation,
  toggleMirror,
} from "../lib/orient.js";

const AXES = ["x", "y", "z"];
const CUSTOM_OPTIONS = ["x", "-x", "y", "-y", "z", "-z"];

export default function OrientBar({ state, onStateChange }) {
  const orient = state.orient;
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const [free, setFree] = useState({ rx: "", ry: "", rz: "" });
  const [custom, setCustom] = useState(orient.custom_remap || ["x", "y", "z"]);

  const send = async (changes) => {
    setBusy(true);
    setMsg(null);
    try {
      onStateChange(await patchOrient(changes));
    } catch (e) {
      setMsg(`erro: ${e.message}`);
    }
    setBusy(false);
  };

  const desfazer = async () => {
    setBusy(true);
    setMsg(null);
    try {
      onStateChange(await postUndo());
    } catch (e) {
      setMsg(`erro: ${e.message}`);
    }
    setBusy(false);
  };

  const refazer = async () => {
    setBusy(true);
    setMsg(null);
    try {
      onStateChange(await postRedo());
    } catch (e) {
      setMsg(`erro: ${e.message}`);
    }
    setBusy(false);
  };

  const trocarPreset = (value) => {
    if (value === "custom") send({ axis_remap: "custom", custom_remap: custom });
    else send({ axis_remap: value });
  };

  const trocarCustomEixo = (i, v) => {
    const novo = [...custom];
    novo[i] = v;
    setCustom(novo);
    send({ axis_remap: "custom", custom_remap: novo });
  };

  const girarLivre = () => {
    const novo = buildFreeRotation(orient, free.rx, free.ry, free.rz);
    if (novo !== orient) {
      send({ rotations: novo.rotations });
      setFree({ rx: "", ry: "", rz: "" });
    }
  };

  const remapAtual = orient.custom_remap ? "custom" : orient.axis_remap;

  return (
    <div className="orientbar">
      <span className="rotulo">ORIENTA</span>
      <select value={remapAtual} onChange={(e) => trocarPreset(e.target.value)} disabled={busy}>
        {Object.keys(REMAP_LABELS).map((k) => (
          <option key={k} value={k}>
            {REMAP_LABELS[k]}
          </option>
        ))}
      </select>
      {remapAtual === "custom" &&
        [0, 1, 2].map((i) => (
          <select
            key={i}
            value={custom[i]}
            onChange={(e) => trocarCustomEixo(i, e.target.value)}
            disabled={busy}
          >
            {CUSTOM_OPTIONS.map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </select>
        ))}

      {AXES.map((a) => (
        <span key={a} className="par-90">
          <button
            className="btn mini"
            disabled={busy}
            onClick={() => send({ rotations: addRotation(orient, a, 90).rotations })}
          >
            {a.toUpperCase()}+90
          </button>
          <button
            className="btn mini"
            disabled={busy}
            onClick={() => send({ rotations: addRotation(orient, a, -90).rotations })}
          >
            {a.toUpperCase()}−90
          </button>
        </span>
      ))}

      <span className="grupo-espelho">
        espelhar
        {AXES.map((a) => (
          <button
            key={a}
            className={"btn mini" + (orient.mirror.includes(a) ? " ativo" : "")}
            disabled={busy}
            onClick={() => send({ mirror: toggleMirror(orient, a).mirror })}
          >
            {a.toUpperCase()}
          </button>
        ))}
      </span>

      <span className="grupo-livre">
        {["rx", "ry", "rz"].map((k) => (
          <input
            key={k}
            type="number"
            placeholder={k}
            value={free[k]}
            onChange={(e) => setFree((f) => ({ ...f, [k]: e.target.value }))}
          />
        ))}
        <button className="btn mini" disabled={busy} onClick={girarLivre}>
          girar
        </button>
      </span>

      {orient.rotations.length > 0 && (
        <button className="btn mini" disabled={busy} onClick={() => send({ rotations: [] })}>
          limpar rotações
        </button>
      )}

      <span className="grupo-undo">
        <button className="btn mini" disabled={busy || !state.can_undo} onClick={desfazer} title="desfazer">
          ↶
        </button>
        <button className="btn mini" disabled={busy || !state.can_redo} onClick={refazer} title="refazer">
          ↷
        </button>
      </span>
      {msg && <span className="msg erro">{msg}</span>}
    </div>
  );
}
