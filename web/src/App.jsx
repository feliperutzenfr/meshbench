import { useCallback, useEffect, useRef, useState } from "react";
import Sidebar from "./components/Sidebar.jsx";
import StatusBar from "./components/StatusBar.jsx";
import Viewport from "./components/Viewport.jsx";
import Inspector from "./components/Inspector.jsx";
import ScaleBar from "./components/ScaleBar.jsx";
import OrientBar from "./components/OrientBar.jsx";
import OriginBar from "./components/OriginBar.jsx";
import ExportBar from "./components/ExportBar.jsx";
import { fetchProject } from "./lib/client.js";
import { ordemExibicao, proximaSelecao } from "./lib/selection.js";

export default function App() {
  const [state, setState] = useState(null);
  const [error, setError] = useState(null);
  const [selectedIds, setSelectedIds] = useState([]); // famílias selecionadas
  const [ancora, setAncora] = useState(null); // último clique sem shift (base do intervalo)
  const [preview, setPreview] = useState(null); // {componentId, url, facesBefore, facesAfter, mostrando}
  const [snapOrigin, setSnapOrigin] = useState(false); // snap de origem armado?
  const [picked, setPicked] = useState(null); // {point: [x,y,z]} clicado no viewport
  const [gizmoOn, setGizmoOn] = useState(false); // gizmo de rotação visível?
  const [gizmoRots, setGizmoRots] = useState(null); // {rots: [{axis, deg}]} do arrasto
  const [orientBusy, setOrientBusy] = useState(false); // PATCH /api/orient em voo?

  useEffect(() => {
    fetchProject().then(setState).catch((e) => setError(String(e)));
  }, []);

  // ordem em que as famílias aparecem na lista — base do shift+clique
  const ordemRef = useRef([]);
  ordemRef.current = state
    ? ordemExibicao(state.components, state.groups).map((c) => c.id)
    : [];

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

  // clique na lista: ctrl alterna, shift pega intervalo, simples substitui
  const handleSelect = useCallback(
    (id, mods = {}) => {
      clearPreview();
      setSelectedIds((ids) => {
        const r = proximaSelecao({
          ids,
          ancora,
          clicado: id,
          ordem: ordemRef.current,
          ctrl: mods.ctrl,
          shift: mods.shift,
        });
        setAncora(r.ancora);
        return r.ids;
      });
    },
    [clearPreview, ancora],
  );

  const handleSelectMany = useCallback(
    (ids) => {
      clearPreview();
      setSelectedIds(ids);
      setAncora(ids.length ? ids[ids.length - 1] : null);
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

  const selecionados = state
    ? state.components.filter((c) => selectedIds.includes(c.id))
    : [];

  const handlePickPoint = useCallback((p) => setPicked({ point: p }), []);
  const handleGizmoRotate = useCallback((rots) => setGizmoRots({ rots }), []);

  if (error) return <div className="tela-aviso">Erro ao carregar o projeto: {error}</div>;
  if (!state) return <div className="tela-aviso">Carregando…</div>;
  return (
    <div className="app">
      <Sidebar
        state={state}
        selectedIds={selectedIds}
        onSelect={handleSelect}
        onStateChange={(novo) => {
          setSelectedIds([]);
          handleStateChange(novo);
        }}
      />
      <main className="viewport-wrap">
        <Viewport
          state={state}
          selectedIds={selectedIds}
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
        entries={selecionados}
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
      <StatusBar state={state} onSelectMany={handleSelectMany} />
    </div>
  );
}
