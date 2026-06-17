<template>
  <main class="workspace">
    <header class="banner">
      <h1>Osteo Vision</h1>
      <p>Research prototype only. Outputs are for physician review.</p>
    </header>

    <section class="panel">
      <div class="row">
        <input v-model="caseTitle" placeholder="Case title" />
        <button @click="createCase">Create case</button>
        <button @click="loadCase">Load current case</button>
      </div>
      <div class="row">
        <input v-model="whiteLightPath" placeholder="White-light image path" />
        <input v-model="fluorescencePath" placeholder="Fluorescence image path" />
        <button @click="importInputs">Add inputs</button>
      </div>
      <div class="row">
        <button @click="runAnalysis">Run dual-channel analysis</button>
        <button @click="exportCase">Export evidence bundle</button>
      </div>
      <p v-if="store.loading">Working…</p>
      <p v-if="store.error" class="error">{{ store.error }}</p>
    </section>

    <section class="grid">
      <article class="card">
        <h2>Case</h2>
        <pre>{{ store.currentCase }}</pre>
      </article>
      <article class="card">
        <h2>Artifacts</h2>
        <pre>{{ store.exportPath }}</pre>
      </article>
    </section>
  </main>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useCaseStore } from "@/stores/caseStore";

const store = useCaseStore();
const caseTitle = ref("Jaw osteomyelitis V1 demo");
const whiteLightPath = ref("");
const fluorescencePath = ref("");

async function createCase() {
  await store.createCase(caseTitle.value);
}

async function loadCase() {
  if (!store.currentCase) return;
  await store.loadCase(store.currentCase.case_id);
}

async function importInputs() {
  await store.importInputs([
    { channel: "white_light", path: whiteLightPath.value },
    { channel: "fluorescence", path: fluorescencePath.value },
  ]);
}

async function runAnalysis() {
  await store.runAnalysis({ alpha: 0.45, threshold: 0.6, colormap: "green" });
}

async function exportCase() {
  await store.exportCase();
}
</script>

<style scoped>
.workspace {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
  font-family: system-ui, sans-serif;
}
.banner {
  margin-bottom: 24px;
}
.panel {
  display: grid;
  gap: 12px;
  margin-bottom: 24px;
}
.row {
  display: grid;
  grid-template-columns: 1fr 1fr auto;
  gap: 12px;
}
.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.card {
  border: 1px solid #d0d7de;
  border-radius: 8px;
  padding: 16px;
  background: #fff;
}
.error {
  color: #b42318;
}
input, button {
  padding: 10px 12px;
}
pre {
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
