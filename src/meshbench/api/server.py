"""Servidor local do MeshBench. Fase 3: viewport com mutações explícitas (PATCH componente, POST preview, POST save); local-only (127.0.0.1)."""

import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from meshbench.api.geometry import build_scene_glb, display_records
from meshbench.api.session_ops import (
    export_project,
    preview_op,
    redo,
    reimport_project,
    save_recipe,
    undo,
    update_component,
    update_export,
    update_orient,
    update_origin,
    update_scale,
)
from meshbench.core.transform.origin import origin_distance
from meshbench.core.analyze.components import split_components
from meshbench.core.io.readers import read_mesh
from meshbench.core.pipeline import FACE_BUDGET, process
from meshbench.core.project import Project, new_project

STATIC_DIR = Path(__file__).parent / "static"

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


@dataclass
class ProjectSession:
    """Um projeto carregado em memória (um por servidor, conforme §13)."""

    project: Project
    base_dir: Path
    records: list
    warnings: list = field(default_factory=list)
    raw_mesh: object = None
    recipe_path: Path | None = None
    revision: int = 0
    lock: threading.RLock = field(default_factory=threading.RLock)
    # cache do GLB servido por /api/project/geometry: (revision, bytes). O
    # viewport agora mantém a cena entre trocas de geometria e pode reconsultar
    # a mesma revision (ex.: reconexão) sem pagar o custo de reconstruir o GLB;
    # a invalidação é automática porque toda mutação incrementa revision.
    glb_cache: tuple | None = None
    undo_stack: list = field(default_factory=list)
    redo_stack: list = field(default_factory=list)


