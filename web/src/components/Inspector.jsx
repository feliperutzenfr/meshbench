import { useEffect, useState } from "react";
import { patchComponent, previewComponent } from "../lib/client.js";
import { formatFaces } from "../lib/format.js";
import { OP_LABELS, OP_TYPES, coerceParams, opDefaults } from "../lib/ops.js";

function CampoNum({ nome, valor, step, onChange }) {
  return (
    <label className="campo">
      <span>{nome}</span>
      <input
        type="number"
        step={step ?? 1}
        value={valor ?? ""}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}

function ParamsForm({ opType, params, setParam }) {
  if (opType === "decimate") {
    return (
      <>
        <CampoNum nome="% do original" valor={params.percent} onChange={(v) => setParam("percent", v)} />
        <CampoNum nome="faces (absoluto, opcional)" valor={params.face_count} onChange={(v) => setParam("face_count", v)} />
      </>
    );
  }
  if (opType === "tube") {
    return (
      <>
        <CampoNum nome="lados do círculo" valor={params.sides} onChange={(v) => setParam("sides", v)} />
        <CampoNum nome="passo da linha (mm)" step={0.5} valor={params.bin_mm} onChange={(v) => setParam("bin_mm", v)} />
        <CampoNum nome="raio (vazio = auto)" step={0.5} valor={params.radius} onChange={(v) => setParam("radius", v)} />
      </>
    );
  }
  if (opType === "reextrude") {
    return (
      <>
        <label className="campo">
          <span>eixo de extrusão</span>
          <select value={params.axis ?? "auto"} onChange={(e) => setParam("axis", e.target.value)}>
            <option value="auto">auto (maior dimensão)</option>
            <option value="x">x</option>
            <option value="y">y</option>
            <option value="z">z</option>
          </select>
        </label>
        <CampoNum nome="fatias de teste" valor={params.n_probe} onChange={(v) => setParam("n_probe", v)} />
        <CampoNum nome="tolerância do perfil" step={0.1} valor={params.tol} onChange={(v) => setParam("tol", v)} />
      </>
    );
  }
  return null;
}

export default function Inspector({
  state,
  entry,
  preview,
  onStateChange,
  onPreviewChange,
  onClearPreview,
}) {
  const [opType, setOpType] = useState("keep");
  const [params, setParams] = useState({});
  const [group, setGroup] = useState("");
  const [novoGrupo, setNovoGrupo] = useState("");
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);

  // sincroniza o formulário quando a seleção muda
  useEffect(() => {
    if (!entry) return;
    setOpType(entry.operation.type);
    setParams({ ...opDefaults(entry.operation.type), ...entry.operation.params });
    setGroup(entry.group ?? "");
    setNovoGrupo("");
    setLabel(entry.user_label ?? "");
    setMsg(null);
  }, [entry?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const setParam = (k, v) => setParams((p) => ({ ...p, [k]: v }));

  const trocarOp = (t) => {
    setOpType(t);
    setParams(opDefaults(t));
  };

  const aplicar = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const g = novoGrupo.trim() || (group === "" ? null : group);
      const novo = await patchComponent(entry.id, {
        operation: { type: opType, params: coerceParams(opType, params) },
        group: g,
        user_label: label.trim() || null,
      });
      onStateChange(novo);
      // resincroniza o formulário com o estado devolvido (ex.: grupo recém-criado)
      const atual = novo.components.find((c) => c.id === entry.id);
      setGroup(atual?.group ?? "");
      setLabel(atual?.user_label ?? "");
      setNovoGrupo("");
      setMsg("aplicado ✓");
    } catch (e) {
      setMsg(`erro: ${e.message}`);
    }
    setBusy(false);
  };

  const preVisualizar = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const p = await previewComponent(entry.id, {
        type: opType,
        params: coerceParams(opType, params),
      });
      onPreviewChange({ componentId: entry.id, ...p, mostrando: "depois" });
    } catch (e) {
      setMsg(`erro: ${e.message}`);
    }
    setBusy(false);
  };

  return (
    <aside className="inspector">
      <h2>Inspetor</h2>
      {!entry && <p className="dica">Clique numa peça (viewport ou lista) para editar.</p>}
      {entry && (
        <>
          <p className="resumo">
            {entry.instances}× {entry.user_label || entry.auto_class} ·{" "}
            {formatFaces(entry.face_count)} f cada
          </p>
          <label className="campo">
            <span>rótulo</span>
            <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder={entry.auto_class} />
          </label>
          <fieldset className="ops">
            <legend>operação</legend>
            {OP_TYPES.map((t) => (
              <label key={t} className="op-radio">
                <input type="radio" name="op" checked={opType === t} onChange={() => trocarOp(t)} />
                {OP_LABELS[t]}
              </label>
            ))}
          </fieldset>
          <ParamsForm opType={opType} params={params} setParam={setParam} />
          <div className="preview-bloco">
            <button className="btn" disabled={busy} onClick={preVisualizar}>
              Pré-visualizar
            </button>
            {preview && preview.componentId === entry.id && (
              <div className="preview">
                <span>
                  {formatFaces(preview.facesBefore)} → {formatFaces(preview.facesAfter)} f
                </span>
                <button
                  className={"btn mini" + (preview.mostrando === "antes" ? " ativo" : "")}
                  disabled={busy}
                  onClick={() => onPreviewChange({ ...preview, mostrando: "antes" })}
                >
                  antes
                </button>
                <button
                  className={"btn mini" + (preview.mostrando === "depois" ? " ativo" : "")}
                  disabled={busy}
                  onClick={() => onPreviewChange({ ...preview, mostrando: "depois" })}
                >
                  depois
                </button>
                <button className="btn mini" disabled={busy} onClick={onClearPreview}>
                  fechar
                </button>
              </div>
            )}
          </div>
          <label className="campo">
            <span>grupo</span>
            <select value={group} onChange={(e) => setGroup(e.target.value)}>
              <option value="">(sem grupo)</option>
              {state.groups.map((g) => (
                <option key={g.name} value={g.name}>
                  {g.name}
                </option>
              ))}
            </select>
          </label>
          <label className="campo">
            <span>novo grupo</span>
            <input
              value={novoGrupo}
              onChange={(e) => setNovoGrupo(e.target.value)}
              placeholder="criar grupo…"
            />
          </label>
          <button className="btn primario" disabled={busy} onClick={aplicar}>
            Aplicar
          </button>
        </>
      )}
      {msg && <p className="msg">{msg}</p>}
    </aside>
  );
}
