import { useEffect, useState } from "react";
import { patchComponent, patchComponents, previewComponent } from "../lib/client.js";
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
  entries,
  preview,
  onStateChange,
  onPreviewChange,
  onClearPreview,
}) {
  // uma peça: edita tudo. Várias: op e grupo em lote; rótulo e preview ficam de
  // fora porque não fazem sentido coletivos (um nome só para N famílias, e um
  // preview que só sabe mostrar uma).
  const entry = entries.length === 1 ? entries[0] : null;
  const lote = entries.length > 1;
  const chave = entries.map((e) => e.id).join(",");
  const [opType, setOpType] = useState("keep");
  const [params, setParams] = useState({});
  const [group, setGroup] = useState("");
  const [novoGrupo, setNovoGrupo] = useState("");
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);

  // sincroniza o formulário quando a seleção muda. Em lote, parte da primeira
  // peça só como ponto de partida — nada é aplicado até o usuário mandar.
  useEffect(() => {
    const base = entries[0];
    if (!base) return;
    setOpType(base.operation.type);
    setParams({ ...opDefaults(base.operation.type), ...base.operation.params });
    setGroup(base.group ?? "");
    setNovoGrupo("");
    setLabel(lote ? "" : (base.user_label ?? ""));
    setMsg(null);
  }, [chave]); // eslint-disable-line react-hooks/exhaustive-deps

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
      const mudancas = {
        operation: { type: opType, params: coerceParams(opType, params) },
        group: g,
      };
      // rótulo só no modo de uma peça — em lote seria o mesmo nome para todas
      if (!lote) mudancas.user_label = label.trim() || null;
      const ids = entries.map((e) => e.id);
      // uma chamada só: o backend reprocessa uma vez e empilha um desfazer
      const novo = lote
        ? await patchComponents(ids, mudancas)
        : await patchComponent(ids[0], mudancas);
      onStateChange(novo);
      // resincroniza o formulário com o estado devolvido (ex.: grupo recém-criado)
      const atual = novo.components.find((c) => c.id === ids[0]);
      setGroup(atual?.group ?? "");
      if (!lote) setLabel(atual?.user_label ?? "");
      setNovoGrupo("");
      setMsg(lote ? `aplicado em ${ids.length} famílias ✓` : "aplicado ✓");
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
      {entries.length === 0 && (
        <p className="dica">Clique numa peça (viewport ou lista) para editar.</p>
      )}
      {entries.length > 0 && (
        <>
          {lote ? (
            <p className="resumo">
              {entries.length} famílias selecionadas ·{" "}
              {entries.reduce((n, e) => n + e.instances, 0)} peças
            </p>
          ) : (
            <p className="resumo">
              {entry.instances}× {entry.user_label || entry.auto_class} ·{" "}
              {formatFaces(entry.face_count)} f cada
            </p>
          )}
          {!lote && (
            <label className="campo">
              <span>rótulo</span>
              <input
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder={entry.auto_class}
              />
            </label>
          )}
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
          {lote ? (
            <p className="dica">
              A operação e o grupo vão para as {entries.length} famílias de uma vez
              (um único desfazer). A pré-visualização e o rótulo são por peça.
            </p>
          ) : (
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
          )}
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
            {lote ? `Aplicar em ${entries.length}` : "Aplicar"}
          </button>
        </>
      )}
      {msg && <p className="msg">{msg}</p>}
    </aside>
  );
}
