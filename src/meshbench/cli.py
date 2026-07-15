"""CLI do MeshBench: inspect (analisa), init (gera receita), apply (exporta)."""

import argparse
import sys
from pathlib import Path

from meshbench.core.analyze.classify import SUGGESTED_OP, classify
from meshbench.core.analyze.components import split_components
from meshbench.core.analyze.units import guess_unit, human_dimensions
from meshbench.core.io.readers import read_mesh
from meshbench.core.pipeline import run
from meshbench.core.project import Project, new_project, rematch


def _cmd_inspect(args):
    mesh = read_mesh(args.arquivo)
    unit, reason = guess_unit(mesh)
    print(f"Arquivo: {args.arquivo}")
    print(f"Dimensões (na unidade do arquivo): {human_dimensions(mesh)}")
    print(f"Unidade sugerida: {unit or 'ambígua'} — {reason}")
    fams = split_components(mesh)
    print(f"\n{len(fams)} famílias de componentes:")
    print(f"{'id':<5} {'inst':>4} {'faces':>7}  {'classe sugerida':<15} {'op sugerida'}")
    for f in fams:
        cls = classify(f.meshes[0])
        print(f"{f.id:<5} {f.instances:>4} {f.face_count:>7}  {cls:<15} {SUGGESTED_OP[cls]}")
    total = sum(f.instances * f.face_count for f in fams)
    print(f"\nTotal: {total} faces")
    return 0


def _cmd_init(args):
    src = Path(args.arquivo)
    name = args.nome or src.stem
    mesh = read_mesh(src)
    fams = split_components(mesh)
    p = new_project(name, src, mesh, fams)
    out_path = Path(args.saida) if args.saida else src.parent / f"{name}.meshbench.json"
    # caminho do source relativo à pasta da receita, quando possível
    try:
        p.source["path"] = str(src.resolve().relative_to(out_path.resolve().parent))
    except ValueError:
        p.source["path"] = str(src.resolve())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    p.save(out_path)
    print(f"Receita criada: {out_path}")
    print("Revise as operações e grupos sugeridos antes de aplicar — a heurística só sugere.")
    return 0


def _cmd_apply(args):
    recipe_path = Path(args.receita)
    p = Project.load(recipe_path)
    base_dir = recipe_path.resolve().parent
    if args.reimport:
        src = Path(p.source["path"])
        if not src.is_absolute():
            src = base_dir / src
        mesh = read_mesh(src)
        p, warnings_list = rematch(p, split_components(mesh))
        for w in warnings_list:
            print(f"⚠ {w}")
        p.save(recipe_path)
    res = run(p, base_dir)
    p.save(recipe_path)  # grava o fator de escala resultante
    for w in res.warnings:
        print(f"⚠ {w}")
    for f in res.files:
        ok = "✓" if f["faces"] <= 15000 else "⚠"
        print(f"{ok} {f['group']}: {f['path']} ({f['faces']} faces)")
    if not res.files:
        print("nenhum arquivo exportado — confira grupos e operações na receita")
    return 0


def main(argv=None):
    # stdout redirecionado/pipado no Windows costuma cair em cp1252 — os símbolos
    # ⚠/✓ quebram com UnicodeEncodeError; força substituição em vez de crashar.
    if (
        hasattr(sys.stdout, "reconfigure")
        and sys.stdout.encoding
        and sys.stdout.encoding.lower() not in ("utf-8", "utf8")
    ):
        sys.stdout.reconfigure(errors="replace")

    parser = argparse.ArgumentParser(
        prog="meshbench",
        description="Prepara malhas 3D exportadas de CAD para software de projeto (Promob e outros).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ins = sub.add_parser("inspect", help="analisa um arquivo e lista os componentes")
    p_ins.add_argument("arquivo")
    p_ins.set_defaults(fn=_cmd_inspect)

    p_init = sub.add_parser("init", help="cria uma receita .meshbench.json com sugestões")
    p_init.add_argument("arquivo")
    p_init.add_argument("-o", "--saida", default=None, help="caminho da receita gerada")
    p_init.add_argument("--nome", default=None, help="nome do projeto (padrão: nome do arquivo)")
    p_init.set_defaults(fn=_cmd_init)

    p_apply = sub.add_parser("apply", help="aplica uma receita e exporta os arquivos")
    p_apply.add_argument("receita")
    p_apply.add_argument(
        "--reimport",
        action="store_true",
        help="re-lê o source e re-casa componentes por assinatura antes de aplicar",
    )
    p_apply.set_defaults(fn=_cmd_apply)

    args = parser.parse_args(argv)
    try:
        return args.fn(args)
    except (FileNotFoundError, ValueError) as e:
        print(f"erro: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
