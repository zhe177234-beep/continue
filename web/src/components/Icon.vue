<script setup>
defineProps({
  name: { type: String, default: "book" },
  size: { type: Number, default: 20 },
});
const paths = {
  book: "M4 4h6a3 3 0 0 1 3 3v14a4 4 0 0 0-4-2H4z M20 4h-4a3 3 0 0 0-3 3v14a4 4 0 0 1 4-2h3z",
  chat: "M21 11a8 8 0 0 1-8 8H7l-4 3v-7a8 8 0 0 1 8-12h2a8 8 0 0 1 8 8z M8 9h8 M8 13h5",
  graph:
    "M7 6l10 0 M6 8l5 9 M18 8l-5 9 M4 3h4v5H4z M16 3h4v5h-4z M10 17h4v4h-4z",
  check:
    "M9 4H5a1 1 0 0 0-1 1v15h16V5a1 1 0 0 0-1-1h-4 M9 2h6v4H9z M8 12l3 3 5-6",
  chart: "M4 3v17h17 M8 16v-4 M13 16V8 M18 16V5",
  layout: "M3 4h18v16H3z M3 9h18 M9 9v11",
  upload: "M12 16V3 M7 8l5-5 5 5 M4 15v6h16v-6",
  file: "M6 3h8l4 4v14H6z M14 3v5h4 M9 12h6 M9 16h6",
  arrow: "M4 12h16 M14 6l6 6-6 6",
  spark: "M12 3l2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z",
  clock: "M12 3a9 9 0 1 0 .01 0 M12 7v5l3 2",
  plus: "M12 5v14 M5 12h14",
  logout: "M9 3H4v18h5 M10 12h11 M16 7l5 5-5 5",
  layers: "M12 3l10 5-10 5L2 8z M2 12l10 5 10-5 M2 16l10 5 10-5",
  shield: "M12 3l8 3v6c0 5-8 9-8 9s-8-4-8-9V6z M8 12l3 3 5-6",
  chevron: "M8 5l7 7-7 7",
  search: "M10 3a7 7 0 1 0 .01 0 M15 15l6 6",
  desktop: "M3 4h18v13H3z M12 17v4 M8 21h8",
  mobile: "M7 2h10v20H7z M10 18h4",
  undo: "M3 10l4-4 M3 10l4 4 M3 10h11a6 6 0 0 1 6 6",
  save: "M4 3h13l3 3v15H4z M8 3v6h8V3 M8 21v-7h8v7",
  download: "M12 3v13 M7 11l5 5 5-5 M4 17v4h16v-4",
};
</script>
<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.65"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path :d="paths[name] || paths.book" />
  </svg>
</template>
