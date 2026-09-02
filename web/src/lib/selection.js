// Seleção de famílias na barra lateral. Lógica pura, sem React, para poder
// testar as combinações de teclado sem montar componente.

/**
 * Famílias na MESMA ordem em que a barra lateral as mostra: por grupo, depois
 * as sem grupo, depois as removidas. O shift+clique pega o intervalo visível,
 * então precisa desta ordem — não a de `state.components`.
 */
export function ordemExibicao(components, groups) {
  const nomes = groups.map((g) => g.name);
  const porGrupo = new Map(nomes.map((n) => [n, []]));
  const removidas = [];
  const semGrupo = [];
  for (const c of components) {
    if (c.operation.type === "remove") removidas.push(c);
    else if (c.group && porGrupo.has(c.group)) porGrupo.get(c.group).push(c);
    else semGrupo.push(c);
  }
  return [...nomes.flatMap((n) => porGrupo.get(n)), ...semGrupo, ...removidas];
}

/** Ids que caíram fora do resultado sem o usuário pedir (op != remover). */
export function foraDaSaida(components) {
  return components
    .filter((c) => !c.in_output && c.operation.type !== "remove")
    .map((c) => c.id);
}

/**
 * Próxima seleção a partir de um clique.
 *
 * - clique simples: substitui a seleção pelo item clicado
 * - ctrl/cmd+clique: alterna o item, preservando o resto
 * - shift+clique: seleciona o intervalo entre a âncora e o item, na ordem em
 *   que as famílias aparecem na lista (`ordem`)
 *
 * `ancora` é o último item clicado sem shift — é dela que o intervalo parte.
 * `clicado` nulo (clique no vazio do viewport) limpa a seleção.
 * Devolve { ids, ancora } para o chamador guardar.
 */
export function proximaSelecao({ ids, ancora, clicado, ordem, ctrl, shift }) {
  if (clicado == null) return { ids: [], ancora: null };
  if (shift && ancora != null) {
    const i = ordem.indexOf(ancora);
    const j = ordem.indexOf(clicado);
    if (i !== -1 && j !== -1) {
      const [de, ate] = i <= j ? [i, j] : [j, i];
      const faixa = ordem.slice(de, ate + 1);
      // ctrl+shift soma o intervalo à seleção; shift sozinho substitui
      const base = ctrl ? ids.filter((id) => !faixa.includes(id)) : [];
      return { ids: [...base, ...faixa], ancora };
    }
  }
  if (ctrl) {
    const tem = ids.includes(clicado);
    return {
      ids: tem ? ids.filter((id) => id !== clicado) : [...ids, clicado],
      ancora: clicado,
    };
  }
  return { ids: [clicado], ancora: clicado };
}
