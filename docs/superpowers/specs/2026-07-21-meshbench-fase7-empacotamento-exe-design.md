# Fase 7 — Empacotamento desktop (`.exe`) da MeshBench

> Spec de design. Primeiro subprojeto da Fase 7 ("Extras"). Os outros
> subprojetos da fase (presets por família, batch) terão cada um seu próprio
> ciclo spec → plano → implementação.

## Objetivo

Entregar um executável Windows que o designer roda **sem Python nem npm
instalados**: duplo-clique no `.exe` → escolhe o arquivo CAD num diálogo nativo
→ o MeshBench abre no navegador padrão. Distribuído como uma pasta compactada em
`.zip` (PyInstaller *one-dir*).

Um instalador Inno Setup fica **explicitamente adiado** para quando o app
estabilizar (decisão do usuário: "por agora .zip; futuramente, quando não
tivermos mais nada para mudar no app, fazemos a última opção de inno setup").

## Contexto atual

- O app hoje sobe por `meshbench serve <alvo>` ([cli.py](../../../src/meshbench/cli.py) `_cmd_serve`, linha 76):
  `create_app(session)` **exige** um alvo (receita ou malha). Não existe modo de
  arranque sem argumento — essa é a principal lacuna da fase.
- O servidor é local: uvicorn em `127.0.0.1`, porta fixa `8765`.
- O frontend usa URLs relativas (`fetch("/api/…")`), então a porta do servidor é
  transparente para ele — trocar a porta não exige mudança no frontend.
- Os campos de caminho na UI (abrir receita em `ProjectActions`, pasta de export
  em `ExportBar`) são hoje **texto digitável**, sem picker nativo.
- `tkinter` acompanha os builds oficiais do Python no Windows e é bundlado pelo
  hook do PyInstaller — é a via do diálogo nativo, sem dependência nova em runtime.

## Decisões travadas (do brainstorming)

1. Construir o `.exe` primeiro (antes de presets e batch).
2. Arranque sem argumento abre **diálogo nativo** (tkinter) para escolher o
   arquivo; também aceita arquivo arrastado no ícone / "Abrir com" (via `argv`).
3. Incluir **os dois** pickers nativos in-app: "Procurar…" para abrir um arquivo
   e para escolher a pasta de export.
4. Distribuição **one-dir → `.zip`** agora; Inno Setup depois.

## Arquitetura

Um novo **launcher** (`src/meshbench/desktop.py`) é o entry point do PyInstaller,
separado do CLI `meshbench` para manter o console limpo. Ele é dono da main
thread e roda o loop do tkinter; o uvicorn roda numa thread de fundo. Um **dialog
broker** na main thread permite que as rotas HTTP (que rodam na thread do
uvicorn) abram diálogos nativos sem tocar em tkinter fora da main thread.

```
duplo-clique / arrastar no ícone
        │
        ▼
  desktop.py (main thread, dono do loop tkinter)
        │
        ├─ arquivo em argv? ── sim ─► usa
        │        └─ não ─► askopenfilename (diálogo nativo)  ── cancelou ─► sai
        │
        ├─ escolhe porta livre (bind :0)
        ├─ sobe uvicorn.Server numa thread de fundo (127.0.0.1:porta)
        ├─ abre o navegador na URL quando o servidor está de pé
        └─ janelinha de status "MeshBench rodando — [Sair]"
                 └─ [Sair]/fechar ─► server.should_exit = True ─► processo encerra

  in-app "Procurar…"  ── POST /api/pick/file|folder ──►  broker (main thread)
                                                              └─ diálogo nativo
                                                                     └─ { path }
```

### Componentes

**1. Launcher — `src/meshbench/desktop.py` (novo)**

Ponto de entrada do bundle. Fluxo `main()`:

- Resolve o alvo: se `sys.argv[1]` existe e é um arquivo, usa; senão abre
  `filedialog.askopenfilename` filtrando `*.stl *.obj *.ply *.3mf *.dxf
  *.meshbench.json`. Se o usuário cancelar, encerra limpo (nenhum servidor sobe).
- Se o alvo for inválido (`read_mesh`/`load_session` erguem), mostra um
  `messagebox` nativo com a mensagem em pt-BR e reabre o diálogo; cancelar sai.
- Escolhe uma porta livre (helper `pick_free_port()` — abre um socket em
  `("127.0.0.1", 0)`, lê a porta atribuída, fecha).
- Cria a app (`create_app(session)`) e sobe `uvicorn.Server(config)` numa thread
  daemon. Guarda a referência ao `Server` para poder sinalizar `should_exit`.
- Espera o servidor ficar de pé (poll de `server.started`) e então
  `webbrowser.open(url)`.
- Instala o broker (ver componente 2) e roda o loop tkinter da janelinha de
  status. A janela mostra a URL e um botão **Sair**; `Sair`/fechar seta
  `server.should_exit = True`, aguarda a thread encerrar e sai do processo.

**2. Dialog broker — na main thread (parte do `desktop.py`)**

Diálogos nativos precisam rodar na main thread; as rotas HTTP rodam na thread do
uvicorn. O broker é a ponte, sem tkinter multi-thread:

- Uma fila thread-safe (`queue.Queue`) de pedidos `{"kind": "file"|"folder",
  "event": threading.Event, "result": [holder]}`.
- O loop tkinter faz *polling* via `root.after(100, drain)`: para cada pedido na
  fila, abre o diálogo nativo correspondente na main thread, grava o caminho (ou
  `None` se cancelou) no holder e seta o `Event`.
- As rotas chamam uma função `request_dialog(kind) -> str | None` que enfileira o
  pedido e bloqueia no `Event` (com timeout de guarda). A função é registrada num
  ponto de acesso do módulo do servidor (ex.: `server.set_dialog_broker(fn)`); se
  nenhum broker estiver registrado (modo `meshbench serve` no dev), as rotas
  respondem 409.

**3. Rotas novas — `src/meshbench/api/server.py`**

- `POST /api/pick/file` → `{ "path": "…" | null }` (null = cancelou).
- `POST /api/pick/folder` → `{ "path": "…" | null }`.
- Ambas chamam `request_dialog(...)`. Sem broker registrado → **409** com corpo
  pt-BR `{"detail": "diálogo nativo indisponível (rode pelo app desktop)"}`.
- Um módulo-nível `_dialog_broker` (callable ou `None`) + `set_dialog_broker(fn)`
  guardam o broker. O launcher registra; o `_cmd_serve` do dev não.

**4. Frontend — pickers "Procurar…"**

- `web/src/lib/client.js`: `pickFile()` e `pickFolder()` chamando as rotas.
  Tratam 409 devolvendo `{ unavailable: true }` em vez de erro.
- `web/src/components/ProjectActions.jsx`: botão "Procurar…" ao lado do input de
  caminho de "Abrir"; ao retornar um path, preenche o input. Em `unavailable`,
  não faz nada (o campo segue digitável).
- `web/src/components/ExportBar.jsx`: botão "Procurar…" ao lado do input de pasta
  de export; mesmo comportamento. Ao escolher, dispara o mesmo `patchExport({
  out_dir })` que a edição manual do campo já usa.
- O campo digitável permanece em ambos os casos — é o *fallback* quando o broker
  não existe (dev) e mantém o app usável por `meshbench serve`.

**5. Build — `scripts/build_exe.ps1` + `meshbench.spec`**

- `build_exe.ps1`: (a) `npm --prefix web install` se necessário e `npm --prefix
  web run build` (popula `src/meshbench/api/static/`); (b) `pyinstaller
  meshbench.spec --noconfirm`; (c) compacta `dist/MeshBench/` em
  `dist/MeshBench-<versão>.zip`.
- `meshbench.spec`: entry `src/meshbench/desktop.py`, one-dir, `--windowed`
  (sem console). Usa `collect_all` / `collect_data_files` / `collect_submodules`
  para o stack científico frágil: **trimesh, shapely, rtree, scipy,
  fast_simplification, mapbox_earcut, networkx, ezdxf, lxml, uvicorn**. Inclui
  `src/meshbench/api/static` como *data* no bundle. `name="MeshBench"`.
- `pyinstaller` entra num extra `build` no `pyproject.toml` (`pip install -e
  ".[build]"`), fora do runtime.

## Fluxo de dados

**Arranque:** duplo-clique → launcher resolve alvo (argv ou diálogo) → porta
livre → `create_app(session)` → uvicorn na thread de fundo → navegador na URL →
app carrega via `fetchProject()` (URLs relativas, porta transparente).

**Picker in-app:** clique em "Procurar…" → `POST /api/pick/file|folder` → rota
chama `request_dialog` → broker abre o diálogo nativo na main thread → caminho
volta no JSON → frontend preenche o campo.

## Tratamento de erros

- **Cancelar o diálogo de arranque:** encerra limpo, nenhum servidor sobe.
- **Alvo inválido no arranque:** `messagebox` nativo pt-BR + reabre o diálogo;
  cancelar sai.
- **Porta:** dinâmica (bind `:0`), então sem colisão com um `8765` já ocupado.
- **Broker fora do modo desktop:** 409 amigável; o frontend ignora e mantém o
  campo digitável (o app segue 100% usável no dev via `meshbench serve`).
- **Timeout do broker:** se o diálogo não resolver dentro de um limite de guarda,
  `request_dialog` devolve `None` (tratado como cancelamento) — evita travar a
  requisição HTTP indefinidamente.
- **Módulo faltando no bundle (hidden import):** aparece como traceback no
  round-trip de aceite; corrige-se adicionando o `collect_*`/hidden import no
  `.spec`. É o risco principal e conhecido do PyInstaller com stack científico.

## Testes

**Unit (pytest):**
- `pick_free_port()` devolve uma porta que dá para fazer bind e é `> 0`.
- Broker: `request_dialog` enfileira e resolve com um diálogo *fake* (injetado),
  devolvendo path e `None` (cancelamento); respeita o timeout de guarda.
- Rotas `POST /api/pick/file` e `/api/pick/folder`: com broker fake registrado
  devolvem `{path}`/`{path: null}`; **sem** broker devolvem 409 com detail pt-BR.

**Aceite (o de ouro) — manual, num ambiente sem as deps de dev:**
- Numa venv limpa (idealmente uma máquina Windows sem Python), rodar
  `dist/MeshBench/MeshBench.exe`:
  1. abre o diálogo nativo, seleciona um STL real (RM-416 ou fruteira);
  2. o navegador abre e o app carrega a peça sem traceback no bundle;
  3. exportar um DXF R12 (3DFACE) que abre no Promob;
  4. "Procurar…" abre o diálogo nativo e devolve um caminho;
  5. o botão Sair encerra o servidor e o processo.
- Sanidade do motor dentro do bundle é coberta indiretamente por (1)–(3): o
  pipeline não muda nesta fase, então as 3 regressões de ouro continuam valendo
  pela suíte normal; o que a fase adiciona é o empacotamento, cujo aceite-chave é
  o round-trip do `.exe`.

## Fora de escopo (consciente)

- Instalador Inno Setup (fase futura, quando o app estabilizar).
- Assinatura de código — o SmartScreen vai avisar "editor desconhecido";
  aceitável por ora, fica anotado.
- Auto-update.
- macOS / Linux (o alvo é Windows/Promob).
