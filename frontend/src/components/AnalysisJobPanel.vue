<template>
  <div class="job-panel" :class="{ timeout: timedOut }">
    <div class="job-panel-copy">
      <strong>后台分析任务</strong>
      <span>{{ jobId }} · {{ jobStatusLabel(status) }}</span>
      <div
        class="job-progress"
        role="progressbar"
        :aria-valuenow="jobProgressPercent(progress)"
        aria-valuemin="0"
        aria-valuemax="100"
      >
        <span :style="{ width: `${jobProgressPercent(progress)}%` }"></span>
      </div>
      <small v-if="jobProgressMessage(progress)">
        {{ jobProgressMessage(progress) }} · {{ jobProgressPercent(progress) }}%
      </small>
      <small v-if="error">{{ error }}</small>
      <small v-else-if="canceling">正在提交取消请求。</small>
      <small v-else-if="timedOut">任务可能仍在后台运行，可继续查询状态。</small>
    </div>
    <div class="job-panel-actions">
      <AppButton variant="ghost" size="sm" icon="load" :disabled="loading || canceling" @click="emit('refresh')">
        继续查询
      </AppButton>
      <AppButton
        variant="ghost"
        size="sm"
        icon="stop"
        :disabled="canceling || !canCancelJob(status)"
        @click="emit('cancel')"
      >
        取消
      </AppButton>
      <AppButton
        variant="ghost"
        size="sm"
        icon="play"
        :disabled="loading || canceling || !canRetryJob(status, timedOut)"
        @click="emit('retry')"
      >
        重试
      </AppButton>
    </div>
  </div>
</template>

<script setup lang="ts">
import AppButton from "@/components/AppButton.vue";

withDefaults(
  defineProps<{
    jobId: string;
    status: string;
    error: string;
    progress: Record<string, unknown>;
    timedOut: boolean;
    loading: boolean;
    canceling?: boolean;
  }>(),
  {
    canceling: false,
  },
);

const emit = defineEmits<{
  refresh: [];
  cancel: [];
  retry: [];
}>();

// Job 状态展示集中在这里，避免主分析组件同时承担任务状态翻译和按钮可用性判断。
function jobStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    queued: "排队中",
    running: "运行中",
    completed: "已完成",
    failed: "失败",
    canceled: "已取消",
  };
  return labels[status] ?? (status || "未启动");
}

function canCancelJob(status: string): boolean {
  return status === "queued" || status === "running";
}

function canRetryJob(status: string, timedOut: boolean): boolean {
  return timedOut || status === "failed" || status === "canceled";
}

function jobProgressPercent(progress: Record<string, unknown>): number {
  const percent = progress.percent;
  if (typeof percent !== "number" || !Number.isFinite(percent)) return 0;
  return Math.max(0, Math.min(100, Math.round(percent)));
}

function jobProgressMessage(progress: Record<string, unknown>): string {
  return typeof progress.message === "string" ? progress.message : "";
}
</script>

<style scoped>
.job-panel {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  margin: 0 0 10px;
  border: 1px solid var(--ov-border);
  border-radius: 6px;
  padding: 8px 10px;
  background: var(--ov-bg-soft);
}

.job-panel.timeout {
  border-color: var(--ov-warning);
  background: var(--ov-bg-warning);
}

.job-panel-copy {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.job-panel-copy strong {
  color: var(--ov-text);
  font-size: 12px;
}

.job-panel-copy span,
.job-panel-copy small {
  min-width: 0;
  color: var(--ov-text-secondary);
  font-size: 11px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.job-progress {
  position: relative;
  width: min(100%, 360px);
  height: 7px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--ov-border-subtle);
}

.job-progress span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--ov-primary-strong);
}

.job-panel-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: flex-end;
}
</style>
