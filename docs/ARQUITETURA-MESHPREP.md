# MeshPrep — Editor e Conversor de Malha 3D para CAD/Móveis
## Documento de Arquitetura Completo

> **Nome:** `MeshPrep` é um nome de trabalho, genérico e trocável (alternativas:
> *MeshForge*, *TriPrep*, *MeshBench*). O app **não é específico de nenhuma empresa
> ou produto** — é uma ferramenta de uso geral para preparar qualquer malha 3D para
> uso em software de projeto (Promob e outros).
>
> **Propósito deste documento:** handoff para uma nova sessão/projeto. Contém todo o
> contexto, aprendizado e algoritmos validados de uma sessão anterior onde arquivos
> foram convertidos manualmente, com scripts ad-hoc. Quem ler isto deve conseguir
> construir o app sem redescobrir nada.

---

# 1. Filosofia do Produto

## 1.1 O problema
Malhas 3D exportadas de CAD (SolidWorks, Rhino, Inventor…) quase nunca entram
"prontas" em software de projeto de móveis. Os problemas recorrentes:

1. **Peso.** Exportações cruas trazem 200k–500k triângulos. O software-alvo trava ou
   recusa. Detalhes invisíveis (pontos de solda, roscas, gaiolas de esfera de
   corrediça) consomem a maior parte das faces.
2. **Orientação errada.** Cada CAD usa uma convenção de eixos; o alvo usa outra. A peça
   entra deitada, de lado ou de cabeça para baixo.
3. **Origem errada.** A peça vem com offset herdado de uma montagem maior e "flutua"
   longe do ponto zero, em vez de estar ancorada num canto útil.
4. **Escala errada.** O arquivo vem em polegadas e o alvo assume milímetros (ou o
   contrário). A peça entra 25,4× maior ou menor.
5. **Peças que precisam ser separadas.** Para animar a abertura de uma gaveta, o alvo
   precisa de dois arquivos: a parte fixa e a parte móvel — com origens coerentes.

## 1.2 O princípio central: **controle manual total**

> **Nada é automático e irreversível. Tudo é sugerido, visualizado e editável.**

Numa sessão anterior, todos esses problemas foram resolvidos via scripts Python. Funcionou,
mas foi frágil, e a maior fonte de erro foi **o algoritmo tentando adivinhar o que era cada
peça**. Formatos de malha como STL **não carregam nomes nem cores** — só triângulos nus.
O software não tem como saber que aquele componente é uma corrediça e aquele outro é um
ponto de solda. **O usuário sabe, instantaneamente.**

Portanto:
- A heurística geométrica existe, mas só para **pré-preencher sugestões**.
- O usuário **clica na peça e diz o que ela é** e o que fazer com ela.
- Toda transformação (escala, rotação, origem) é **interativa, com preview e desfazer**.
- Toda operação de malha expõe **todos os seus parâmetros**.

---

# 2. Escopo: o que o app faz

| Categoria | Capacidades |
|---|---|
| **Importar** | STL (ASCII/binário), DXF (3DFACE), OBJ, PLY, 3MF, VRML |
| **Analisar** | Split em componentes conectados; agrupar peças idênticas; medir bbox, volume, contagem de faces; detectar unidades prováveis |
| **Escalar** | Conversão de unidades (pol↔mm↔cm↔m); fator uniforme; fator por eixo; "escalar para caber" numa dimensão-alvo |
| **Simplificar** | Remover; reconstruir arame como tubo; re-extrudar perfil; decimação quádrica; convex hull; manter |
| **Transformar** | Remap de eixos (presets); rotação livre + snap de 90°; espelho por eixo; translação |
| **Origem** | Ancorar em canto/centro do bbox; snapar num vértice/aresta/face clicada; coordenada numérica; origem comum entre grupos ou por grupo |
| **Agrupar** | N grupos nomeados → N arquivos de saída (para animação: fixo/móvel) |
| **Exportar** | DXF R12 (3DFACE) — alvo principal; também STL/OBJ para outros usos |
| **Reproduzir** | Salvar a "receita" em JSON, versionável no git; re-importar o source e reaplicar tudo |

---

# 3. Conhecimento de Domínio (descoberto empiricamente — não redescubra)

## 3.1 O que o Promob aceita
- **DXF 3D** com entidades **`3DFACE`**, versão **R12 / AC1009**. Validado.
- Cada `3DFACE` é um quad de 4 vértices; para triângulo, repete-se o 4º vértice = 3º.
- Não precisa de blocos, layers ou hierarquia — malha solta no modelspace funciona.
- Campo na UI do Promob: `Editor de Módulos > aba Desenho > Arquivo 3D`.
- O Promob mostra a origem como um **quadradinho vermelho**.

## 3.2 Convenção de eixos (A ARMADILHA PRINCIPAL)
Um CAD de origem comum guarda:
- `Y` = altura real
- `Z` = profundidade real (**frequentemente com offset grande** herdado de montagem —
  ex.: Z indo de 961 a 1418 em vez de 0 a 457)

O Promob espera:
- `Z` = **altura** (para cima) · `Y` = **profundidade** · `X` = **largura**

**Preset validado (`cad_to_promob`):**
```
nx = x        # largura
ny = z        # profundidade real (Z do CAD) -> Y
nz = y        # altura real (Y do CAD) -> Z (para cima)
```
…seguido de zerar os mínimos (mata o offset da montagem).

> **Nunca hardcodar.** O STL do SolidWorks pode vir em qualquer orientação. Isto é um
> **preset selecionável**, e o usuário confirma olhando o preview.

## 3.3 Orçamento de faces (empírico)
- 455k faces → o Promob não aceita / trava.
- ~14k faces → funciona bem.
- ~2k–8k faces → ótimo.
- **Meta: manter cada arquivo de saída abaixo de ~15k faces.** Mostrar isso na UI como
  um "orçamento" com semáforo.

