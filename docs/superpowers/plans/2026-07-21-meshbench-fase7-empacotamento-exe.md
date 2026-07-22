# Fase 7 — Empacotamento desktop (.exe) — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Empacotar a MeshBench num executável Windows one-dir (`.zip`) que roda sem Python/npm: duplo-clique → diálogo nativo escolhe o arquivo → app abre no navegador; com pickers nativos "Procurar…" in-app.

**Architecture:** Um launcher novo (`src/meshbench/desktop.py`) é o entry point do PyInstaller, dono da main thread (loop tkinter: diálogos + janela de status); o uvicorn roda numa thread daemon em porta livre dinâmica. Um `DialogBroker` na main thread deixa as rotas HTTP (thread do uvicorn) abrirem diálogos nativos sem tocar tkinter fora da main thread. Fora do modo desktop as rotas de pick respondem 409 e a UI cai no campo digitável.

**Tech Stack:** Python 3.11+, tkinter (stdlib), uvicorn.Server (thread), PyInstaller (one-dir, `--windowed`), React/Vite (frontend), FastAPI TestClient + vitest (testes).

## Global Constraints

- Python `>=3.11`; alvo **Windows** (Promob). macOS/Linux fora de escopo.
- Strings de UI / mensagens de erro / docstrings em **pt-BR**; identificadores de código em **inglês**.
- Conventional Commits; trailer `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` em todo commit.
- Distribuição **one-dir → `.zip`** nesta fase; **sem Inno Setup** (adiado).
- Servidor **local-only** `127.0.0.1`, **porta livre dinâmica** (bind `:0`) — nunca 8765 fixo no launcher.
- Diálogos nativos via **tkinter** (stdlib, sem dep de runtime nova).
- O campo de caminho digitável permanece na UI como fallback quando o broker não existe (`meshbench serve` no dev).
- Setup/testes: `.venv/Scripts/python -m pytest`, `npm --prefix web test`.

---

### Task 1: `desktop.py` — porta livre + DialogBroker

**Files:**
- Create: `src/meshbench/desktop.py`
- Test: `tests/test_desktop.py`

**Interfaces:**
- Produces:
  - `pick_free_port() -> int` — porta TCP livre em 127.0.0.1.
  - `class DialogBroker(timeout: float = 300.0)` com:
    - `submit(kind: str) -> str | None` — lado da rota; enfileira e bloqueia até o loop tk resolver; devolve caminho ou `None` (cancelou/timeout).
    - `drain(open_dialog: Callable[[str], str | None]) -> None` — lado do loop tk; processa pedidos pendentes chamando `open_dialog(kind)`.

- [ ] **Step 1: Escrever os testes que falham**

Create `tests/test_desktop.py`:

```python
import socket
import threading
import time

from meshbench.desktop import DialogBroker, pick_free_port


def test_pick_free_port_is_bindable():
    port = pick_free_port()
    assert isinstance(port, int) and port > 0
    # a porta devolvida está livre — dá para fazer bind nela
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", port))


def _run_submit(broker, kind, out):
    out["path"] = broker.submit(kind)
    out["done"] = True


def test_broker_submit_resolves_with_dialog():
    broker = DialogBroker(timeout=5.0)
    out = {}
    t = threading.Thread(target=_run_submit, args=(broker, "file", out))
    t.start()
    # o loop tk daria drain periodicamente; simulamos até resolver
    for _ in range(200):
        broker.drain(lambda kind: "C:/x.stl" if kind == "file" else None)
        if out.get("done"):
            break
        time.sleep(0.01)
    t.join(2.0)
    assert out["path"] == "C:/x.stl"


def test_broker_submit_cancel_returns_none():
    broker = DialogBroker(timeout=5.0)
    out = {}
    t = threading.Thread(target=_run_submit, args=(broker, "folder", out))
    t.start()
    for _ in range(200):
        broker.drain(lambda kind: None)  # usuário cancelou
        if out.get("done"):
            break
        time.sleep(0.01)
    t.join(2.0)
    assert out["path"] is None


def test_broker_timeout_returns_none():
    broker = DialogBroker(timeout=0.1)
    # ninguém dá drain → submit devolve None depois do timeout de guarda
    assert broker.submit("file") is None
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_desktop.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'meshbench.desktop'`

- [ ] **Step 3: Implementar `desktop.py` (só porta + broker por enquanto)**

Create `src/meshbench/desktop.py`:

