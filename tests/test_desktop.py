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