---

# 4. A Pilha de Transformação (ORDEM IMPORTA)

Esta é a espinha dorsal do motor. A ordem **não é negociável** — foi definida assim
porque cada etapa depende da anterior.

```
 1. IMPORT            lê o arquivo → uma malha bruta
 2. UNITS / SCALE     normaliza para mm  ← FAZER PRIMEIRO
 3. SPLIT             separa em componentes conectados; agrupa idênticos
 4. OPS (por peça)    remove / tube / reextrude / decimate / hull / keep
 5. GROUP             junta componentes em grupos nomeados (arquivos de saída)
 6. ORIENT            remap de eixos → rotação → espelho
 7. ORIGIN            ancora o ponto zero  ← FAZER POR ÚLTIMO
 8. EXPORT            um arquivo por grupo
```

**Por que a escala vem primeiro:** vários parâmetros das operações são em **milímetros
absolutos** (`bin_mm=3.0` do tubo, `tol=0.4` da re-extrusão, limiares da classificação
automática). Se a malha estiver em polegadas, esses números viram lixo. **Normalize para
mm antes de qualquer análise.**

**Por que a origem vem por último:** a âncora ("canto inferior do fundo") só faz sentido
depois que a peça já está na orientação final. Ancorar antes e girar depois joga a origem
para o lugar errado — erro cometido na sessão anterior.

---

# 5. Etapa 2 — Unidades e Escala (o problema polegada/mm)

## 5.1 O problema real
Arquivos vêm em polegadas e o alvo assume mm (ou converte errado). A peça entra 25,4×
fora de escala. STL, em particular, **não armazena unidade nenhuma** — é só um monte de
números. Não há como saber com certeza.

## 5.2 Detecção heurística (sugestão, nunca imposição)
Ao importar, o app calcula o bbox e **sugere** a unidade:

| Maior dimensão do bbox | Sugestão | Raciocínio |
|---|---|---|
| 100 – 5000 | **mm** (provável) | Faixa típica de um componente de móvel em mm |
| 5 – 100 | **polegadas ou cm** (ambíguo) | Pode ser 50mm ou 50" — **perguntar** |
| 0.1 – 5 | **metros** (provável) | Um móvel de 0,45 m |
| > 5000 | suspeito | Talvez já esteja em mm mas seja um objeto grande |

A UI mostra: *"Maior dimensão: 1000.0. Se for **mm**, a peça tem 1,00 m. Se for
**polegadas**, tem 25,40 m."* — e deixa o usuário escolher. **Sempre mostrar o resultado
em unidade humana**, para o erro saltar aos olhos.

## 5.3 Modos de escala (todos disponíveis na UI)
1. **Conversão de unidade** — dropdown "de → para": `pol → mm` (×25,4), `cm → mm` (×10),
   `m → mm` (×1000), `mm → mm` (×1), e o inverso.
2. **Fator uniforme** — campo numérico livre (ex.: `0.5`, `2.0`).
3. **Fator por eixo** — `sx`, `sy`, `sz` independentes (para corrigir distorções raras).
   ⚠️ Avisar que escala não-uniforme distorce raios de tubo/perfil.
4. **Escalar para dimensão-alvo** — o mais útil na prática: *"quero que a largura seja
   exatamente 450 mm"* → o app calcula o fator e aplica uniformemente.
   Isto resolve o caso real: o usuário sabe a dimensão do produto pelo desenho técnico.

## 5.4 Validador
Após a escala, mostrar sempre `Largura × Altura × Profundidade` em mm, grande e visível.
Se alguma dimensão for absurda (< 1 mm ou > 5000 mm), destacar em vermelho.

---

# 6. Etapa 4 — Operações de Malha (o motor)

Cada operação abaixo foi **desenvolvida, testada e validada visualmente**. O código
completo está no **Anexo A**. Todos os parâmetros ficam **expostos na UI**.

## 6.1 Taxonomia de peças (usada só para SUGERIR)

| Tipo | Como reconhecer | Operação | Redução típica |
|---|---|---|---|
| **Ponto de solda** | Esfera, bbox ~cúbica pequena, muitas faces | `remove` | 5.852 → 0 |
| **Arame / haste redonda** | Tubo redondo curvo (hairpin) | `tube` | 4.978 → 448 |
| **Perfil / trilho / corrediça** | Prismático, parede fina, seção **aberta**, com furos | `reextrude` | 4.866 → 64 |
| **Frame / moldura** | Anel com vão central real | `decimate` | 7.380 → ~200 |
| **Ferragem pequena maciça** | Bucha, clipe, tampa, braçadeira | `hull` | 640 → ~200 |
| **Chapa interna escondida** | Fina, dentro de outra peça | `remove` | 1.724 → 0 |

## 6.2 As operações

### `keep`
Passa direto, intacta.

### `remove`
Descarta. Para solda, peças internas invisíveis, ferragens que o alvo já tem na biblioteca.

### `decimate` — decimação quádrica
`trimesh.simplify_quadric_decimation(face_count=N)`.
**Parâmetros na UI:** alvo de faces (slider absoluto **ou** % do original).
**Use quando:** a peça tem topologia que precisa ser preservada (um frame com vão central).
**NÃO use em:** arame curvo (destrói as pontas — ver abaixo).

### `tube` — reconstrução de arame como tubo low-poly
**Por que existe:** a decimação quádrica **destrói as pontas curvas** do arame, virando um
"leque" de triângulos bagunçado. O usuário reclamou explicitamente disso.

**Como funciona:**
1. Extrai a **linha de centro** por **distância geodésica**: monta o grafo das arestas,
   roda Dijkstra a partir de um extremo, agrupa vértices em "anéis" por faixa de distância,
   tira o centroide de cada anel.
   *Robusto até em curvas em U de 180°* — fatiar por plano falharia ali (o plano corta as
   duas pernas do U e o centroide sai no vazio).
