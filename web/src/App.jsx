import { useEffect, useState } from "react";
import Sidebar from "./components/Sidebar.jsx";
import StatusBar from "./components/StatusBar.jsx";
import Viewport from "./components/Viewport.jsx";

export default function App() {
  const [state, setState] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch("/api/project")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setState)
      .catch((e) => setError(String(e)));
  }, []);

  if (error) return <div className="tela-aviso">Erro ao carregar o projeto: {error}</div>;
  if (!state) return <div className="tela-aviso">Carregando…</div>;
  return (
    <div className="app">
      <Sidebar state={state} />
      <main className="viewport-wrap">
        <Viewport state={state} />
      </main>
      <StatusBar state={state} />
    </div>
  );
}
