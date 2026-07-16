"""Servidor local do MeshBench. Fase 3: viewport com mutações explícitas (PATCH componente, POST preview, POST save); local-only (127.0.0.1)."""

import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from meshbench.api.geometry import build_scene_glb, display_records
from meshbench.api.session_ops import preview_op, save_recipe, update_component
from meshbench.core.analyze.components import split_components
from meshbench.core.io.readers import read_mesh
from meshbench.core.pipeline import FACE_BUDGET, process
from meshbench.core.project import Project, new_project

STATIC_DIR = Path(__file__).parent / "static"


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


def load_session(path):
    """Carrega uma receita .meshbench.json OU um arquivo de malha (projeto virtual)."""
    path = Path(path)
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
    return ProjectSession(
        project=project,
        base_dir=base_dir,
        records=records,
        warnings=warnings,
        raw_mesh=raw_mesh,
        recipe_path=recipe_path,
    )


def _project_state(session):
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
        "groups": session.project.groups,
        "components": [asdict(c) for c in session.project.components],
        "warnings": session.warnings,
        "group_faces": totals,
        "face_budget": FACE_BUDGET,
        "dims_mm": dims,
        "revision": session.revision,
    }


def create_app(session):
    app = FastAPI(title="MeshBench")

    @app.get("/api/project")
    def get_project():
        return JSONResponse(_project_state(session))

    @app.get("/api/project/geometry")
    def get_geometry():
        # sem registros (tudo removido ou sem grupo) o trimesh não exporta uma
        # cena vazia — 404 em vez de 500
        if not session.records:
            return JSONResponse(
                status_code=404,
                content={"detail": "nenhuma peça no resultado — tudo removido ou sem grupo"},
            )
        glb = build_scene_glb(display_records(session.records))
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

    @app.post("/api/project/save")
    def post_save():
        return JSONResponse({"path": str(save_recipe(session))})

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