2. Estima o raio (média da distância dos vértices do anel ao centroide).
3. Varre um círculo de N lados ao longo da linha usando **parallel transport frames**
   (evita torção do perfil ao longo da curva).

**Parâmetros na UI:** nº de lados do círculo (default 8), passo da linha de centro
(`bin_mm`, default 3.0), raio (auto-detectado, mas **sobrescrevível**).

### `reextrude` — re-extrusão de perfil prismático
**Por que existe:** `convex_hull` **fecha o perfil C aberto**, virando um bloco maciço.
O usuário rejeitou isso explicitamente: *"não era pra ficar uma peça fechada, era apenas
para retirar os furos e tentar deixar mais plano, mas mantendo o formato bruto"*.

**Como funciona:**
1. Detecta o eixo de extrusão (maior dimensão do bbox) — **sobrescrevível na UI**.
2. Fatia perpendicular ao eixo em N posições e **escolhe a fatia de MAIOR ÁREA** — essa é
   a seção limpa, sem furo/rasgo passando.
3. Simplifica o polígono da seção (Shapely `.simplify(tol)`).
4. Re-extruda ao longo de todo o comprimento, com tampas trianguladas.

**Resultado:** tira os furos, achata as faces, **mantém o perfil aberto**.
**Parâmetros na UI:** eixo de extrusão, nº de fatias de teste, tolerância de simplificação
do polígono (slider com preview da seção 2D — muito útil).

### `hull` — convex hull
Para ferragens pequenas e maciças.
⚠️ **Validador obrigatório:** se aplicado a uma peça detectada como perfil aberto, a UI
**deve avisar**: *"isto vai fechar o perfil"*. Foi um erro real cometido.

---

# 7. Etapa 6 — Orientação (remap, rotação, espelho)

## 7.1 Remap de eixos
Dropdown de presets, aplicado à malha inteira:
- `identidade` — não mexe
- `cad_to_promob` — `(x, z, y)` — o validado
- `z_up ↔ y_up` — as duas conversões clássicas
- `custom` — o usuário escolhe a permutação e o sinal de cada eixo (ex.: `x, -z, y`)

## 7.2 Rotação (o que o usuário pediu)
**Dois modos, ambos disponíveis:**

1. **Snap de 90°** — seis botões (`X+90 X-90 Y+90 Y-90 Z+90 Z-90`), com preview imediato.
   **Este deve ser o caminho padrão.** Na sessão anterior, os erros de orientação vieram
   de tentar raciocinar o ângulo em vez de olhar o resultado. Clicar e ver resolve.
2. **Rotação livre** — gizmo de rotação no viewport + campos numéricos (`rx, ry, rz` em
   graus, ordem XYZ explícita). Para os casos em que 90° não basta.

**Requisitos:**
- Preview em tempo real.
- **Desfazer/refazer** (a rotação é a operação mais tentativa-e-erro de todas).
- Mostrar sempre o bbox resultante em mm, para o usuário conferir contra o desenho técnico.

## 7.3 Espelho
Botões `Espelhar X / Y / Z`. Necessário para peças "direita/esquerda".
⚠️ Espelhar inverte a orientação das faces (normais) — o app deve **corrigir o winding**
automaticamente (`mesh.invert()`), senão a peça renderiza preta/pelo avesso.

> **Nota (2026-07):** no trimesh >=4.x o apply_scale/apply_transform já corrige o winding em
> transformações de determinante negativo — NÃO chamar invert() depois (flip duplo). Ver mirror.py.

---

# 8. Etapa 7 — Origem (o que o usuário pediu)

O ponto mais sensível de todos, e onde mais se perdeu tempo na sessão anterior.

## 8.1 Modos de ancoragem (todos na UI)
1. **Canto do bbox** — grid com os **8 cantos** + centro + centros de face. Clicar num
   deles ancora a origem ali. O caso mais comum: *canto inferior do fundo*.
2. **Snap em geometria** — o usuário **clica num vértice / aresta / face no viewport** e
   a origem vai exatamente para lá. Essencial: o "canto da peça" que importa nem sempre é
   o canto do bbox (pode ser o canto do frame, com um clipe sobressaindo além dele).
3. **Coordenada numérica** — campos `X, Y, Z` para digitar direto.
4. **Referência a um componente** — "ancorar no canto inferior-fundo **da peça X**".
   Isto resolve o caso real em que o bbox era definido por uma peça e o canto que
   interessava era de outra.

## 8.2 Origem comum vs. por grupo (CRÍTICO para multi-arquivo)
Quando o projeto exporta vários grupos (ex.: parte fixa + parte móvel de uma gaveta):

- **`common`** — todos os grupos compartilham o **mesmo referencial** (mínimo global).
  Ao carregar os dois arquivos no alvo, eles **caem encaixados sozinhos**. *Foi a escolha
  do usuário para o calceiro.*
- **`per_group`** — cada arquivo zera no seu próprio canto. Origem limpa em cada um, mas
  o usuário posiciona manualmente no alvo.

**A UI deve explicar a troca em uma frase**, porque a consequência não é óbvia e o usuário
precisa decidir com conhecimento de causa.

## 8.3 Validador de origem
- Marcador visual (quadrado vermelho, igual ao Promob).
- Mostrar numericamente a **distância da origem até a geometria mais próxima**.
- Se passar de um limiar (ex.: 50 mm), avisar: **"origem flutuando"** — foi exatamente
  a reclamação real do usuário no Promob.

---

# 9. Arquitetura Técnica