def _load_fields(path):
    """Lê uma receita .json ou um arquivo de malha e devolve os campos derivados."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"arquivo não encontrado: {path}")
    if path.suffix.lower() == ".json":
        project = Project.load(path)
        base_dir = path.resolve().parent
        recipe_path = path.resolve()
        src = Path(project.source["path"])
        if not src.is_absolute():
            src = base_dir / src
        raw_mesh = read_mesh(src)
    else:
        raw_mesh = read_mesh(path)
        project = new_project(path.stem, path, raw_mesh, split_components(raw_mesh))
        project.source["path"] = path.name
        base_dir = path.resolve().parent
        recipe_path = (base_dir / f"{path.stem}.meshbench.json").resolve()
    records, warnings = process(project, base_dir, mesh=raw_mesh)
    return {
        "project": project,
        "base_dir": base_dir,
        "records": records,
        "warnings": warnings,
        "raw_mesh": raw_mesh,
        "recipe_path": recipe_path,
    }


def load_session(path):
    """Carrega uma receita .meshbench.json OU um arquivo de malha (projeto virtual)."""
    return ProjectSession(**_load_fields(path))


def open_project(session, path):
    """Carrega outra receita/malha na sessão existente, substituindo tudo.

    Reseta desfazer/refazer, o cache de GLB e a revision — é um projeto novo. Se a
    leitura falhar, ergue antes de mutar a sessão (o estado antigo fica intacto).
    """
    with session.lock:
        fields = _load_fields(path)  # pode erguer FileNotFoundError/ValueError
        session.project = fields["project"]
        session.base_dir = fields["base_dir"]
        session.records = fields["records"]
        session.warnings = fields["warnings"]
        session.raw_mesh = fields["raw_mesh"]
        session.recipe_path = fields["recipe_path"]
        session.revision += 1
        session.glb_cache = None
        session.undo_stack.clear()
        session.redo_stack.clear()


def _project_state(session):
    # RLock — reentra sem problema se o chamador já segura o lock (ex.:
    # update_component termina com o lock ainda aberto e monta o estado logo
    # em seguida); protege contra ler records/project a meio de um reprocesso
    # concorrente.
    with session.lock:
        totals = {}
        for r in session.records:
            totals[r.group] = totals.get(r.group, 0) + len(r.mesh.faces)
        dims = None
        if session.records:
            pts = np.vstack([r.mesh.bounds for r in session.records])
            dims = (pts.max(axis=0) - pts.min(axis=0)).tolist()
        return {
            "name": session.project.name,
            "source": session.project.source,
            "scale": session.project.scale,
            "orient": session.project.orient,
            "export": session.project.export,
            "origin": session.project.origin,
            "groups": session.project.groups,
            "components": [asdict(c) for c in session.project.components],
            "warnings": session.warnings,
            "group_faces": totals,
            "face_budget": FACE_BUDGET,
            "dims_mm": dims,
            "origin_distance_mm": (
                origin_distance([r.mesh for r in session.records])
                if session.records
                else None
            ),
            "source_dims": (
                [float(x) for x in session.raw_mesh.extents]
                if session.raw_mesh is not None
                else None
            ),
            "revision": session.revision,
            "can_undo": len(session.undo_stack) > 0,
            "can_redo": len(session.redo_stack) > 0,
        }


def create_app(session):
    app = FastAPI(title="MeshBench")

    @app.get("/api/project")
    def get_project():
        return JSONResponse(_project_state(session))

    @app.get("/api/project/geometry")
    def get_geometry():
        # lock ao redor da checagem + build do GLB: sem isto um reprocesso
        # concorrente poderia trocar session.records entre a checagem e a
        # leitura, ou o build ler registros a meio de mutação
        with session.lock:
            # sem registros (tudo removido ou sem grupo) o trimesh não exporta
            # uma cena vazia — 404 em vez de 500
            if not session.records:
                return JSONResponse(
                    status_code=404,
                    content={"detail": "nenhuma peça no resultado — tudo removido ou sem grupo"},
                )
            if session.glb_cache is not None and session.glb_cache[0] == session.revision:
                glb = session.glb_cache[1]
            else:
                glb = build_scene_glb(display_records(session.records))
                session.glb_cache = (session.revision, glb)
        return Response(content=glb, media_type="model/gltf-binary")

    @app.patch("/api/component/{comp_id}")
    def patch_component(comp_id: str, changes: dict):
        try:
            update_component(session, comp_id, changes)
        except KeyError as e:
            return JSONResponse(status_code=404, content={"detail": str(e).strip("'\"")})
        except ValueError as e:
            return JSONResponse(status_code=422, content={"detail": str(e)})
        return JSONResponse(_project_state(session))

    @app.post("/api/preview/{comp_id}")
    def post_preview(comp_id: str, body: dict):
        try:
            glb, before, after = preview_op(session, comp_id, body.get("operation"))
        except KeyError as e:
            return JSONResponse(status_code=404, content={"detail": str(e).strip("'\"")})
        except ValueError as e:
            return JSONResponse(status_code=422, content={"detail": str(e)})
        if glb is None:
            return JSONResponse(
                status_code=404,
                content={"detail": "a operação não produziu malha para esta peça"},
            )
        return Response(
            content=glb,
            media_type="model/gltf-binary",
            headers={"X-Faces-Before": str(before), "X-Faces-After": str(after)},
        )

    @app.patch("/api/scale")
    def patch_scale(changes: dict):
        try:
            update_scale(session, changes)
        except ValueError as e:
            return JSONResponse(status_code=422, content={"detail": str(e)})
        return JSONResponse(_project_state(session))

    @app.patch("/api/orient")
    def patch_orient(changes: dict):
        try:
            update_orient(session, changes)
        except ValueError as e:
            return JSONResponse(status_code=422, content={"detail": str(e)})
        return JSONResponse(_project_state(session))

    @app.patch("/api/origin")
    def patch_origin(changes: dict):
        try:
            update_origin(session, changes)
        except ValueError as e:
            return JSONResponse(status_code=422, content={"detail": str(e)})
        return JSONResponse(_project_state(session))

    @app.patch("/api/export")
    def patch_export(changes: dict):
        try:
            update_export(session, changes)
        except ValueError as e:
            return JSONResponse(status_code=422, content={"detail": str(e)})
        return JSONResponse(_project_state(session))

    @app.post("/api/export")
    def post_export():
        try:
            result = export_project(session)
        except ValueError as e:
            return JSONResponse(status_code=422, content={"detail": str(e)})
        return JSONResponse({"files": result.files, "warnings": result.warnings})

    @app.post("/api/project/reimport")
    def post_reimport():
        try:
            reimport_project(session)
        except FileNotFoundError as e:
            return JSONResponse(status_code=404, content={"detail": str(e)})
        except ValueError as e:
            return JSONResponse(status_code=422, content={"detail": str(e)})
        return JSONResponse(_project_state(session))

    @app.post("/api/project/open")
    def post_open(body: dict):
        path = body.get("path")
        if not isinstance(path, str) or not path.strip():
            return JSONResponse(
                status_code=422, content={"detail": "path deve ser um caminho não vazio"}
            )
        try:
            open_project(session, path.strip())
        except FileNotFoundError as e:
            return JSONResponse(status_code=404, content={"detail": str(e)})
        except ValueError as e:
            return JSONResponse(status_code=422, content={"detail": str(e)})
        return JSONResponse(_project_state(session))

    @app.post("/api/undo")
    def post_undo():
        try:
            undo(session)
        except ValueError as e:
            return JSONResponse(status_code=409, content={"detail": str(e)})
        return JSONResponse(_project_state(session))

    @app.post("/api/redo")
    def post_redo():
        try:
            redo(session)
        except ValueError as e:
            return JSONResponse(status_code=409, content={"detail": str(e)})
        return JSONResponse(_project_state(session))

    @app.post("/api/project/save")
    def post_save():
        return JSONResponse({"path": str(save_recipe(session))})

    @app.post("/api/pick/file")
    def post_pick_file():
        return _pick("file")

    @app.post("/api/pick/folder")
    def post_pick_folder():
        return _pick("folder")

    if STATIC_DIR.exists():
        app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
    else:

        @app.get("/")
        def index_hint():
            return JSONResponse(
                {
                    "detail": "frontend não buildado — rode: "
                    "npm --prefix web install && npm --prefix web run build"
                }
            )

    return app