```python
"""Launcher desktop do MeshBench: entry point do executável empacotado (PyInstaller).

Roda o loop do tkinter na main thread (diálogos nativos + janela de status) e o
uvicorn numa thread de fundo. Sem argumento, abre um diálogo nativo para escolher
o arquivo; também aceita um arquivo passado em argv (arrastado no ícone).
"""

import queue
import socket
import threading


def pick_free_port() -> int:
    """Devolve uma porta TCP livre em 127.0.0.1 (bind em :0, lê a porta, fecha)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class DialogBroker:
    """Ponte thread-safe entre as rotas HTTP e os diálogos nativos.

    As rotas rodam na thread do uvicorn; o tkinter exige a main thread. `submit`
    (lado da rota) enfileira um pedido e bloqueia; `drain` (lado do loop tk) abre
    o diálogo na main thread e libera o pedido.
    """

    def __init__(self, timeout: float = 300.0):
        self._q: queue.Queue = queue.Queue()
        self._timeout = timeout

    def submit(self, kind: str) -> str | None:
        """Enfileira um pedido de diálogo e bloqueia até o loop tk resolver.

        Devolve o caminho escolhido ou None (cancelou / timeout de guarda).
        """
        done = threading.Event()
        holder: list = [None]
        self._q.put((kind, holder, done))
        if not done.wait(self._timeout):
            return None
        return holder[0]

    def drain(self, open_dialog) -> None:
        """Processa os pedidos pendentes chamando open_dialog(kind) -> str|None.

        Chamado periodicamente pelo loop tk (main thread). open_dialog roda na
        main thread e é quem de fato abre o diálogo nativo.
        """
        while True:
            try:
                kind, holder, done = self._q.get_nowait()
            except queue.Empty:
                return
            try:
                holder[0] = open_dialog(kind)
            finally:
                done.set()
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/Scripts/python -m pytest tests/test_desktop.py -v`
Expected: PASS (4 testes)

- [ ] **Step 5: Commit**

```bash
git add src/meshbench/desktop.py tests/test_desktop.py
git commit -m "feat: porta livre e DialogBroker para o launcher desktop

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Rotas `/api/pick/file` e `/api/pick/folder` + registro do broker

**Files:**
- Modify: `src/meshbench/api/server.py`
- Test: `tests/test_api_pick.py`

**Interfaces:**
- Consumes: `DialogBroker.submit` (Task 1) como o callable registrado.
- Produces:
  - `set_dialog_broker(fn: Callable[[str], str | None] | None) -> None` em `server.py` — registra/limpa o broker (módulo-global `_dialog_broker`).
  - `POST /api/pick/file` e `POST /api/pick/folder` → `{"path": str | null}`; sem broker → 409 `{"detail": "diálogo nativo indisponível (rode pelo app desktop)"}`.

- [ ] **Step 1: Escrever os testes que falham**

Create `tests/test_api_pick.py`:

```python
from fastapi.testclient import TestClient

from meshbench.api.server import create_app, load_session, set_dialog_broker


def _app(tmp_path, box):
    p = tmp_path / "box.stl"
    box.export(p)
    return create_app(load_session(p))


def test_pick_sem_broker_retorna_409(tmp_path, box):
    set_dialog_broker(None)
    client = TestClient(_app(tmp_path, box))
    r = client.post("/api/pick/file")
    assert r.status_code == 409
    assert "desktop" in r.json()["detail"]


def test_pick_file_com_broker_retorna_path(tmp_path, box):
    set_dialog_broker(lambda kind: "C:/escolhido.stl" if kind == "file" else None)
    try:
        client = TestClient(_app(tmp_path, box))
        r = client.post("/api/pick/file")
        assert r.status_code == 200
        assert r.json() == {"path": "C:/escolhido.stl"}
    finally:
        set_dialog_broker(None)


def test_pick_folder_cancelado_retorna_null(tmp_path, box):
    set_dialog_broker(lambda kind: None)  # cancelou
    try:
        client = TestClient(_app(tmp_path, box))
        r = client.post("/api/pick/folder")
        assert r.status_code == 200
        assert r.json() == {"path": None}
    finally:
        set_dialog_broker(None)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_api_pick.py -v`
Expected: FAIL com `ImportError: cannot import name 'set_dialog_broker'`

- [ ] **Step 3: Implementar em `server.py`**

Add near the top of `src/meshbench/api/server.py`, right after `STATIC_DIR = Path(__file__).parent / "static"` (server.py:32):

```python
# broker de diálogos nativos — só o launcher desktop registra; no dev
# (meshbench serve) fica None e as rotas de pick respondem 409.
_dialog_broker = None  # Callable[[str], str | None] | None