## 9.1 Camadas
```
┌──────────────────────────────────────────────────────────┐
│  UI (browser) — Three.js viewport + painéis              │
│  seleção · operações · escala · rotação · origem · export│
└────────────────────────┬─────────────────────────────────┘
                         │ HTTP/JSON + geometria
┌────────────────────────▼─────────────────────────────────┐
│  API (FastAPI)                                            │
└────────────────────────┬─────────────────────────────────┘
┌────────────────────────▼─────────────────────────────────┐
│  CORE (Python puro — testável, scriptável, sem UI)        │
│   io/         readers (STL/DXF/OBJ/PLY) · writers (DXF)   │
│   analyze/    split · agrupamento · classificação · units │
│   ops/        remove · tube · reextrude · decimate · hull  │
│   transform/  scale · axes · rotate · mirror · origin      │
│   pipeline.py orquestra a pilha da §4                     │
│   project.py  modelo de dados + JSON                      │
└──────────────────────────────────────────────────────────┘
```

## 9.2 Stack
**Backend:** Python 3.11+ · `trimesh` · `numpy` · `scipy` (Dijkstra) ·
`shapely` + `mapbox_earcut` + `rtree` (seções e triangulação) · `ezdxf` (DXF R12) ·
`fastapi` + `uvicorn` · `pytest`

**Frontend:** **Three.js** (viewport, raycast para seleção, `TransformControls` para o
gizmo de rotação/origem) · React + Vite (recomendado) ou JS vanilla

**Rodar:** `python -m meshprep` → sobe uvicorn e abre `localhost:8765`
**Empacotar (depois):** PyInstaller → `.exe`

> Alternativa considerada: desktop nativo (PySide6 + VTK). Evita servidor, mas o
> desenvolvimento de UI é bem mais lento e o viewport do Three.js é mais flexível —
> em especial os gizmos de transformação, que aqui são centrais. **Recomendo a web local.**

---

# 10. Modelo de Dados — `projeto.meshprep.json`

Reprodutível, diffável, versionável no git.

```jsonc
{
  "version": 1,
  "name": "RM-416-cava",
  "source": {
    "path": "source/RM-416.STL",
    "sha256": "…",                 // detecta se o source mudou
    "detected_units": "mm",        // heurística
    "units": "mm"                  // o que o USUÁRIO confirmou
  },

  "scale": {
    "mode": "unit_convert",        // unit_convert | uniform | per_axis | fit_dimension
    "from_unit": "in", "to_unit": "mm",
    "factor": [1, 1, 1],           // resultante, sempre gravado
    "fit": null                    // ex.: { "axis": "x", "target_mm": 450 }
  },

  "components": [
    {
      "id": "c0",
      "signature": "f4978:v2491:b[4,182,321]",  // reidentificação após re-import
      "instances": 12,                          // peças idênticas agrupadas
      "face_count": 4978,
      "bbox": [[0,0,0],[4,182,321]],
      "auto_class": "wire_rod",                 // sugestão da heurística
      "user_label": "hastes",                   // o que o USUÁRIO disse que é
      "operation": { "type": "tube",
                     "params": { "sides": 8, "bin_mm": 3.0, "radius": null } },
      "group": "movel"
    }
  ],

  "groups": [
    { "name": "fixa",  "role": "fixed"  },
    { "name": "movel", "role": "moving" }
  ],

  "orient": {
    "axis_remap": "cad_to_promob",   // identidade | cad_to_promob | custom
    "custom_remap": null,            // ex.: ["x", "-z", "y"]
    "rotations": [                   // aplicadas em ordem
      { "axis": "z", "deg": 90 },
      { "axis": "z", "deg": 180 }
    ],
    "mirror": []                     // ex.: ["x"]
  },

  "origin": {
    "mode": "common",                // common | per_group
    "anchor": "bbox_min",            // bbox_min | bbox_corner_N | center | feature | custom
    "feature_ref": null,             // id do componente de referência
    "snap_point": null,              // [x,y,z] escolhido clicando no viewport
    "offset": [0, 0, 0]
  },

  "export": {
    "format": "dxf_r12",             // dxf_r12 | stl | obj
    "out_dir": "out/",
    "naming": "{project}_{group}.dxf"
  }
}
```

## 10.1 IDs estáveis (essencial no uso real)
O usuário vai **ajustar o modelo no CAD e reexportar** várias vezes. Se os IDs mudarem,
todo o trabalho de classificação se perde.

**Solução:** assinatura geométrica = `(face_count, vertex_count, bbox arredondado,
volume arredondado)`. No re-import, casa componentes por assinatura e **preserva as
escolhas do usuário**. O que não casar entra como "novo — revisar", destacado na UI.

---

# 11. UI / UX

## 11.1 Layout
```
┌───────────┬───────────────────────────────┬────────────────┐
│  PEÇAS    │        VIEWPORT 3D             │   INSPETOR     │
│           │                                │                │
│ ▸ Fixa    │   malha colorida por grupo     │  Operação:     │
│   ☑ 2× perfil                              │   ( ) manter   │
│   ☑ 2× metalon                             │   (•) tubo     │
│           │   ⊕ origem (quadrado vermelho) │   ( ) re-extr. │
│ ▸ Móvel   │   gizmo de rotação             │   ( ) decimar  │
│   ☑ 12× haste                              │   ( ) hull     │
│   ☑ 1× frame                               │   ( ) remover  │
│           │   eixos X/Y/Z + régua          │                │
│ ▸ Removidas│                               │  parâmetros…   │
│   ☑ 64× solda                              │  [slider]      │
│           │                                │                │
│ ▸ Sem grupo│                               │  Grupo: [▾]    │
│   ☐ 2× clipe   ⚠                           │  Faces: 4978→448│
├───────────┴────────────────────────────────┴────────────────┤
│ ESCALA  [pol→mm ▾] [fator: 1.0] [ajustar largura p/: 450mm] │
│         → 450.0 × 234.0 × 457.3 mm                          │
│ ORIENTA [preset ▾] [X±90][Y±90][Z±90] [espelhar X|Y|Z] ↶ ↷  │
│ ORIGEM  (•)comum ( )por grupo  âncora:[canto inf-fundo ▾]   │
│         [snapar clicando na peça]   dist. p/ peça: 3.2mm ✓  │
│ TOTAL   fixa 1.520 f │ móvel 6.538 f   ✓         [EXPORTAR] │
└─────────────────────────────────────────────────────────────┘
```

