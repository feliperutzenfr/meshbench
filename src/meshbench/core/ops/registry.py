"""Registro central de operações de malha. Toda operação recebe uma malha e
params explícitos (todos expostos na UI) e retorna a malha nova, ou None = removida."""

OPS = {}


def register(name, fn):
    OPS[name] = fn


def apply_op(mesh, op):
    """Aplica a operação descrita na receita: {"type": ..., "params": {...}}."""
    kind = op.get("type", "keep")
    if kind not in OPS:
        raise ValueError(f"operação '{kind}' desconhecida (disponíveis: {sorted(OPS)})")
    return OPS[kind](mesh, **(op.get("params") or {}))
