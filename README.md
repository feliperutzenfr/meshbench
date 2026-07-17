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

## Viewport 3D (Fases 2–5a)

    meshbench serve peça.stl              # abre o editor 3D no navegador
    meshbench serve receita.meshbench.json

No navegador: clique numa peça (viewport ou lista) para selecionar a família,
atribua operação/grupo/rótulo no inspetor, pré-visualize antes/depois e salve a
receita. A contagem de faces por grupo atualiza ao vivo contra o orçamento de
15k. Orientação/origem interativas (gizmos) vêm na fase 5.

### Escala e unidades (Fase 4)

A barra ESCALA converte unidades (pol/cm/m → mm), aplica fator uniforme ou por
eixo, e ajusta uma dimensão-alvo ("quero largura = 450 mm"). Quando o arquivo
tem unidade ambígua (STL não guarda unidade), um banner compara as
possibilidades em tamanho humano e pede confirmação. Dimensões suspeitas
(< 1 mm ou > 5 m) ficam em vermelho.

### Orientação e desfazer (Fase 5a)

A barra ORIENTA aplica presets de eixos (ex.: CAD → Promob), giros de 90° por
botão com preview imediato ("ver > deduzir"), espelho por eixo e rotação livre
em graus (ordem X→Y→Z). Todo o histórico de edições tem desfazer/refazer (↶ ↷).
Origem interativa e gizmo vêm na fase 5b.

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
