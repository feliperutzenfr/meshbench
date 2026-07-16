import { useCallback, useEffect, useState } from "react";
import Sidebar from "./components/Sidebar.jsx";
import StatusBar from "./components/StatusBar.jsx";
import Viewport from "./components/Viewport.jsx";
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
      <StatusBar state={state} />
    </div>
  );
}
