# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

**Phase 1 (core engine + CLI) is implemented.** The starting point was [docs/ARQUITETURA-MESHPREP.md](docs/ARQUITETURA-MESHPREP.md) (in Portuguese), a complete architecture handoff from a previous session where the whole workflow was validated with ad-hoc scripts. **Read that document before implementing anything** — it contains validated algorithms (Annex A, meant to be ported as-is, not rewritten), empirically discovered domain constraints, and a table of pitfalls already hit once ("Armadilhas Conhecidas", §15).

## Commands

- Setup: `python -m venv .venv` then `.venv/Scripts/python -m pip install -e ".[dev]"`
- Tests (fast, synthetic fixtures): `.venv/Scripts/python -m pytest`
- Single test: `.venv/Scripts/python -m pytest tests/test_ops_tube.py::test_op_tube_reduz_faces -v`
- Gold regression (needs `docs/peças exemplo/`, slow): `.venv/Scripts/python -m pytest -m slow`
- CLI: `.venv/Scripts/python -m meshbench inspect|init|apply …`
- Viewport (fase 2): `.venv/Scripts/python -m meshbench serve <arquivo>` (porta 8765)
- Frontend: `npm --prefix web install|run build|run dev|test` (build vai para `src/meshbench/api/static/`, gitignored)

Phases 1 (core+CLI) and 2 (read-only viewport: FastAPI + React/Three.js in `web/`) are implemented. Phases 3+ (selection, interactive ops, gizmos) are not yet.

## What this project is

**MeshBench** — a local web app to prepare 3D meshes exported from CAD (SolidWorks, Rhino…) for furniture-design software, primarily **Promob**. It imports STL/DXF/OBJ/PLY/3MF, lets the user split, simplify, scale, orient, and re-anchor parts, and exports **DXF R12 with `3DFACE` entities** (the validated Promob format). Every session is saved as a reproducible `*.meshbench.json` recipe.

**Core product principle: nothing is automatic and irreversible.** Geometric heuristics (part classification, unit detection) only *pre-fill suggestions*; the user always confirms by looking at the preview. STL carries no names/colors, so the user — not the algorithm — decides what each part is.

## Planned stack

- **Core:** Python 3.11+, `trimesh`, `numpy`, `scipy` (Dijkstra), `shapely` + `mapbox_earcut` + `rtree`, `ezdxf`
- **API:** FastAPI + uvicorn
- **Frontend:** Three.js (raycast selection, `TransformControls` gizmos), React + Vite

## The transformation pipeline (order is non-negotiable)

```
IMPORT → UNITS/SCALE → SPLIT → OPS (per part) → GROUP → ORIENT → ORIGIN → EXPORT
```

- **Scale to mm comes FIRST**: operation parameters (`bin_mm`, `tol`, classification thresholds) are in absolute millimeters and become garbage on unscaled meshes.
- **Origin comes LAST**: anchoring before rotation puts the origin in the wrong place (a real bug from the previous session).

## Domain constraints (empirical — do not rediscover)

- Promob accepts DXF **R12 / AC1009** with `3DFACE` entities; loose mesh in modelspace, no layers/blocks needed. Triangles repeat the 4th vertex.
- **Face budget: keep each output file under ~15k faces** (455k crashes Promob; 2k–8k is ideal). Surface this in the UI as a traffic-light budget.
- Axis convention trap: common CAD is Y-up; Promob expects Z=height, Y=depth, X=width. The validated preset `cad_to_promob` is `(x, z, y)` followed by zeroing the minimums — but it must stay a *selectable preset*, never hardcoded.
- STL stores no units. Suggest a unit from bbox heuristics (§5.2) but always ask when ambiguous.

## Known pitfalls (all hit in practice — §15 has the full table)

- Always call `mesh.merge_vertices()` after reading, or `split()` won't find components.
- Never `convex_hull` an open profile (it closes into a solid block) — warn in the UI.
- Never quadric-decimate curved wire (destroys the tips) — use the `tube` reconstruction (geodesic centerline via Dijkstra + parallel transport frames), not plane slicing.
- For `reextrude`, probe N slices and take the **largest-area** section (avoids slicing through a hole).
- Mirroring: trimesh >=4.x auto-corrects winding on negative-determinant transforms — do NOT add `mesh.invert()` after mirror (double-flip); the architecture doc's Annex A.7 predates this.
- Multi-group exports that fit together need a **common origin** (`mode: "common"`), not per-group.
- Validator: every component must be in a group or explicitly removed, or it silently disappears from the output.

## Stable component IDs

Users re-export from CAD repeatedly. Components are re-matched across imports by geometric signature `(face_count, vertex_count, rounded bbox)` so user classifications survive; unmatched parts are flagged as "new — review".

## Regression fixtures

Annex B defines three real products as gold-standard regression cases (fruteira `2191-0400`, calceiro `3214-0400`, perfil `RM-416.STL`). Phase 1 acceptance criterion: the core engine + CLI reproduces those three conversions.
