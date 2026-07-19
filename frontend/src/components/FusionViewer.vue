<template>
  <section class="viewer-panel">
    <div class="panel-heading">
      <p>双通道融合</p>
      <h2>图像查看</h2>
    </div>
    <div class="viewer-placeholder">暂无融合图像</div>
  </section>
</template>

<style scoped>
.viewer-panel {
  border: 1px solid var(--ov-border);
  border-radius: 8px;
  padding: 14px;
  background: var(--ov-bg-elevated);
}

.panel-heading {
  margin-bottom: 12px;
}

.panel-heading p,
.panel-heading h2 {
  margin: 0;
  letter-spacing: 0;
}

.panel-heading p {
  margin-bottom: 6px;
  color: var(--ov-text-secondary);
  font-size: 12px;
  font-weight: 700;
}

.panel-heading h2 {
  font-size: 18px;
}

.viewer-placeholder {
  display: grid;
  place-items: center;
  min-height: 220px;
  border: 1px dashed var(--ov-border-strong);
  border-radius: 8px;
  background: var(--ov-bg-soft);
  color: var(--ov-text-secondary);
  font-weight: 700;
}
</style>