def set_dialog_broker(fn):
    """Registra (ou limpa, com None) o broker de diálogos nativos do desktop."""
    global _dialog_broker
    _dialog_broker = fn


def _pick(kind):
    if _dialog_broker is None:
        return JSONResponse(
            status_code=409,
            content={"detail": "diálogo nativo indisponível (rode pelo app desktop)"},
        )
    return JSONResponse({"path": _dialog_broker(kind)})
```

Then register the routes inside `create_app`, right after the `post_save` route (server.py:292, before the `if STATIC_DIR.exists():` block):

```python
    @app.post("/api/pick/file")
    def post_pick_file():
        return _pick("file")

    @app.post("/api/pick/folder")
    def post_pick_folder():
        return _pick("folder")
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/Scripts/python -m pytest tests/test_api_pick.py -v`
Expected: PASS (3 testes)

- [ ] **Step 5: Rodar a suíte toda (nada quebrou)**

Run: `.venv/Scripts/python -m pytest`
Expected: PASS (toda a suíte + os 3 novos)

- [ ] **Step 6: Commit**

```bash
git add src/meshbench/api/server.py tests/test_api_pick.py
git commit -m "feat: rotas de diálogo nativo (/api/pick/file|folder) com 409 fora do desktop

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Frontend — `pickFile`/`pickFolder` + botões "Procurar…"

**Files:**
- Modify: `web/src/lib/client.js`
- Modify: `web/src/components/ProjectActions.jsx`
- Modify: `web/src/components/ExportBar.jsx`
- Test: `web/src/lib/client.test.js` (create)

**Interfaces:**
- Consumes: `POST /api/pick/file|folder` (Task 2).
- Produces em `client.js`:
  - `pickFile() -> Promise<{path: string|null} | {unavailable: true}>`
  - `pickFolder() -> Promise<{path: string|null} | {unavailable: true}>`

- [ ] **Step 1: Escrever o teste que falha**

Create `web/src/lib/client.test.js`:

```javascript
import { afterEach, expect, test, vi } from "vitest";
import { pickFile, pickFolder } from "./client.js";

afterEach(() => {
  vi.restoreAllMocks();
});

test("pickFile devolve {unavailable} em 409", async () => {
  global.fetch = vi.fn(async () => new Response(null, { status: 409 }));
  expect(await pickFile()).toEqual({ unavailable: true });
});

test("pickFile devolve {path} em 200", async () => {
  global.fetch = vi.fn(
    async () =>
      new Response(JSON.stringify({ path: "C:/a.stl" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
  );
  expect(await pickFile()).toEqual({ path: "C:/a.stl" });
});

test("pickFolder devolve {path:null} quando cancelado", async () => {
  global.fetch = vi.fn(
    async () =>
      new Response(JSON.stringify({ path: null }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
  );
  expect(await pickFolder()).toEqual({ path: null });
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm --prefix web test -- --run client.test.js`
Expected: FAIL — `pickFile` não é exportado.

- [ ] **Step 3: Implementar em `client.js`**

Add to `web/src/lib/client.js`, right before the `geometryUrl` export (client.js:127):

```javascript
async function pickPath(url) {
  const r = await fetch(url, { method: "POST" });
  if (r.status === 409) return { unavailable: true };
  await checkOk(r);
  const data = await r.json();
  return { path: data.path };
}

export async function pickFile() {
  return pickPath("/api/pick/file");
}

export async function pickFolder() {
  return pickPath("/api/pick/folder");
}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `npm --prefix web test -- --run client.test.js`
Expected: PASS (3 testes)

- [ ] **Step 5: Ligar o botão em `ProjectActions.jsx`**

In `web/src/components/ProjectActions.jsx`, change the import line (line 2):

```javascript
import { openRecipe, pickFile, postReimport, saveRecipe } from "../lib/client.js";
```

Add a `procurar` handler right after the `abrir` function (after line 47):

```javascript
  const procurar = async () => {
    const r = await pickFile();
    if (r.unavailable || !r.path) return; // sem broker (dev) ou cancelou → mantém o campo digitável
    setCaminho(r.path);
  };