## 11.2 Interações essenciais
**Seleção**
- Clicar no viewport (raycast) **ou** na lista.
- Peças idênticas repetidas aparecem **numa linha só**: *"12× haste (4.978 f cada)"*.
  Selecionar aplica a operação nas 12 de uma vez. *Isto foi crucial: 64 esferas de solda
  idênticas, 12 hastes idênticas.*
- Multi-seleção (Ctrl/Shift) · **Isolar** · **Ocultar** (para achar peças escondidas
  dentro de outras).

**Preview de operação:** toggle antes/depois no viewport; contagem de faces ao vivo.

**Desfazer/refazer global** — obrigatório. Rotação e origem são tentativa-e-erro.

**Validadores (semáforos na UI):**
- ⚠ Componente **sem grupo** e não removido → *"esta peça vai sumir do resultado"*.
  (Erro real: o metalon sumiu dos dois arquivos numa rodada.)
- ⚠ `hull` em perfil aberto → *"isto vai fechar o perfil"*.
- ⚠ Origem a > 50 mm da geometria → *"origem flutuando"*.
- ⚠ Grupo acima de 15k faces → *"pode não abrir no Promob"*.
- ⚠ Dimensão final absurda (< 1 mm ou > 5 m) → *"confira a unidade"*.

## 11.3 Fluxo típico
1. Arrasta o arquivo. O app mostra o bbox e **pergunta a unidade** se for ambíguo.
2. Confere/ajusta a escala (ou usa "ajustar largura para 450 mm").
3. Vê a lista de peças com operações sugeridas; clica e corrige o que for preciso.
4. Atribui grupos (fixa/móvel) — ou deixa tudo num grupo só.
5. Orienta com os botões de 90° até ficar certo no preview.
6. Ancora a origem (canto do bbox ou clicando na peça).
7. Exporta. Testa no alvo. Se precisar, volta, ajusta, re-exporta — **em segundos**.
8. Salva o `.meshprep.json` junto no git.

---

# 12. Estrutura de Arquivos

```
meshprep/
├── README.md
├── ARQUITETURA.md                 ← este documento
├── pyproject.toml
│
├── src/meshprep/
│   ├── __main__.py                # python -m meshprep
│   ├── core/
│   │   ├── io/
│   │   │   ├── readers.py         # STL, DXF(3DFACE), OBJ, PLY, 3MF
│   │   │   └── writers.py         # DXF R12 3DFACE, STL, OBJ
│   │   ├── analyze/
│   │   │   ├── components.py      # split, merge_vertices, assinatura, agrupamento
│   │   │   ├── classify.py        # heurísticas (só SUGEREM)
│   │   │   └── units.py           # detecção heurística de unidade
│   │   ├── ops/
│   │   │   ├── tube.py            # centerline geodésica + parallel transport
│   │   │   ├── reextrude.py       # seção de maior área + simplify + extrude
│   │   │   ├── decimate.py
│   │   │   ├── hull.py
│   │   │   └── registry.py
│   │   ├── transform/
│   │   │   ├── scale.py           # unidades, uniforme, por eixo, fit-to-dimension
│   │   │   ├── axes.py            # presets de remap
│   │   │   ├── rotate.py          # 90° snap + livre
│   │   │   ├── mirror.py          # + correção de winding
│   │   │   └── origin.py          # âncoras, snap, comum vs por-grupo
│   │   ├── pipeline.py            # a pilha da §4
│   │   └── project.py             # modelo de dados + JSON
│   ├── api/
│   │   ├── server.py
│   │   └── routes.py
│   └── web/
│       ├── index.html
│       ├── main.js                # Three.js
│       └── style.css
│
├── tests/
│   ├── fixtures/                  # malhas pequenas + os 3 produtos de regressão
│   ├── test_scale_units.py
│   ├── test_ops_tube.py
│   ├── test_ops_reextrude.py      # garante que o perfil C continua ABERTO
│   ├── test_transform_origin.py
│   └── test_roundtrip_dxf.py
│
└── examples/
    └── *.meshprep.json            # receitas prontas
```

---

# 13. API

```
POST  /api/project                 cria projeto de um upload
GET   /api/project                 estado (componentes, grupos, transform, escala)
GET   /api/project/geometry        malha p/ o viewport, já processada, colorida por grupo
PATCH /api/component/{id}          operação · grupo · label
PATCH /api/scale                   unidade · fator · fit-to-dimension
PATCH /api/orient                  remap · rotações · espelho
PATCH /api/origin                  modo · âncora · snap · offset
POST  /api/preview/{id}            malha antes/depois de uma operação
POST  /api/export                  gera arquivos; retorna caminhos + faces
POST  /api/project/save|load       .meshprep.json
POST  /api/project/reimport        re-lê o source, re-casa por assinatura
```
Performance: manter as malhas em memória (um projeto por vez). Se o viewport receber
> ~200k triângulos, mandar uma versão decimada só para exibição.

---

# 14. Roadmap

| Fase | Entrega | Critério de aceite |
|---|---|---|
| **1** | **Motor** (`core/`) + CLI, sem UI | Reproduzir os 3 produtos já convertidos (regressão de ouro) |
| **2** | Viewport read-only (FastAPI + Three.js) | Malha aparece, componentes coloridos, lista lateral, marcador de origem |
| **3** | Seleção + operações + preview | Clicar, atribuir operação/grupo, ver faces ao vivo |
| **4** | **Escala e unidades** | Detecção, conversão, fit-to-dimension, validador |
| **5** | **Rotação + espelho + origem interativa** | Gizmo, snap de 90°, snap de origem por clique, desfazer |
| **6** | Export + projeto JSON + re-import | Salvar/abrir receita; re-importar preservando escolhas |
| **7** | Extras | Presets por família de produto; batch; `.exe` |

