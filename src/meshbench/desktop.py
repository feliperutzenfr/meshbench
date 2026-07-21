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
