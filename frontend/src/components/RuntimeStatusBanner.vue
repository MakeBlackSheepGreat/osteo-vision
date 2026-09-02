<template>
  <section
    v-if="visible"
    class="runtime-status"
    :class="`runtime-status--${tone}`"
    :role="blocking ? 'alert' : 'status'"
    :aria-live="blocking ? 'assertive' : 'polite'"
  >
    <div class="runtime-status__inner">
      <AppIcon :name="blocking ? 'stop' : 'alert'" />
      <div class="runtime-status__copy">
        <strong>{{ title }}</strong>
        <span>{{ detail }}</span>
      </div>
      <dl v-if="readiness" class="runtime-status__facts">
        <div>
          <dt>运行档位</dt>
          <dd>{{ readiness.runtime_profile }}</dd>
        </div>
        <div>
          <dt>模型</dt>
          <dd>{{ modelLabel }}</dd>
        </div>
        <div>
          <dt>配置校验</dt>
          <dd>{{ shortHash(readiness.config_sha256) }}</dd>
        </div>
        <div>
          <dt>模型校验</dt>
          <dd>{{ modelHashLabel }}</dd>
        </div>
        <div>
          <dt>计算</dt>
          <dd>{{ acceleratorLabel }}</dd>
        </div>
      </dl>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import AppIcon from "@/components/AppIcon.vue";
import { getRuntimeReadiness } from "@/services/runtimeClient";
import type { AcceleratorRuntimeStatus, RuntimeReadiness } from "@/types/runtime";

const emit = defineEmits<{
  blockingChange: [blocking: boolean];
}>();

const expectStrict = import.meta.env.VITE_OSTEO_EXPECT_STRICT_RUNTIME === "true";
const readiness = ref<RuntimeReadiness | null>(null);
const accelerator = ref<AcceleratorRuntimeStatus | null>(null);
const requestFailed = ref(false);
const checking = ref(expectStrict);

const strictMismatch = computed(
  () =>
    Boolean(readiness.value) &&
    (readiness.value?.runtime_profile !== "competition_strict" || readiness.value?.strict_startup !== true),
);
const blocking = computed(
  () => expectStrict && (checking.value || requestFailed.value || strictMismatch.value || readiness.value?.passed !== true),
);
const strictVerified = computed(
  () =>
    readiness.value?.passed === true &&
    readiness.value.runtime_profile === "competition_strict" &&
    readiness.value.strict_startup === true,
);
const visible = computed(() => checking.value || requestFailed.value || Boolean(readiness.value));
const tone = computed(() => {
  if (blocking.value || requestFailed.value) return "danger";
  return strictVerified.value ? "success" : "warning";
});
const title = computed(() => {
  if (checking.value) return "正在核验比赛运行环境";
  if (requestFailed.value) return "运行环境核验失败";
  if (blocking.value) return "比赛运行已阻断";
  if (strictVerified.value) return "比赛严格运行已核验";
  return "当前为研发运行档位";
});
const detail = computed(() => {
  if (checking.value) return "严格配置核验完成前，病例工作流保持锁定。";
  if (requestFailed.value) return "无法读取后端就绪状态，请检查后端服务和网络配置。";
  if (blocking.value) return "后端未满足 competition_strict、严格启动和模型校验要求。";
  if (strictVerified.value) return "配置、主线模型、checkpoint 校验和视频工具均通过严格启动门。";
  return "当前实例允许夹具或研发模型，仅用于工程验证；比赛演示请使用严格启动入口。";
});
const modelLabel = computed(() => {
  const models = readiness.value?.required_model_ids ?? [];
  return models.length ? models.join(", ") : "未锁定";
});
const modelHashLabel = computed(() => {
  const hashes = readiness.value?.verified_models?.map((item) => shortHash(item.checkpoint_sha256)) ?? [];
  return hashes.length ? hashes.join(", ") : "无已验证模型";
});
const acceleratorLabel = computed(() => {
  if (!accelerator.value) return "未读取";
  if (accelerator.value.gpu_acceleration_enabled) {
    return `GPU：${accelerator.value.gpu_name ?? "CUDA"}`;
  }
  return accelerator.value.fallback_active ? `CPU 降级：${fallbackReasonLabel(accelerator.value.fallback_reason)}` : "CPU 策略";
});

onMounted(async () => {
  emit("blockingChange", blocking.value);
  try {
    const response = await getRuntimeReadiness();
    readiness.value = response.runtime_readiness;
    accelerator.value = response.accelerator ?? null;
  } catch {
    requestFailed.value = true;
  } finally {
    checking.value = false;
    emit("blockingChange", blocking.value);
  }
});

function shortHash(value?: string | null): string {
  return value ? value.slice(0, 12) : "不可用";
}

function fallbackReasonLabel(value?: string | null): string {
  const labels: Record<string, string> = {
    torch_unavailable: "Torch 运行时不可用",
    cuda_unavailable: "CUDA 驱动或设备不可用",
    cuda_device_missing: "未发现 CUDA 设备",
    cuda_probe_failed: "CUDA 探测失败",
  };
  return value ? (labels[value] ?? value) : "未提供原因";
}
</script>

<style scoped>
.runtime-status {
  border-bottom: 1px solid var(--ov-border-subtle);
}

.runtime-status--warning {
  border-color: color-mix(in srgb, var(--ov-warning) 32%, transparent);
  background: var(--ov-bg-warning);
  color: var(--ov-warning);
}

.runtime-status--danger {
  border-color: var(--ov-danger-border);
  background: var(--ov-bg-danger);
  color: var(--ov-danger);
}

.runtime-status--success {
  border-color: color-mix(in srgb, var(--ov-success) 32%, transparent);
  background: var(--ov-bg-success);
  color: var(--ov-success);
}

.runtime-status__inner {
  display: grid;
  grid-template-columns: auto minmax(260px, 1fr) minmax(420px, auto);
  gap: 14px;
  align-items: center;
  width: min(100%, var(--ov-content-wide));
  margin: 0 auto;
  padding: 10px var(--ov-page-inline);
}

.runtime-status__inner :deep(.app-icon) {
  width: 20px;
  height: 20px;
}

.runtime-status__copy {
  display: grid;
  gap: 2px;
}

.runtime-status__copy strong,
.runtime-status__copy span,
.runtime-status__facts dd {
  overflow-wrap: anywhere;
}

.runtime-status__copy strong {
  font-size: 13px;
}

.runtime-status__copy span {
  color: var(--ov-text-muted);
  font-size: 12px;
}

.runtime-status__facts {
  display: grid;
  grid-template-columns: repeat(5, minmax(90px, auto));
  gap: 12px;
  margin: 0;
}

.runtime-status__facts div {
  display: grid;
  gap: 1px;
}

.runtime-status__facts dt {
  color: var(--ov-text-muted);
  font-size: 10px;
}

.runtime-status__facts dd {
  max-width: 240px;
  margin: 0;
  color: var(--ov-text);
  font-size: 11px;
  font-weight: 650;
}

@media (max-width: 1180px) {
  .runtime-status__inner {
    grid-template-columns: auto 1fr;
  }

  .runtime-status__facts {
    grid-column: 2;
    grid-template-columns: repeat(2, minmax(120px, 1fr));
  }
}
</style>