---

# 15. Armadilhas Conhecidas (aprendidas na marra — leia antes de codar)

| Armadilha | O que acontece | Como evitar |
|---|---|---|
| `convex_hull` em perfil C | Fecha o perfil, vira bloco maciço | Só usar hull em peças maciças. **Avisar na UI.** |
| Decimação quádrica em arame | Destrói as pontas curvas (vira leque de triângulos) | Usar `tube` (linha de centro) |
| Fatiar por plano numa curva U | O plano corta as duas pernas → centroide no vazio | Usar distância **geodésica** (Dijkstra) |
| Fatiar a seção num rasgo | A seção sai com furo e a re-extrusão sai errada | Testar N fatias, pegar a de **maior área** |
| Espelhar sem corrigir winding | Faces invertidas, peça renderiza pelo avesso | `mesh.invert()` após espelhar [nota (2026-07): no trimesh >=4.x o apply_scale/apply_transform já corrige o winding sozinho — NÃO chamar invert() depois (flip duplo); ver mirror.py] |
| Origem antes de orientar | A âncora vai para o lugar errado depois da rotação | **Origem é sempre a ÚLTIMA etapa** |
| Origem por peça em conjunto | As partes não encaixam no alvo | Usar **origem comum** para grupos que se encaixam |
| Escala depois das operações | Parâmetros em mm (`bin_mm`, `tol`) viram lixo | **Escala é sempre a PRIMEIRA etapa** |
| Girar "no raciocínio" | Peça entra espelhada/virada | Botões de 90° **com preview**. Ver > deduzir. |
| Alinhar pela referência errada | Ajustei a corrediça (5 mm) e desalinhei o frame do fundo | Deixar o **usuário escolher** a feature de referência |
| Assumir que o STL tem peças | STL não tem nomes nem cores | Componentes conectados + **seleção humana** |
| Esquecer peça num bucket | Uma peça sumiu dos dois arquivos de saída | Validador: **toda peça precisa ter grupo ou estar marcada como removida** |
| Esquecer `merge_vertices()` | O `split()` não acha os componentes | Sempre `merge_vertices()` após ler |

---

# ANEXO A — Algoritmos Validados

> Todo este código **rodou e foi validado visualmente**. Portar para `core/`.

## A.1 Ler DXF 3DFACE → trimesh
```python
import ezdxf, numpy as np, trimesh

def read_dxf_3dface(path):
    doc = ezdxf.readfile(path)
    verts, tris = [], []
    for f in doc.modelspace().query('3DFACE'):
        p = [f.dxf.vtx0, f.dxf.vtx1, f.dxf.vtx2, f.dxf.vtx3]
        base = len(verts)
        is_quad = (p[2] != p[3])
        for pp in (p[:4] if is_quad else p[:3]):
            verts.append((pp[0], pp[1], pp[2]))
        if is_quad:
            tris += [(base, base+1, base+2), (base, base+2, base+3)]
        else:
            tris.append((base, base+1, base+2))
    m = trimesh.Trimesh(vertices=np.array(verts), faces=np.array(tris), process=False)
    m.merge_vertices()          # ESSENCIAL — sem isso o split() não acha componentes
    return m
```

## A.2 Escrever DXF R12 3DFACE
```python
def write_dxf_r12(meshes, path):
    doc = ezdxf.new(dxfversion='AC1009')
    msp = doc.modelspace()
    for m in meshes:
        v = m.vertices
        for tri in m.faces:
            a, b, c = v[tri[0]], v[tri[1]], v[tri[2]]
            msp.add_3dface([tuple(a), tuple(b), tuple(c), tuple(c)])
    doc.saveas(path)
```

## A.3 Split + agrupamento de peças idênticas
```python
from collections import defaultdict

def signature(c):
    d = np.round(c.bounds[1] - c.bounds[0], 2)
    return (len(c.faces), len(c.vertices), tuple(d))

def split_components(mesh):
    groups = defaultdict(list)
    for c in mesh.split(only_watertight=False):
        groups[signature(c)].append(c)
    return groups
```
> Na prática, agrupar só por `len(c.faces)` já separou perfeitamente as famílias
> (64 esferas de 5.852 f, 12 hastes de 4.978 f, 2 corrediças de 4.866 f…).

## A.4 Escala e unidades
```python
UNIT_MM = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4, "ft": 304.8}

def scale_to_mm(mesh, from_unit):
    return scale_uniform(mesh, UNIT_MM[from_unit])

def scale_uniform(mesh, f):
    m = mesh.copy(); m.apply_scale(f); return m

def scale_per_axis(mesh, sx, sy, sz):
    m = mesh.copy(); m.apply_scale([sx, sy, sz]); return m

def fit_dimension(mesh, axis, target_mm):
    """Escala uniforme para que a dimensão `axis` fique exatamente target_mm."""
    i = "xyz".index(axis)
    cur = mesh.bounds[1][i] - mesh.bounds[0][i]
    if cur <= 0:
        raise ValueError("dimensão nula")
    return scale_uniform(mesh, target_mm / cur)

def guess_unit(mesh):
    d = float(np.max(mesh.bounds[1] - mesh.bounds[0]))
    if d > 5000:  return "mm", "suspeito: muito grande"
    if d >= 100:  return "mm", "provável"
    if d >= 5:    return None, "ambíguo: pode ser polegada ou cm — perguntar"
    return "m", "provável"
```