```

Replace the `abrir-receita` block (lines 68-83) with a version that adds the button:

```javascript
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
```

- [ ] **Step 6: Ligar o botão em `ExportBar.jsx`**

In `web/src/components/ExportBar.jsx`, change the import (line 2):

```javascript
import { patchExport, pickFolder, postExport } from "../lib/client.js";
```

Add a `procurarPasta` handler right after `salvarConfig` (after line 37):

```javascript
  const procurarPasta = async () => {
    const r = await pickFolder();
    if (r.unavailable || !r.path) return; // sem broker (dev) ou cancelou
    setOutDir(r.path);
    salvarConfig({ out_dir: r.path, naming });
  };
```

Add the button right after the `pasta` label (after line 86, the closing `</label>` of the pasta field):

```javascript
      <button className="btn mini" type="button" disabled={busy} onClick={procurarPasta}>
        Procurar…
      </button>
```

- [ ] **Step 7: Rodar a suíte de frontend inteira**

Run: `npm --prefix web test -- --run`
Expected: PASS (suíte existente + client.test.js)

- [ ] **Step 8: Build do frontend (sanidade)**

Run: `npm --prefix web run build`
Expected: build sem erro; `src/meshbench/api/static/` populado.

- [ ] **Step 9: Commit**

```bash
git add web/src/lib/client.js web/src/lib/client.test.js web/src/components/ProjectActions.jsx web/src/components/ExportBar.jsx
git commit -m "feat: botoes Procurar... (abrir arquivo e pasta de export) via diálogo nativo

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Launcher `main()` — argv/diálogo, uvicorn em thread, janela de status

**Files:**
- Modify: `src/meshbench/desktop.py`
- Test: `tests/test_desktop.py` (append)

**Interfaces:**
- Consumes: `pick_free_port`, `DialogBroker` (Task 1); `create_app`, `load_session`, `set_dialog_broker` (Task 2); `uvicorn.Server`.
- Produces:
  - `_resolve_target(argv: list[str]) -> Path | None` — primeiro arquivo existente em `argv[1:]` (arrastado no ícone) ou None.
  - `main(argv: list[str] | None = None) -> int` — entry point do executável.

- [ ] **Step 1: Escrever os testes que falham (só `_resolve_target`, que é puro)**

Append to `tests/test_desktop.py`:

```python
from pathlib import Path

from meshbench.desktop import _resolve_target


def test_resolve_target_pega_arquivo_existente(tmp_path):
    f = tmp_path / "a.stl"
    f.write_text("x")
    assert _resolve_target(["prog", str(f)]) == f


def test_resolve_target_none_sem_arquivo():
    assert _resolve_target(["prog"]) is None


def test_resolve_target_none_para_inexistente():
    assert _resolve_target(["prog", "nao-existe-xyz.stl"]) is None
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_desktop.py -k resolve_target -v`
Expected: FAIL — `_resolve_target` não existe.

- [ ] **Step 3: Implementar o resto de `desktop.py`**

Add `from pathlib import Path` to the imports of `src/meshbench/desktop.py` (top of file), then append these functions at the end:

```python
def _resolve_target(argv):
    """Primeiro arquivo existente em argv[1:] (arrastado no ícone) ou None."""
    for a in argv[1:]:
        p = Path(a)
        if p.exists() and p.is_file():
            return p
    return None


def _ask_open_file():
    """Diálogo nativo de abertura no arranque; devolve o caminho ou None."""
    from tkinter import filedialog

    chosen = filedialog.askopenfilename(
        title="MeshBench — escolha o arquivo CAD ou a receita",
        filetypes=[
            ("Malhas e receitas", "*.stl *.obj *.ply *.3mf *.dxf *.meshbench.json"),
            ("Todos os arquivos", "*.*"),
        ],
    )
    return chosen or None


def _open_dialog(kind):
    """Diálogo nativo para os pickers in-app (broker). kind: 'file' | 'folder'."""
    from tkinter import filedialog

    if kind == "folder":
        return filedialog.askdirectory(title="MeshBench — escolha a pasta de export") or None
    return filedialog.askopenfilename(title="MeshBench — escolha um arquivo") or None


def main(argv=None):
    """Entry point do executável: resolve o alvo, sobe o servidor e a UI."""
    import sys
    import time
    import tkinter as tk
    import webbrowser
    from tkinter import messagebox

    import uvicorn

    from meshbench.api.server import create_app, load_session, set_dialog_broker

    argv = list(sys.argv if argv is None else argv)

    root = tk.Tk()
    root.withdraw()  # esconde a janela-raiz enquanto resolve o alvo

    target = _resolve_target(argv)
    session = None
    while session is None:
        if target is None:
            chosen = _ask_open_file()
            if not chosen:
                root.destroy()
                return 0  # cancelou → sai limpo, sem servidor
            target = Path(chosen)
        try:
            session = load_session(target)
        except (FileNotFoundError, ValueError, OSError) as e:
            messagebox.showerror("MeshBench", f"Não consegui abrir o arquivo:\n\n{e}")
            target = None  # reabre o diálogo

    port = pick_free_port()
    url = f"http://127.0.0.1:{port}"

    broker = DialogBroker()
    set_dialog_broker(broker.submit)

    app = create_app(session)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    def _open_when_ready():
        for _ in range(100):
            if server.started:
                webbrowser.open(url)
                return
            time.sleep(0.1)

    threading.Thread(target=_open_when_ready, daemon=True).start()

    # janela de status (main thread): mostra a URL e um botão Sair
    root.deiconify()
    root.title("MeshBench")
    tk.Label(root, text="MeshBench está rodando.", font=("Segoe UI", 11)).pack(
        padx=24, pady=(20, 4)
    )
    tk.Label(root, text=url, fg="#0645ad").pack(padx=24, pady=(0, 12))

    def sair():
        server.should_exit = True
        server_thread.join(timeout=5.0)
        set_dialog_broker(None)
        root.destroy()

    tk.Button(root, text="Sair", command=sair, width=12).pack(pady=(0, 20))
    root.protocol("WM_DELETE_WINDOW", sair)

    def poll_broker():
        broker.drain(_open_dialog)
        root.after(100, poll_broker)

    root.after(100, poll_broker)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Rodar e ver passar (os testes de `_resolve_target`)**

Run: `.venv/Scripts/python -m pytest tests/test_desktop.py -v`
Expected: PASS (os 4 anteriores + 3 novos = 7)

- [ ] **Step 5: Fumaça manual do launcher (sem empacotar ainda)**

Run: `.venv/Scripts/python -m meshbench.desktop "docs/peças exemplo/RM-416.STL"`
(Se não houver a peça exemplo, use qualquer `.stl`.)
Expected: uma janelinha "MeshBench está rodando" abre, o navegador abre no `http://127.0.0.1:<porta>` mostrando a peça; clicar **Sair** fecha tudo. Se o console não estiver disponível, rode via `python -c "import sys; sys.argv=['x','<arquivo>']; from meshbench.desktop import main; main()"`.

- [ ] **Step 6: Commit**

```bash
git add src/meshbench/desktop.py tests/test_desktop.py
git commit -m "feat: launcher desktop — diálogo de arranque, uvicorn em thread, janela de status

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Empacotamento — `meshbench.spec`, `build_exe.ps1`, extra `build`, docs, aceite

**Files:**
- Create: `meshbench.spec`
- Create: `scripts/build_exe.ps1`
- Modify: `pyproject.toml`
- Modify: `README.md`
- Modify: `.gitignore` (garantir `dist/`, `build/`)

**Interfaces:**
- Consumes: `src/meshbench/desktop.py:main` (Task 4) como entry; `src/meshbench/api/static/` (build do frontend, Task 3).

- [ ] **Step 1: Adicionar o extra `build` ao `pyproject.toml`**

In `pyproject.toml`, replace the `[project.optional-dependencies]` block:

```toml
[project.optional-dependencies]
dev = ["pytest>=8.0", "httpx2>=0.1"]
build = ["pyinstaller>=6.0"]
```

- [ ] **Step 2: Instalar o extra de build**

Run: `.venv/Scripts/python -m pip install -e ".[build]"`
Expected: instala `pyinstaller`.

- [ ] **Step 3: Criar `meshbench.spec`**

Create `meshbench.spec` at repo root:

```python
# -*- mode: python ; coding: utf-8 -*-
"""Spec do PyInstaller — empacota a MeshBench one-dir, sem console (--windowed).

Usa collect_all para o stack científico (que carrega dados/binários nativos e
submódulos por string, invisíveis à análise estática) e inclui o frontend
buildado (api/static) como data.
"""
from PyInstaller.utils.hooks import collect_all

datas = [("src/meshbench/api/static", "meshbench/api/static")]
binaries = []
hiddenimports = []

for pkg in [
    "trimesh",
    "shapely",
    "rtree",
    "scipy",
    "fast_simplification",
    "mapbox_earcut",
    "networkx",
    "ezdxf",
    "lxml",
    "uvicorn",
]:
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# uvicorn resolve loop/protocolos por string em runtime
hiddenimports += [
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
]

