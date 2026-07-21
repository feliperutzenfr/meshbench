import { useState } from "react";
import { openRecipe, pickFile, postReimport, saveRecipe } from "../lib/client.js";

export default function ProjectActions({ onStateChange }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const [abrindo, setAbrindo] = useState(false);
  const [caminho, setCaminho] = useState("");

  const salvar = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const r = await saveRecipe();
      setMsg(`salva: ${r.path}`);
    } catch (e) {
      setMsg(`erro: ${e.message}`);
    }
    setBusy(false);
  };

  const reimportar = async () => {
    setBusy(true);
    setMsg(null);
    try {
      onStateChange(await postReimport());
      setMsg("re-importado ✓ — confira as peças marcadas 'novo — revisar'");
    } catch (e) {
      setMsg(`erro: ${e.message}`);
    }
    setBusy(false);
  };

  const abrir = async () => {
    if (!caminho.trim()) return;
    setBusy(true);
    setMsg(null);
    try {
      onStateChange(await openRecipe(caminho.trim()));
      setAbrindo(false);
      setCaminho("");
      setMsg("receita aberta ✓");
    } catch (e) {
      setMsg(`erro: ${e.message}`);
    }
    setBusy(false);
  };

  const procurar = async () => {
    const r = await pickFile();
    if (r.unavailable || !r.path) return; // sem broker (dev) ou cancelou → mantém o campo digitável
    setCaminho(r.path);
  };

  return (
    <section className="projeto-acoes">
      <h2>Projeto</h2>
      <button className="btn" disabled={busy} onClick={salvar}>
        Salvar receita
      </button>
      <button
        className="btn"
        disabled={busy}
        onClick={reimportar}
        title="re-lê o source do CAD e re-casa componentes por assinatura"
      >
        Re-importar source
      </button>
      {!abrindo ? (
        <button className="btn" disabled={busy} onClick={() => setAbrindo(true)}>
          Abrir receita…
        </button>
      ) : (
        <div className="abrir-receita">
          <input
            value={caminho}
            onChange={(e) => setCaminho(e.target.value)}
            placeholder="caminho da .meshbench.json"
            autoFocus
          />
          <span className="abrir-botoes">
            <button className="btn mini" disabled={busy} onClick={procurar}>
              Procurar…
            </button>
            <button className="btn mini" disabled={busy} onClick={abrir}>
              abrir
            </button>
            <button className="btn mini" disabled={busy} onClick={() => setAbrindo(false)}>
              cancelar
            </button>
          </span>
        </div>
      )}
      {msg && <p className={"msg" + (msg.startsWith("erro") ? " erro" : "")}>{msg}</p>}
    </section>
  );
}