## A.5 `tube` — reconstrução de arame
```python
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

def extract_centerline(mesh, bin_mm=3.0):
    v = mesh.vertices
    e = mesh.edges_unique
    el = np.linalg.norm(v[e[:, 0]] - v[e[:, 1]], axis=1)
    n = len(v)
    W = csr_matrix((np.concatenate([el, el]),
                    (np.concatenate([e[:, 0], e[:, 1]]),
                     np.concatenate([e[:, 1], e[:, 0]]))), shape=(n, n))
    c0 = v - v.mean(0)
    _, vec = np.linalg.eigh(np.cov(c0.T))
    t = c0 @ vec[:, -1]
    g = dijkstra(W, indices=int(np.argmax(t)), directed=False)
    g[~np.isfinite(g)] = g[np.isfinite(g)].max()
    nb = max(4, int(g.max() / bin_mm))
    bins = np.linspace(0, g.max(), nb + 1)
    idx = np.digitize(g, bins) - 1
    cl, rad = [], []
    for b in range(nb):
        m = idx == b
        if m.sum() < 3:
            continue
        cen = v[m].mean(0)
        cl.append(cen)
        rad.append(np.linalg.norm(v[m] - cen, axis=1).mean())
    return np.array(cl), float(np.median(rad))


def tube_from_centerline(cl, radius, sides=8):
    P = np.asarray(cl)
    T = np.gradient(P, axis=0)
    T /= (np.linalg.norm(T, axis=1, keepdims=True) + 1e-9)
    ref = np.array([0, 0, 1.]) if abs(T[0, 2]) < 0.9 else np.array([0, 1., 0])
    n0 = np.cross(T[0], ref); n0 /= np.linalg.norm(n0) + 1e-9
    normals = [n0]
    for i in range(1, len(P)):                       # parallel transport (Rodrigues)
        pn = normals[-1]
        vx = np.cross(T[i-1], T[i]); cs = np.dot(T[i-1], T[i])
        if np.linalg.norm(vx) < 1e-6:
            nn = pn
        else:
            vx /= np.linalg.norm(vx)
            a = np.arccos(np.clip(cs, -1, 1))
            nn = (pn*np.cos(a) + np.cross(vx, pn)*np.sin(a)
                  + vx*np.dot(vx, pn)*(1 - np.cos(a)))
        nn = nn - np.dot(nn, T[i]) * T[i]
        nn /= np.linalg.norm(nn) + 1e-9
        normals.append(nn)
    normals = np.array(normals)
    B = np.cross(T, normals)
    ang = np.linspace(0, 2*np.pi, sides, endpoint=False)
    rings = np.array([P[i] + radius*(np.cos(ang)[:, None]*normals[i]
                                     + np.sin(ang)[:, None]*B[i])
                      for i in range(len(P))])
    ns = len(P)
    V = rings.reshape(-1, 3)
    F = []
    for i in range(ns - 1):
        for j in range(sides):
            a = i*sides + j;      b = i*sides + (j+1) % sides
            c = (i+1)*sides + j;  d = (i+1)*sides + (j+1) % sides
            F += [[a, b, d], [a, d, c]]
    for ci, flip in [(0, False), (ns-1, True)]:      # tampas
        idx = len(V); V = np.vstack([V, P[ci]])
        for j in range(sides):
            a = ci*sides + j; b = ci*sides + (j+1) % sides
            F.append([idx, b, a] if flip else [idx, a, b])
    return trimesh.Trimesh(vertices=V, faces=np.array(F), process=False)
```

## A.6 `reextrude` — perfil prismático (mantém o perfil ABERTO)
```python
from shapely.ops import unary_union
from trimesh.creation import triangulate_polygon

def reextrude(mesh, axis=None, n_probe=25, tol=0.4):
    dims = mesh.bounds[1] - mesh.bounds[0]
    if axis is None:
        axis = int(np.argmax(dims))            # eixo = maior dimensão (sobrescrevível)
    normal = [0, 0, 0]; normal[axis] = 1
    amin, amax = mesh.bounds[0, axis], mesh.bounds[1, axis]

    best, best_area = None, -1
    for ap in np.linspace(amin + (amax-amin)*0.1, amax - (amax-amin)*0.1, n_probe):
        o = [0, 0, 0]; o[axis] = ap
        try:
            sec = mesh.section(plane_origin=o, plane_normal=normal)
            if sec is None:
                continue
            p2d, to3d = sec.to_2D()
            area = sum(pp.area for pp in p2d.polygons_full)
        except Exception:
            continue
        if area > best_area:                   # a fatia de MAIOR área = seção sem furo
            best_area, best = area, (p2d, to3d)
    if best is None:
        return None

    p2d, to3d = best
    geom = unary_union(list(p2d.polygons_full)).simplify(tol)
    if geom.geom_type == 'MultiPolygon':
        geom = max(geom.geoms, key=lambda g: g.area)
    v2d, fcap = triangulate_polygon(geom, engine='earcut')

    def to_world(p2):
        h = np.column_stack([p2, np.zeros(len(p2)), np.ones(len(p2))])
        return (to3d @ h.T).T[:, :3]

    other = [i for i in range(3) if i != axis]
    prof = to_world(v2d)[:, other]
    V, F = [], []

    def ring(aval, pts):
        base = len(V)
        for p in pts:
            xyz = [0., 0., 0.]
            xyz[axis] = aval; xyz[other[0]] = p[0]; xyz[other[1]] = p[1]
            V.append(xyz)
        return base

    b0 = ring(amin, prof)
    for f in fcap: F.append([b0+f[0], b0+f[2], b0+f[1]])      # tampa (winding invertido)
    b1 = ring(amax, prof)
    for f in fcap: F.append([b1+f[0], b1+f[1], b1+f[2]])      # tampa
    ext = np.array(geom.exterior.coords)[:-1]
    extw = to_world(ext)[:, other]
    ne = len(ext)
    r0 = ring(amin, extw); r1 = ring(amax, extw)
    for i in range(ne):                                       # parede lateral
        a = r0+i; b = r0+(i+1) % ne; c = r1+i; d = r1+(i+1) % ne
        F += [[a, b, d], [a, d, c]]
    return trimesh.Trimesh(vertices=np.array(V, float),
                           faces=np.array(F), process=False)
```

