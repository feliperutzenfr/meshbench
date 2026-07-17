"""Modelo de dados do projeto — a receita .meshbench.json (§10 do doc).

Reprodutível, diffável, versionável no git. Campos auto_* são sugestões da
heurística; campos user_* e as escolhas de operação/grupo são do USUÁRIO —
o rematch por assinatura preserva essas escolhas após re-export do CAD.
"""

import hashlib
import json
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

from meshbench.core.analyze.classify import SUGGESTED_OP, classify
from meshbench.core.analyze.units import guess_unit

DEFAULT_SCALE = {
    "mode": "unit_convert",
    "from_unit": "mm",
    "to_unit": "mm",
    "value": None,
    "per_axis": None,
    "fit": None,
    "factor": [1, 1, 1],
}
DEFAULT_ORIENT = {
    "axis_remap": "identidade",
    "custom_remap": None,
    "rotations": [],
    "mirror": [],
}
DEFAULT_ORIGIN = {
    "mode": "common",
    "anchor": "bbox_min",
    "feature_ref": None,
    "snap_point": None,
    "offset": [0, 0, 0],
}
DEFAULT_EXPORT = {
    "format": "dxf_r12",
    "out_dir": "out/",
    "naming": "{project}_{group}.dxf",
}


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class ComponentEntry:
    id: str
    signature: str
    instances: int
    face_count: int
    bbox: list
    auto_class: str
    user_label: str | None = None
    operation: dict = field(default_factory=lambda: {"type": "keep", "params": {}})
    group: str | None = None
    needs_review: bool = False


@dataclass
class Project:
    name: str
    source: dict
    scale: dict = field(default_factory=lambda: dict(DEFAULT_SCALE))
    components: list[ComponentEntry] = field(default_factory=list)
    groups: list = field(default_factory=list)
    orient: dict = field(default_factory=lambda: dict(DEFAULT_ORIENT))
    origin: dict = field(default_factory=lambda: dict(DEFAULT_ORIGIN))
    export: dict = field(default_factory=lambda: dict(DEFAULT_EXPORT))
    version: int = 1

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        d = dict(d)
        d["components"] = [ComponentEntry(**c) for c in d.get("components", [])]
        d["scale"] = {**DEFAULT_SCALE, **d.get("scale", {})}
        d["orient"] = {**DEFAULT_ORIENT, **d.get("orient", {})}
        d["origin"] = {**DEFAULT_ORIGIN, **d.get("origin", {})}
        d["export"] = {**DEFAULT_EXPORT, **d.get("export", {})}
        custom_remap = d["orient"]["custom_remap"]
        if d["orient"]["axis_remap"] == "custom" and not (
            isinstance(custom_remap, (list, tuple)) and len(custom_remap) == 3
        ):
            raise ValueError(
                "receita inválida: axis_remap 'custom' exige custom_remap "
                "com 3 eixos (±x, ±y, ±z)"
            )
        return cls(**d)

    def save(self, path):
        Path(path).write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )

    @classmethod
    def load(cls, path):
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def _entry_from_family(fam, group):
    auto = classify(fam.meshes[0])
    return ComponentEntry(
        id=fam.id,
        signature=fam.signature,
        instances=fam.instances,
        face_count=fam.face_count,
        bbox=fam.bbox,
        auto_class=auto,
        operation={"type": SUGGESTED_OP[auto], "params": {}},
        group=None if SUGGESTED_OP[auto] == "remove" else group,
    )


def new_project(name, source_path, mesh, families):
    """Receita inicial: sugestões preenchidas, tudo num grupo 'saida'. O usuário edita."""
    unit, reason = guess_unit(mesh)
    detected = unit or "mm"
    return Project(
        name=name,
        source={
            "path": str(source_path),
            "sha256": sha256_of(source_path),
            "detected_units": detected,
            "detection_note": reason,
            "units": detected,  # o que o USUÁRIO confirmou (editável)
        },
        scale={**DEFAULT_SCALE, "from_unit": detected},
        components=[_entry_from_family(f, "saida") for f in families],
        groups=[{"name": "saida", "role": "fixed"}],
    )


def rematch(project, families):
    """Casa famílias novas com a receita por assinatura, preservando escolhas do usuário.

    Retorna (projeto_novo, avisos) — o projeto original NÃO é modificado.
    Famílias sem par entram como needs_review=True; entradas cuja peça
    sumiu são removidas e reportadas.
    """
    warnings_list = []
    by_sig = {c.signature: c for c in project.components}
    new_components = []
    matched = set()
    for fam in families:
        old = by_sig.get(fam.signature)
        if old is not None:
            matched.add(old.signature)
            new_components.append(
                ComponentEntry(
                    id=fam.id,
                    signature=fam.signature,
                    instances=fam.instances,
                    face_count=fam.face_count,
                    bbox=fam.bbox,
                    auto_class=old.auto_class,
                    user_label=old.user_label,
                    operation=old.operation,
                    group=old.group,
                    needs_review=False,
                )
            )
        else:
            e = _entry_from_family(fam, group=None)
            e.needs_review = True
            new_components.append(e)
            warnings_list.append(f"componente novo — revisar: {fam.signature}")
    for c in project.components:
        if c.signature not in matched:
            label = c.user_label or c.auto_class
            warnings_list.append(f"componente sumiu do source: {label} ({c.signature})")
    return replace(project, components=new_components), warnings_list
