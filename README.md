# MeshBench

[![CI](https://github.com/feliperutzenfr/meshbench/actions/workflows/ci.yml/badge.svg)](https://github.com/feliperutzenfr/meshbench/actions/workflows/ci.yml)
[![Licença: MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-blue.svg)](LICENSE)

**Prepara malhas 3D exportadas de CAD (SolidWorks, Rhino, Inventor…) para o
Promob e outros softwares de projeto de móveis** — simplifica, escala, orienta,
reancora a origem e exporta **DXF R12 (3DFACE)**, o formato que o Promob importa
sem drama.

Tudo num editor 3D local que roda no navegador, e cada sessão vira uma **receita
reproduzível** (`*.meshbench.json`) — reimportou a peça do CAD, é só reaplicar.

> **Princípio central: nada é automático e irreversível.** As heurísticas (que
> peça é essa, qual a unidade, qual operação) só *sugerem* — você olha o preview e
> decide. STL não carrega nome nem cor; quem sabe o que cada coisa é, é você.

## O problema que ele resolve

Malha de CAD quase nunca entra bem no Promob:

- **Arquivo pesado trava.** Acima de ~15k faces o Promob começa a sofrer; 455k
  faces derrubam. O ideal fica entre 2k e 8k faces por arquivo. O MeshBench
  simplifica com um **semáforo de faces** ao vivo (verde ≤ 8k, amarelo ≤ 15k,
  vermelho acima).
- **Eixos trocados.** CAD costuma ser Y-up; o Promob espera Z = altura, Y =
  profundidade, X = largura. Tem preset `CAD → Promob` selecionável (nunca
  chumbado).
- **Unidade perdida.** STL não guarda unidade. O app sugere pelo tamanho e pede
  confirmação quando está ambíguo.
- **Origem no lugar errado.** Reancora por canto/centro, com snap por clique e
  aviso de "origem flutuando".

## Recursos

- **Importa** STL, DXF, OBJ, PLY, 3MF.
- **Divide** a malha em peças (famílias de componentes) e classifica com sugestões.
- **Simplifica** com orçamento de faces por grupo (semáforo 8k/15k).
- **Escala e converte unidades** (pol/cm/m → mm), por fator ou por dimensão-alvo.
- **Orienta**: presets de eixos, giros de 90°, espelho, rotação livre e **gizmo**
  de arrasto no viewport.
- **Reancora a origem**: 8 cantos + centro, offset, snap por clique.
- **Agrupa e exporta** um arquivo por grupo em **DXF R12 (3DFACE)** para o Promob,
  ou STL/OBJ.
- **Desfazer/refazer** global de todas as edições.
- **Receita reproduzível** (`*.meshbench.json`): reimporta o CAD e re-casa as peças
  por assinatura geométrica, marcando as novas como "novo — revisar".

## Baixar (Windows, sem instalar nada)

Pegue o `.zip` mais recente em **[Releases](https://github.com/feliperutzenfr/meshbench/releases)**,
extraia e dê **duplo-clique em `MeshBench.exe`**:

1. Um diálogo nativo pede o arquivo CAD (ou uma receita `.meshbench.json`).
2. O app abre no seu navegador padrão. Feche pela janelinha "MeshBench rodando".

Também dá para **arrastar um arquivo sobre o `.exe`**. Na primeira execução o
Windows SmartScreen pode avisar "editor desconhecido" (o executável não é
assinado) — clique em **Mais informações → Executar assim mesmo**.

## Rodar a partir do código-fonte

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m meshbench serve peça.stl
```

## O editor 3D

`meshbench serve <arquivo>` abre o editor no navegador. Clique numa peça (viewport
ou lista) para selecionar a família, atribua operação/grupo/rótulo no inspetor, e
pré-visualize antes/depois. As barras seguem a **ordem do pipeline** (que não é
negociável):

```
IMPORTAR → ESCALA → dividir → OPERAÇÕES → agrupar → ORIENTA → ORIGEM → EXPORTA
```

- **ESCALA** — converte unidades e ajusta tamanho. Dimensões suspeitas (< 1 mm ou
  > 5 m) ficam em vermelho; unidade ambígua abre um banner comparando os tamanhos
  em escala humana.
- **ORIENTA** — presets de eixos (ex.: CAD → Promob), giros de 90° com preview
  imediato, espelho e rotação livre em graus (ordem X→Y→Z).
- **ORIGEM** — modo comum (arquivos caem encaixados no destino) ou por grupo,
  âncora (8 cantos + centro), offset e snap por clique. Aviso de **origem
  flutuando** acima de 50 mm.
- **EXPORTA** — um arquivo por grupo, na pasta configurável, com o semáforo de
  faces por grupo. O `{group}` no nome só é obrigatório quando há 2+ grupos.

## Linha de comando (CLI)

Para automação ou uso sem interface:

```bash
meshbench inspect peça.stl           # componentes, sugestões, unidade
meshbench init peça.stl              # gera a receita peça.meshbench.json
meshbench apply peça.meshbench.json  # aplica e exporta (out/)
meshbench apply receita.json --reimport  # após reexportar do CAD
```

## Formato de saída para o Promob

O alvo é **DXF R12 / AC1009 com entidades `3DFACE`** (malha solta em modelspace,
sem layers nem blocos). É o formato validado que o Promob importa de forma
confiável. Mantenha cada arquivo **abaixo de ~15k faces**.

## Desenvolvimento

```bash
npm --prefix web install
npm --prefix web run build   # builda para src/meshbench/api/static/
npm --prefix web run dev     # dev server com proxy para :8765
npm --prefix web test        # vitest

.venv\Scripts\python -m pytest           # suíte rápida (sintética)
.venv\Scripts\python -m pytest -m slow   # regressão com peças reais (fora do git)
```

Para regerar o executável Windows:

```bash
.venv\Scripts\python -m pip install -e ".[build]"
powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1
```

O script builda o frontend e roda o PyInstaller (`meshbench.spec`, one-dir),
gerando `dist/MeshBench/MeshBench.exe` e `dist/MeshBench-<versão>.zip`.

## Arquitetura

Ver [`docs/ARQUITETURA-MESHPREP.md`](docs/ARQUITETURA-MESHPREP.md) — documento
completo com o conhecimento de domínio, os algoritmos validados e as armadilhas
conhecidas. O stack: Python (`trimesh`, `numpy`, `scipy`, `shapely`, `ezdxf`) +
FastAPI no back-end; Three.js + React (Vite) no front-end.

## Contribuindo e sugestões

Se você usa Promob (ou outro software de projeto) e sofre com arquivos de CAD,
**suas sugestões são muito bem-vindas**. Abra uma
[issue](https://github.com/feliperutzenfr/meshbench/issues) contando o que
precisa, o que quebrou, ou que formato/ajuste faltou — casos reais são o que mais
ajudam a melhorar a ferramenta. Pull requests também são bem-vindos.

## Licença

MIT — ver [LICENSE](LICENSE). Use, modifique e distribua à vontade, inclusive
comercialmente; só mantenha o aviso de copyright.
