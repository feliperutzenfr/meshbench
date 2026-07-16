import { formatFaces } from "../lib/format.js";
import { OP_LABELS } from "../lib/ops.js";
import { groupColor } from "../lib/palette.js";

function Familia({ c, cor, removida, selecionada, onSelect }) {
  const label = c.user_label || c.auto_class;
  return (
    <div
      className={
        "familia" + (removida ? " removida" : "") + (selecionada ? " selecionada" : "")
      }
      onClick={() => onSelect(c.id)}
    >
      <span className="cor" style={{ background: cor }} />
      <span>
        {c.instances}× {label} ({formatFaces(c.face_count)} f cada)
        {c.needs_review ? <span className="alerta"> ⚠ novo — revisar</span> : null}
      </span>
      <span className="op">{OP_LABELS[c.operation.type] || c.operation.type}</span>
    </div>
  );
}

export default function Sidebar({ state, selected, onSelect }) {
  const groupNames = state.groups.map((g) => g.name);
  const porGrupo = new Map(groupNames.map((n) => [n, []]));
  const removidas = [];
  const semGrupo = [];
  for (const c of state.components) {
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
      selecionada={c.id === selected}
      onSelect={onSelect}
    />
  );

  return (
    <aside className="sidebar">
      <h1 style={{ fontSize: "1rem" }}>{state.name}</h1>
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
    </aside>
  );
}
