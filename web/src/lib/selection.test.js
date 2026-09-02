import { describe, expect, it } from "vitest";
import { foraDaSaida, ordemExibicao, proximaSelecao } from "./selection.js";

const ordem = ["c1", "c2", "c3", "c4", "c5"];
const sel = (over) =>
  proximaSelecao({ ids: [], ancora: null, ordem, ctrl: false, shift: false, ...over });

describe("proximaSelecao", () => {
  it("clique simples substitui a seleção", () => {
    expect(sel({ ids: ["c1", "c2"], clicado: "c4" })).toEqual({
      ids: ["c4"],
      ancora: "c4",
    });
  });

  it("ctrl+clique acrescenta preservando o resto", () => {
    expect(sel({ ids: ["c1"], clicado: "c3", ctrl: true }).ids).toEqual(["c1", "c3"]);
  });

  it("ctrl+clique num já selecionado remove", () => {
    expect(sel({ ids: ["c1", "c3"], clicado: "c1", ctrl: true }).ids).toEqual(["c3"]);
  });

  it("shift+clique pega o intervalo a partir da âncora", () => {
    expect(sel({ ids: ["c2"], ancora: "c2", clicado: "c4", shift: true }).ids).toEqual([
      "c2",
      "c3",
      "c4",
    ]);
  });

  it("shift+clique para trás também funciona", () => {
    expect(sel({ ids: ["c4"], ancora: "c4", clicado: "c2", shift: true }).ids).toEqual([
      "c2",
      "c3",
      "c4",
    ]);
  });

  it("shift mantém a âncora, para o próximo shift partir dela", () => {
    expect(sel({ ids: ["c2"], ancora: "c2", clicado: "c5", shift: true }).ancora).toBe(
      "c2",
    );
  });

  it("ctrl+shift soma o intervalo sem duplicar", () => {
    const r = sel({
      ids: ["c1", "c3"],
      ancora: "c3",
      clicado: "c4",
      ctrl: true,
      shift: true,
    });
    expect(r.ids.slice().sort()).toEqual(["c1", "c3", "c4"]);
  });

  it("clique no vazio limpa a seleção", () => {
    expect(sel({ ids: ["c1", "c2"], ancora: "c2", clicado: null })).toEqual({
      ids: [],
      ancora: null,
    });
  });

  it("clique no vazio limpa mesmo com ctrl segurado", () => {
    expect(sel({ ids: ["c1"], clicado: null, ctrl: true }).ids).toEqual([]);
  });

  it("shift sem âncora cai no clique simples", () => {
    expect(sel({ ids: ["c1"], clicado: "c3", shift: true }).ids).toEqual(["c3"]);
  });
});

describe("foraDaSaida", () => {
  const comp = (id, in_output, type = "reextrude") => ({
    id,
    in_output,
    operation: { type },
  });

  it("pega só quem sumiu sem ter sido removido de propósito", () => {
    expect(
      foraDaSaida([
        comp("c1", true),
        comp("c2", false),
        comp("c3", false, "remove"), // removida de propósito — não é problema
        comp("c4", false),
      ]),
    ).toEqual(["c2", "c4"]);
  });

  it("devolve vazio quando está tudo na saída", () => {
    expect(foraDaSaida([comp("c1", true), comp("c2", true)])).toEqual([]);
  });
});

describe("ordemExibicao", () => {
  const c = (id, group, type = "keep") => ({ id, group, operation: { type } });

  it("agrupa como a barra lateral: grupos, sem grupo, removidas", () => {
    const comps = [
      c("c1", null, "remove"),
      c("c2", "b"),
      c("c3", null),
      c("c4", "a"),
      c("c5", "b"),
    ];
    const ids = ordemExibicao(comps, [{ name: "a" }, { name: "b" }]).map((x) => x.id);
    expect(ids).toEqual(["c4", "c2", "c5", "c3", "c1"]);
  });

  it("trata grupo inexistente como sem grupo", () => {
    const ids = ordemExibicao([c("c1", "fantasma"), c("c2", "a")], [{ name: "a" }]).map(
      (x) => x.id,
    );
    expect(ids).toEqual(["c2", "c1"]);
  });
});
