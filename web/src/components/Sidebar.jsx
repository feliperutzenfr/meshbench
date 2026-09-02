import { formatFaces } from "../lib/format.js";
import { OP_LABELS } from "../lib/ops.js";
import { groupColor } from "../lib/palette.js";
import { ordemExibicao } from "../lib/selection.js";
import ProjectActions from "./ProjectActions.jsx";

function Familia({ c, cor, removida, selecionada, onSelect }) {
  const label = c.user_label || c.auto_class;
  // ctrl/cmd alterna, shift pega o intervalo — quem decide é a lib de seleção
  const mods = (e) => ({ ctrl: e.ctrlKey || e.metaKey, shift: e.shiftKey });
  const foraDaSaida = !c.in_output && c.operation.type !== "remove";
  return (
    <div
      className={
        "familia" +
        (removida ? " removida" : "") +
        (selecionada ? " selecionada" : "") +
        (foraDaSaida ? " sem-saida" : "")
      }
      onClick={(e) => onSelect(c.id, mods(e))}
      role="button"
      aria-pressed={selecionada}
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect(c.id, mods(e));
        }
      }}
    >
      <span className="cor" style={{ background: cor }} />
      <span>
        {c.instances}× {label} ({formatFaces(c.face_count)} f cada)
        {c.needs_review ? <span className="alerta"> ⚠ novo — revisar</span> : null}
        {foraDaSaida ? (
          <span className="alerta" title="a operação não produziu malha para esta peça">
            {" "}
            ⚠ fora da saída
          </span>
        ) : null}
      </span>
      <span className="op">{OP_LABELS[c.operation.type] || c.operation.type}</span>
    </div>
  );
}

export default function Sidebar({ state, selectedIds, onSelect, onStateChange }) {
  const groupNames = state.groups.map((g) => g.name);
  // mesma repartição que ordemExibicao() usa para o shift+clique — uma função
  // só, para a ordem da tela e a do intervalo nunca divergirem
  const porGrupo = new Map(groupNames.map((n) => [n, []]));
  const removidas = [];
  const semGrupo = [];
  for (const c of ordemExibicao(state.components, state.groups)) {
    if (c.operation.type === "remove") removidas.push(c);
    else if (c.group && porGrupo.has(c.group)) porGrupo.get(c.group).push(c);
    else semGrupo.push(c);
  }

  const familia = (c, cor, removida) => (
    <Familia
      key={c.id}
      c={c}
      cor={cor}
      removida={removida}
      selecionada={selectedIds.includes(c.id)}
      onSelect={onSelect}
    />
  );

  return (
    <aside className="sidebar">
      <h1 style={{ fontSize: "1rem" }}>{state.name}</h1>
      <p className="dica-selecao">
        ctrl+clique soma · shift+clique pega o intervalo
        {selectedIds.length > 1 ? ` · ${selectedIds.length} selecionadas` : ""}
      </p>
      {groupNames.map((g) => (
        <section key={g}>
          <h2>▸ {g}</h2>
          {porGrupo.get(g).map((c) => familia(c, groupColor(g, groupNames), false))}
        </section>
      ))}
      {semGrupo.length > 0 && (
        <section>
          <h2>▸ sem grupo ⚠</h2>
          {semGrupo.map((c) => familia(c, "#666", false))}
        </section>
      )}
      {removidas.length > 0 && (
        <section>
          <h2>▸ removidas</h2>
          {removidas.map((c) => familia(c, "#666", true))}
        </section>
      )}
      <ProjectActions onStateChange={onStateChange} />
    </aside>
  );
}
