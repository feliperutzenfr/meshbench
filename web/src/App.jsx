import { useCallback, useEffect, useState } from "react";
import Sidebar from "./components/Sidebar.jsx";
import StatusBar from "./components/StatusBar.jsx";
import Viewport from "./components/Viewport.jsx";
import Inspector from "./components/Inspector.jsx";
import ScaleBar from "./components/ScaleBar.jsx";
import OrientBar from "./components/OrientBar.jsx";
import OriginBar from "./components/OriginBar.jsx";
import ExportBar from "./components/ExportBar.jsx";
import { fetchProject } from "./lib/client.js";

export default function App() {
  const [state, setState] = useState(null);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null); // id da família selecionada
  const [preview, setPreview] = useState(null); // {componentId, url, facesBefore, facesAfter, mostrando}
  const [snapOrigin, setSnapOrigin] = useState(false); // snap de origem armado?
  const [picked, setPicked] = useState(null); // {point: [x,y,z]} clicado no viewport
  const [gizmoOn, setGizmoOn] = useState(false); // gizmo de rotação visível?
  const [gizmoRots, setGizmoRots] = useState(null); // {rots: [{axis, deg}]} do arrasto
  const [orientBusy, setOrientBusy] = useState(false); // PATCH /api/orient em voo?

  useEffect(() => {
    fetchProject().then(setState).catch((e) => setError(String(e)));
  }, []);

  const clearPreview = useCallback(() => {
    setPreview((p) => {
      if (p) URL.revokeObjectURL(p.url);
      return null;
    });
  }, []);

  // troca de preview revoga o objectURL anterior; o toggle antes/depois reusa
  // a mesma url (via {...preview, mostrando}) e não revoga nada
  const handlePreviewChange = useCallback((novo) => {
    setPreview((atual) => {
      if (atual && novo && atual.url !== novo.url) URL.revokeObjectURL(atual.url);
      return novo;
    });
  }, []);

  const handleSelect = useCallback(
    (id) => {
      clearPreview();
      setSelected(id);
    },
    [clearPreview],
  );

  // resposta de um PATCH substitui o estado inteiro (o servidor reprocessou)
  const handleStateChange = useCallback(
    (novo) => {
      clearPreview();
      setState(novo);
    },
    [clearPreview],
  );

  const handlePickPoint = useCallback((p) => setPicked({ point: p }), []);
  const handleGizmoRotate = useCallback((rots) => setGizmoRots({ rots }), []);

  if (error) return <div className="tela-aviso">Erro ao carregar o projeto: {error}</div>;
  if (!state) return <div className="tela-aviso">Carregando…</div>;
  return (
    <div className="app">
      <Sidebar
        state={state}
        selected={selected}
        onSelect={handleSelect}
        onStateChange={(novo) => {
          setSelected(null);
          handleStateChange(novo);
        }}
      />
      <main className="viewport-wrap">
        <Viewport
          state={state}
          selected={selected}
          onSelect={handleSelect}
          preview={preview}
          pickMode={snapOrigin}
          onPickPoint={handlePickPoint}
          gizmoOn={gizmoOn}
          onGizmoRotate={handleGizmoRotate}
          busy={orientBusy}
        />
      </main>
      <Inspector
        state={state}
        entry={state.components.find((c) => c.id === selected) || null}
        preview={preview}
        onStateChange={handleStateChange}
        onPreviewChange={handlePreviewChange}
        onClearPreview={clearPreview}
      />
      <ScaleBar state={state} onStateChange={handleStateChange} />
      <OrientBar
        state={state}
        onStateChange={handleStateChange}
        gizmoOn={gizmoOn}
        onToggleGizmo={setGizmoOn}
        gizmoRots={gizmoRots}
        onGizmoConsumed={() => setGizmoRots(null)}
        onBusyChange={setOrientBusy}
      />
      <OriginBar
        state={state}
        onStateChange={handleStateChange}
        snapArmed={snapOrigin}
        onToggleSnap={setSnapOrigin}
        picked={picked}
        onPickConsumed={() => setPicked(null)}
      />
      <ExportBar state={state} onStateChange={handleStateChange} />
      <StatusBar state={state} />
    </div>
  );
}