a = Analysis(
    ["src/meshbench/desktop.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter.test"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MeshBench",
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="MeshBench",
)
```

- [ ] **Step 4: Criar `scripts/build_exe.ps1`**

Create `scripts/build_exe.ps1`:

```powershell
# Builda o frontend e empacota a MeshBench num executável one-dir + .zip.
# Uso: powershell -ExecutionPolicy Bypass -File scripts/build_exe.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root ".venv/Scripts/python.exe"

Write-Host "==> build do frontend"
npm --prefix "$root/web" install
npm --prefix "$root/web" run build

Write-Host "==> PyInstaller (one-dir)"
& $py -m PyInstaller "$root/meshbench.spec" --noconfirm `
    --distpath "$root/dist" --workpath "$root/build"

Write-Host "==> compactando .zip"
$version = "0.1.0"
$zip = Join-Path $root "dist/MeshBench-$version.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path (Join-Path $root "dist/MeshBench/*") -DestinationPath $zip
Write-Host "pronto: $zip"
```

- [ ] **Step 5: Garantir `dist/` e `build/` no `.gitignore`**

Check `.gitignore` for `dist/` and `build/`; if absent, append:

```
/dist/
/build/
```

- [ ] **Step 6: Rodar o build**

Run: `powershell -ExecutionPolicy Bypass -File scripts/build_exe.ps1`
Expected: gera `dist/MeshBench/MeshBench.exe` e `dist/MeshBench-0.1.0.zip` sem erro fatal.

- [ ] **Step 7: Aceite de ouro — round-trip do `.exe`**

Numa venv/ambiente **sem** as deps de dev (idealmente uma máquina/So sem Python; no mínimo um shell fora do `.venv`), rodar `dist/MeshBench/MeshBench.exe`:
1. o diálogo nativo abre → selecionar um STL real (`RM-416.STL` ou a fruteira);
2. o navegador abre e o app carrega a peça — **sem traceback** na janela/console do bundle;
3. na barra EXPORTA, gerar um **DXF R12 (3DFACE)** e confirmar que o arquivo é criado e abre no Promob;
4. clicar **Procurar…** (abrir e pasta) → o diálogo nativo abre e devolve um caminho;
5. o botão **Sair** encerra o servidor e o processo.

Se aparecer `ModuleNotFoundError`/`FileNotFoundError` de algum pacote no passo 2, adicionar o pacote ao laço `collect_all` (ou o submódulo a `hiddenimports`) em `meshbench.spec` e repetir do Step 6. Este é o risco conhecido do PyInstaller com stack científico.

- [ ] **Step 8: Documentar no `README.md`**

Add a new section after the "Testes" section:

```markdown
## Empacotamento desktop (.exe)

Para gerar o executável Windows (roda sem Python/npm instalados):

    .venv\Scripts\python -m pip install -e ".[build]"
    powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1

O script builda o frontend e roda o PyInstaller (`meshbench.spec`, one-dir),
gerando `dist/MeshBench/MeshBench.exe` e `dist/MeshBench-<versão>.zip`. Distribua
o `.zip`: o usuário extrai e dá duplo-clique no `.exe` — um diálogo nativo pede o
arquivo CAD/receita e o app abre no navegador. Também dá para arrastar um arquivo
sobre o `.exe`. (Instalador Inno Setup fica para quando o app estabilizar.)
```

- [ ] **Step 9: Atualizar `CLAUDE.md` (status da fase)**

In `CLAUDE.md`, update the "Project status" phase line to note Phase 7 packaging done, e.g. mark that the `.exe` packaging sub-project of Phase 7 is implemented (presets/batch still pending).

- [ ] **Step 10: Rodar a suíte inteira (nada quebrou)**

Run: `.venv/Scripts/python -m pytest` and `npm --prefix web test -- --run`
Expected: tudo verde.

- [ ] **Step 11: Commit**

```bash
git add meshbench.spec scripts/build_exe.ps1 pyproject.toml README.md CLAUDE.md .gitignore
git commit -m "build: empacotamento .exe (PyInstaller one-dir + zip) e docs

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Revisão final do branch + merge

Após as 5 tasks, rodar a revisão final do branch inteiro (opus, modelo mais capaz) contra este plano e o spec; corrigir o que aparecer; então **merge local na main + push** (padrão das fases anteriores). O aceite-chave da fase é o round-trip do `.exe` (Task 5, Step 7) — a revisão deve confirmar que ele foi executado, não só que o código compila.