## A.7 Orientação e origem
```python
REMAPS = {
    "identidade":    lambda v: v,
    "cad_to_promob": lambda v: np.column_stack([v[:, 0], v[:, 2], v[:, 1]]),  # x, z, y
}

def rotate_90(v, axis, steps):
    """steps = múltiplos de +90° (CCW olhando do + do eixo)."""
    for _ in range(steps % 4):
        if axis == 'z':   v = np.column_stack([-v[:, 1],  v[:, 0],  v[:, 2]])
        elif axis == 'x': v = np.column_stack([ v[:, 0], -v[:, 2],  v[:, 1]])
        elif axis == 'y': v = np.column_stack([ v[:, 2],  v[:, 1], -v[:, 0]])
    return v

def rotate_free(mesh, rx, ry, rz):
    """Graus, ordem X→Y→Z. Para o gizmo / entrada numérica."""
    m = mesh.copy()
    for ang, ax in ((rx, [1,0,0]), (ry, [0,1,0]), (rz, [0,0,1])):
        if ang:
            m.apply_transform(trimesh.transformations.rotation_matrix(
                np.deg2rad(ang), ax))
    return m

def mirror(mesh, axis):
    m = mesh.copy()
    s = [1, 1, 1]; s["xyz".index(axis)] = -1
    m.apply_scale(s)
    m.invert()                      # CORRIGE O WINDING — senão renderiza pelo avesso
    return m
```

> **Nota (2026-07):** no trimesh >=4.x o apply_scale/apply_transform já corrige o winding em
> transformações de determinante negativo — NÃO chamar invert() depois (flip duplo). Ver mirror.py.

```python
def place_origin(verts_by_group, mode="common", anchor_point=None):
    """Executar por ÚLTIMO, após escala + orientação."""
    if anchor_point is not None:                    # snap explícito (clique no viewport)
        return {g: [v - anchor_point for v in vs] for g, vs in verts_by_group.items()}
    if mode == "common":                            # grupos encaixam entre si
        allv = np.concatenate([v for vs in verts_by_group.values() for v in vs])
        mn = allv.min(axis=0)
        return {g: [v - mn for v in vs] for g, vs in verts_by_group.items()}
    out = {}                                        # per_group
    for g, vs in verts_by_group.items():
        mn = np.concatenate(vs).min(axis=0)
        out[g] = [v - mn for v in vs]
    return out
```

---

# ANEXO B — Casos Reais de Referência (fixtures de regressão)

## B.1 Gaveta Fruteira (aramado) — `2191-0400`
455.804 `3DFACE` · 112 componentes · **64× esfera de solda (5.852 f cada) = 82% do
arquivo** · aro perimetral · arames da grade · ferragens nas pontas.
→ 14.076 faces. `remove` + `decimate` + remap de eixos + rotação 180° em Z.

## B.2 Calceiro — `3214-0400-CL-00` / `3214-0450-CL-00`
Papéis identificados **pelo usuário** (não pela heurística):

| faces | qtd | peça | operação | grupo |
|---|---|---|---|---|
| 5852 | 16/64 | esfera de solda | `remove` | — |
| 4978 | 12 | haste (arame) | `tube` | móvel |
| 7380 | 1 | frame | `decimate` | móvel |
| 4866/4800 | 2 | corrediça EXTERNA | `reextrude` | fixa |
| 2284/2236 | 2 | corrediça INTERNA | `reextrude` | móvel |
| 1012 | 2 | trilho do meio | `reextrude` | fixa |
| 948 | 2 | metalon L | `reextrude` | fixa |
| 1724 | 4 | tira fina 3 mm (escondida) | `remove` | — |
| 342/640/376/320 | 2 cada | tampa, braçadeira, clipe, bucha | `hull` | vários |

Origem: **comum** entre os grupos · rotação de 90° em Z para a corrediça ficar à esquerda.

## B.3 Perfil/cava — `RM-416.STL` (SolidWorks 2020)
**ASCII STL**, `solid RM-416` · **536 faces** · 270 vértices · watertight ·
**1 componente** · bbox `54,49 × 15,05 × 1000,0` mm (**eixo longo em Z**) ·
origem já em ~(0,0,0).
Seção transversal: **1 polígono aberto**, área 124,7 mm², **271 vértices de exterior**
(só tesselação de curvatura), **0 furos** → caso perfeito de `reextrude` (536 → ~50 faces).

**Lição:** exportar direto do CAD já resolve o peso. O trabalho do app aqui é
**escala + orientação + origem + simplificação de perfil**.

---

# ANEXO C — Exportação a partir do CAD

- **DXF/DWG do SolidWorks é 2D** (vistas/planificação). **Não serve.**
- Usar **STL** (malha pura; o `trimesh` lê nativamente). Equivalentes: VRML (`.wrl`),
  PLY, 3MF.
- **Não usar** STEP / IGES / Parasolid (`.x_t`) / ACIS (`.sat`): são BREP (sólido) e
  exigiriam um kernel CAD para tesselar.
- Nas opções do STL dá para controlar **resolução (desvio/ângulo)** — exportar grosso já
  reduz muito os triângulos na origem.
- **Dica de ouro:** para produtos que precisam ser separados (fixo/móvel), exportar
  **dois STLs** do CAD, ocultando os componentes de cada lado. Isso elimina a
  classificação geométrica — que foi a maior fonte de erro.
- Ocultar solda e peças internas escondidas **antes** de exportar economiza a etapa de
  remoção.
- ⚠️ **STL não armazena unidade.** Sempre confirmar a escala no import.
