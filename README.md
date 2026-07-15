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

## Testes

    .venv\Scripts\python -m pytest              # suíte rápida (sintética)
    .venv\Scripts\python -m pytest -m slow      # regressão com as peças reais

A regressão usa os arquivos de `docs/peças exemplo/` (fora do git).

## Arquitetura

Ver `docs/ARQUITETURA-MESHPREP.md` — documento completo com o conhecimento de
domínio, os algoritmos validados e as armadilhas conhecidas.
