// Cores por grupo — determinísticas pela ordem de declaração dos grupos na receita.
export const GROUP_COLORS = [
  "#4e79a7",
  "#f28e2b",
  "#59a14f",
  "#e15759",
  "#b07aa1",
  "#76b7b2",
  "#edc948",
  "#ff9da7",
];

export function groupColor(groupName, groupNames) {
  const i = groupNames.indexOf(groupName);
  return GROUP_COLORS[(i >= 0 ? i : 0) % GROUP_COLORS.length];
}
