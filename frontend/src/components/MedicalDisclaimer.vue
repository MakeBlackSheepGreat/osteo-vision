<template>
  <section class="disclaimer">
    <strong>医生复核边界</strong>
    <span>输出仅作为医生复核参考，不能替代临床诊断结论。</span>
  </section>
</template>

<style scoped>
.disclaimer {
  display: flex;
  gap: 12px;
  align-items: center;
  border: 1px solid var(--ov-border);
  border-left: 4px solid var(--ov-warning);
  border-radius: 8px;
  padding: 14px 16px;
  background: var(--ov-bg-warning);
  color: var(--ov-warning);
  font-size: 14px;
  line-height: 1.55;
}
</style>
