<template>
  <section class="panel">
    <div class="panel-heading">
      <p>质控</p>
      <h2>运行提示</h2>
    </div>
    <p>暂无阻断性提示。</p>
  </section>
</template>

<style scoped>
.panel {
  border: 1px solid var(--ov-border);
  border-radius: 8px;
  padding: 14px;
  background: var(--ov-bg-elevated);
}

.panel-heading p,
.panel-heading h2,
p {
  margin: 0;
  letter-spacing: 0;
}

.panel-heading {
  margin-bottom: 10px;
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

p {
  color: var(--ov-text-secondary);
  font-size: 13px;
}
</style>
