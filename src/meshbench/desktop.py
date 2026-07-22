"""Launcher desktop do MeshBench: entry point do executável empacotado (PyInstaller).

Roda o loop do tkinter na main thread (diálogos nativos + janela de status) e o
uvicorn numa thread de fundo. Sem argumento, abre um diálogo nativo para escolher
o arquivo; também aceita um arquivo passado em argv (arrastado no ícone).
"""

import queue
import socket
import threading
from pathlib import Path


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
        cancelled = threading.Event()
        holder: list = [None]
        self._q.put((kind, holder, done, cancelled))
        if not done.wait(self._timeout):
            cancelled.set()  # expirou: ninguém mais espera este pedido
            return None
        return holder[0]

    def drain(self, open_dialog) -> None:
        """Processa os pedidos pendentes chamando open_dialog(kind) -> str|None.

        Chamado periodicamente pelo loop tk (main thread). open_dialog roda na
        main thread e é quem de fato abre o diálogo nativo. Pedidos que já
        expiraram (submit deu timeout) são descartados sem abrir diálogo.
        """
        while True:
            try:
                kind, holder, done, cancelled = self._q.get_nowait()
            except queue.Empty:
                return
            if cancelled.is_set():
                continue  # ninguém espera este pedido — descarta
            try:
                holder[0] = open_dialog(kind)
            finally:
                done.set()


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
    import os
    import sys
    import tkinter as tk
    import webbrowser
    from tkinter import messagebox

    import uvicorn

    from meshbench.api.server import create_app, load_session, set_dialog_broker

    # PyInstaller --windowed (sem console): sys.stdout/stderr vêm None. O uvicorn
    # (e qualquer lib que chame .isatty()/.write() neles) quebra com AttributeError
    # sem isso — armadilha conhecida de apps windowed do PyInstaller.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")

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

    # abre o navegador quando o servidor sobe; roda no loop tk (main thread) para
    # poder avisar com messagebox, com segurança, se o servidor morrer no arranque
    ready_tries = [0]

    def check_ready():
        if server.started:
            webbrowser.open(url)
            return
        if not server_thread.is_alive():
            messagebox.showerror(
                "MeshBench",
                "O servidor não subiu. Feche a janela e tente novamente.",
            )
            return
        ready_tries[0] += 1
        if ready_tries[0] > 100:  # ~10s ainda sem subir (e a thread viva)
            messagebox.showerror(
                "MeshBench",
                "O servidor demorou demais para responder. Feche e tente de novo.",
            )
            return
        root.after(100, check_ready)

    root.after(100, check_ready)

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
        # re-arma sempre, mesmo se um diálogo nativo lançar — senão o polling do
        # broker morreria em silêncio e os pickers in-app travariam até o timeout
        try:
            broker.drain(_open_dialog)
        finally:
            root.after(100, poll_broker)

    root.after(100, poll_broker)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
