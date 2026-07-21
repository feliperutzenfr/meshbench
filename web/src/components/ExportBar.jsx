import { useEffect, useState } from "react";
import { patchExport, postExport } from "../lib/client.js";
import { formatFaces } from "../lib/format.js";
import { FORMAT_LABELS, budgetClass, namingForFormat, validNaming } from "../lib/export.js";

function dirDe(caminho) {
  // pasta do primeiro arquivo (separador \ ou /), para dizer onde caíram
  const i = Math.max(caminho.lastIndexOf("/"), caminho.lastIndexOf("\\"));
  return i >= 0 ? caminho.slice(0, i) : caminho;
}

export default function ExportBar({ state, onStateChange }) {
  const exp = state.export || {};
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const [result, setResult] = useState(null); // {files, warnings}
  const [outDir, setOutDir] = useState(exp.out_dir || "out/");
  const [naming, setNaming] = useState(exp.naming || "{project}_{group}.dxf");

  // sincroniza os campos com a config vigente; keyed no conteúdo para não
  // descartar edição em andamento em mutações não relacionadas
  const expJson = JSON.stringify(exp);
  useEffect(() => {
    setOutDir(exp.out_dir || "out/");
    setNaming(exp.naming || "{project}_{group}.dxf");
  }, [expJson]); // eslint-disable-line react-hooks/exhaustive-deps

  const salvarConfig = async (changes) => {
    setBusy(true);
    setMsg(null);
    try {
      onStateChange(await patchExport(changes));
    } catch (e) {
      setMsg(`erro: ${e.message}`);
    }
    setBusy(false);
  };

  const trocarFormato = (fmt) => {
    const novoNaming = namingForFormat(naming, fmt);
    setNaming(novoNaming);
    salvarConfig({ format: fmt, out_dir: outDir, naming: novoNaming });
  };

  const aplicarConfig = () => {
    if (!validNaming(naming)) {
      setMsg("erro: nome deve conter {group}");
      return;
    }
    salvarConfig({ out_dir: outDir, naming });
  };

  const gerar = async () => {
    if (!validNaming(naming)) {
      setMsg("erro: nome deve conter {group}");
      return;
    }
    setBusy(true);
    setMsg(null);
    setResult(null);
    try {
      // grava a config vigente (pasta/nome digitados) antes de gerar
      await patchExport({ format: exp.format, out_dir: outDir, naming });
      const r = await postExport();
      setResult(r);
      setMsg(r.files.length ? "exportado ✓" : "nenhum arquivo — confira grupos e operações");
    } catch (e) {
      setMsg(`erro: ${e.message}`);
    }
    setBusy(false);
  };

  return (
    <div className="exportbar">
      <span className="rotulo">EXPORTA</span>
      <select value={exp.format} disabled={busy} onChange={(e) => trocarFormato(e.target.value)}>
        {Object.keys(FORMAT_LABELS).map((f) => (
          <option key={f} value={f}>
            {FORMAT_LABELS[f]}
          </option>
        ))}
      </select>
      <label className="campo-inline">
        <span>pasta</span>
        <input value={outDir} disabled={busy} onChange={(e) => setOutDir(e.target.value)} onBlur={aplicarConfig} />
      </label>
      <label className="campo-inline">
        <span>nome</span>
        <input value={naming} disabled={busy} onChange={(e) => setNaming(e.target.value)} onBlur={aplicarConfig} />
      </label>
      <button className="btn primario" disabled={busy} onClick={gerar}>
        Exportar
      </button>
      {result && result.files.length > 0 && (
        <span className="export-result">
          {result.files.map((f) => (
            <span key={f.group} className={"export-file " + budgetClass(f.faces, state.face_budget)} title={f.path}>
              {f.group}: {formatFaces(f.faces)} f
            </span>
          ))}
          <span className="export-dir">→ {dirDe(result.files[0].path)}</span>
        </span>
      )}
      {msg && <span className={"msg" + (msg.startsWith("erro") ? " erro" : "")}>{msg}</span>}
    </div>
  );
}
