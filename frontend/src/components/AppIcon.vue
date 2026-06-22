<template>
  <span :class="iconClass" aria-hidden="true">
    <svg
      class="app-icon__glyph"
      viewBox="0 0 24 24"
      focusable="false"
      v-html="svgMarkup"
    ></svg>
  </span>
</template>

<script setup lang="ts">
import { computed } from "vue";

import { appIconSvg, type AppIconName } from "@/components/appIcons";

const props = withDefaults(
  defineProps<{
    name: AppIconName;
    variant?: "line" | "tile" | "badge";
    tone?: "blue" | "cyan" | "green" | "amber" | "red" | "slate";
  }>(),
  {
    variant: "line",
    tone: "blue",
  },
);

const svgMarkup = computed(() => appIconSvg[props.name]);
const iconClass = computed(() => [
  "app-icon",
  `app-icon--${props.variant}`,
  `app-icon--${props.tone}`,
  `app-icon--${props.name}`,
]);
</script>

<style scoped>
.app-icon {
  --icon-top: #3ba3e8;
  --icon-mid: #1d78c1;
  --icon-bottom: #0d528b;
  --icon-ring: rgba(102, 178, 231, 0.42);
  --icon-shadow: rgba(16, 87, 147, 0.28);
  --icon-line: currentColor;
  position: relative;
  display: inline-grid;
  flex: 0 0 auto;
  place-items: center;
  width: 1em;
  height: 1em;
  color: currentColor;
  vertical-align: -0.125em;
}

.app-icon__glyph {
  position: relative;
  z-index: 2;
  width: 1em;
  height: 1em;
  fill: none;
  stroke: var(--icon-line);
  stroke-width: 1.9;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.app-icon--play .app-icon__glyph {
  fill: var(--icon-line);
  stroke: none;
}

.app-icon--tile,
.app-icon--badge {
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.72);
  background:
    radial-gradient(circle at 28% 22%, rgba(255, 255, 255, 0.82), transparent 23%),
    linear-gradient(145deg, var(--icon-top), var(--icon-mid) 52%, var(--icon-bottom));
  color: #ffffff;
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.9) inset,
    0 -10px 18px rgba(0, 38, 76, 0.16) inset,
    0 9px 18px var(--icon-shadow);
}

.app-icon--tile::before,
.app-icon--badge::before {
  position: absolute;
  inset: 1px;
  border-radius: inherit;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.38), transparent 44%),
    radial-gradient(circle at 74% 78%, rgba(255, 255, 255, 0.18), transparent 28%);
  content: "";
}

.app-icon--tile::after,
.app-icon--badge::after {
  position: absolute;
  inset: 0;
  border: 1px solid var(--icon-ring);
  border-radius: inherit;
  content: "";
}

.app-icon--tile {
  border-radius: 11px;
}

.app-icon--tile .app-icon__glyph {
  width: 52%;
  height: 52%;
  filter: drop-shadow(0 1px 1px rgba(0, 30, 64, 0.34));
  stroke: #ffffff;
  stroke-width: 2.2;
}

.app-icon--badge {
  border-radius: 999px;
}

.app-icon--badge .app-icon__glyph {
  width: 58%;
  height: 58%;
  filter: drop-shadow(0 1px 1px rgba(0, 30, 64, 0.3));
  stroke: #ffffff;
  stroke-width: 2.3;
}

.app-icon--cyan {
  --icon-top: #4dd5ec;
  --icon-mid: #1d9ed0;
  --icon-bottom: #106a9c;
  --icon-ring: rgba(116, 216, 239, 0.46);
  --icon-shadow: rgba(9, 112, 153, 0.24);
}

.app-icon--green {
  --icon-top: #4ed79f;
  --icon-mid: #249b70;
  --icon-bottom: #12664e;
  --icon-ring: rgba(115, 223, 172, 0.42);
  --icon-shadow: rgba(20, 119, 83, 0.23);
}

.app-icon--amber {
  --icon-top: #ffd06a;
  --icon-mid: #e79122;
  --icon-bottom: #b9610d;
  --icon-ring: rgba(255, 194, 89, 0.44);
  --icon-shadow: rgba(173, 100, 16, 0.24);
}

.app-icon--red {
  --icon-top: #ff8f76;
  --icon-mid: #d8543f;
  --icon-bottom: #9d2e24;
  --icon-ring: rgba(240, 124, 102, 0.42);
  --icon-shadow: rgba(148, 54, 40, 0.24);
}

.app-icon--slate {
  --icon-top: #9fb4c7;
  --icon-mid: #647f98;
  --icon-bottom: #3d566e;
  --icon-ring: rgba(154, 179, 199, 0.38);
  --icon-shadow: rgba(61, 86, 110, 0.2);
}
</style>
