import { useState } from "react";
import { budgetLevel, formatDims, formatFaces } from "../lib/format.js";
import { isSuspiciousDims } from "../lib/scale.js";
import { foraDaSaida } from "../lib/selection.js";

export default function StatusBar({ state, onSelectMany }) {
  const [aberto, setAberto] = useState(true);
  const avisos = state.warnings;
  const semSaida = foraDaSaida(state.components);
  return (
    <footer className="statusbar">
      <div className="statusbar-linha">
        <span className={"dims" + (isSuspiciousDims(state.dims_mm) ? " suspeito" : "")}>
          {formatDims(state.dims_mm)}
        </span>
        {Object.entries(state.group_faces).map(([g, faces]) => (
          <span key={g} className="budget">
            <span className={"luz " + budgetLevel(faces)} />
            {g}: {formatFaces(faces)} f
          </span>
        ))}
        {avisos.length > 0 && (
          <button
            className="btn mini avisos-toggle"
            onClick={() => setAberto((a) => !a)}
            aria-expanded={aberto}
          >
            ⚠ {avisos.length} {avisos.length === 1 ? "aviso" : "avisos"}{" "}
            {aberto ? "▾" : "▸"}
          </button>
        )}
        {semSaida.length > 0 && (
          <button
            className="btn mini"
            onClick={() => onSelectMany(semSaida)}
            title="seleciona as famílias cuja operação não produziu malha, para tratar todas de uma vez"
          >
            selecionar as {semSaida.length} fora da saída
          </button>
        )}
      </div>
      {/* rola dentro de si: sem a altura máxima, muitos avisos empurram o
          viewport (linha 1fr do grid) para fora da tela */}
      {avisos.length > 0 && aberto && (
        <div className="avisos">
          {avisos.map((w, i) => (
            <div key={i}>⚠ {w}</div>
          ))}
        </div>
      )}
    </footer>
  );
}
