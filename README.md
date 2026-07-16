# MeshBench

Prepara malhas 3D exportadas de CAD (SolidWorks, Rhino, Inventor…) para uso em
software de projeto de móveis (Promob e outros): simplifica, escala, orienta,
ancora a origem e exporta DXF R12 (3DFACE).

**Princípio central: nada é automático e irreversível.** As heurísticas só
sugerem — o usuário decide o que cada peça é e o que fazer com ela.

## Instalação (desenvolvimento)

    python -m venv .venv
    .venv\Scripts\python -m pip install -e ".[dev]"

## Uso

    meshbench inspect peça.stl          # analisa: componentes, sugestões, unidade
    meshbench init peça.stl             # gera a receita peça.meshbench.json
    # ... edite a receita: operações, grupos, orientação, origem ...
    meshbench apply peça.meshbench.json # aplica e exporta (out/)
    meshbench apply peça.meshbench.json --reimport  # após reexportar do CAD

## Viewport 3D (Fases 2–3)

    meshbench serve peça.stl              # abre o editor 3D no navegador
    meshbench serve receita.meshbench.json

No navegador: clique numa peça (viewport ou lista) para selecionar a família,
atribua operação/grupo/rótulo no inspetor, pré-visualize antes/depois e salve a
receita. A contagem de faces por grupo atualiza ao vivo contra o orçamento de
15k. Escala/orientação/origem interativas vêm nas fases 4–5.

### Desenvolvimento do frontend

    npm --prefix web install
    npm --prefix web run build   # builda para src/meshbench/api/static/
    npm --prefix web run dev     # dev server com proxy para :8765
    npm --prefix web test        # vitest

## Testes

    .venv\Scripts\python -m pytest              # suíte rápida (sintética)
    .venv\Scripts\python -m pytest -m slow      # regressão com as peças reais

A regressão usa os arquivos de `docs/peças exemplo/` (fora do git).

## Arquitetura

Ver `docs/ARQUITETURA-MESHPREP.md` — documento completo com o conhecimento de
domínio, os algoritmos validados e as armadilhas conhecidas.
