import { useCallback, useEffect, useState } from "react";
import Sidebar from "./components/Sidebar.jsx";
import StatusBar from "./components/StatusBar.jsx";
import Viewport from "./components/Viewport.jsx";
import Inspector from "./components/Inspector.jsx";
import ScaleBar from "./components/ScaleBar.jsx";
import { fetchProject } from "./lib/client.js";

export default function App() {
  const [state, setState] = useState(null);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null); // id da família selecionada
  const [preview, setPreview] = useState(null); // {componentId, url, facesBefore, facesAfter, mostrando}

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

  if (error) return <div className="tela-aviso">Erro ao carregar o projeto: {error}</div>;
  if (!state) return <div className="tela-aviso">Carregando…</div>;
  return (
    <div className="app">
      <Sidebar state={state} selected={selected} onSelect={handleSelect} />
      <main className="viewport-wrap">
        <Viewport state={state} selected={selected} onSelect={handleSelect} preview={preview} />
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
      <StatusBar state={state} />
    </div>
  );
}
