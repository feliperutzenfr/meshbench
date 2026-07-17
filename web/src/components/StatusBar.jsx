import { budgetLevel, formatDims, formatFaces } from "../lib/format.js";
import { isSuspiciousDims } from "../lib/scale.js";

export default function StatusBar({ state }) {
  return (
    <footer className="statusbar">
      <span className={"dims" + (isSuspiciousDims(state.dims_mm) ? " suspeito" : "")}>
        {formatDims(state.dims_mm)}
      </span>
      {Object.entries(state.group_faces).map(([g, faces]) => (
        <span key={g} className="budget">
          <span className={"luz " + budgetLevel(faces)} />
          {g}: {formatFaces(faces)} f
        </span>
      ))}
      {state.warnings.length > 0 && (
        <span className="avisos">
          {state.warnings.map((w, i) => (
            <div key={i}>⚠ {w}</div>
          ))}
        </span>
      )}
    </footer>
  );
}
