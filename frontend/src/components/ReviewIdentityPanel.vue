<template>
  <section class="identity-panel" :class="{ 'identity-panel--verified': identity?.authenticated }">
    <div class="identity-summary">
      <AppIcon :name="identity?.authenticated ? 'check' : 'alert'" />
      <div>
        <span>当前复核身份</span>
        <strong>{{ identityLabel }}</strong>
        <small>{{ identityDetail }}</small>
      </div>
    </div>

    <form v-if="!identity?.authenticated" class="identity-form" @submit.prevent="verifyToken">
      <label>
        <span>复核访问令牌</span>
        <input
          v-model="token"
          type="password"
          autocomplete="off"
          minlength="16"
          placeholder="输入医院或项目签发的令牌"
          :disabled="loading"
        />
      </label>
      <AppButton type="submit" variant="secondary" size="sm" icon="check" :disabled="loading || token.trim().length < 16">
        {{ loading ? "正在核验" : "核验身份" }}
      </AppButton>
    </form>
    <AppButton v-else variant="ghost" size="sm" icon="close" :disabled="loading" @click="disconnect">
      退出复核身份
    </AppButton>

    <p v-if="error" class="identity-error" role="alert">{{ error }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import AppButton from "@/components/AppButton.vue";
import AppIcon from "@/components/AppIcon.vue";
import { apiClient, clearReviewAccessToken, setReviewAccessToken } from "@/services/apiClient";
import type { ReviewIdentityStatus, ReviewerRole } from "@/types/reviewIdentity";

const identity = ref<ReviewIdentityStatus | null>(null);
const token = ref("");
const loading = ref(false);
const error = ref("");

const identityLabel = computed(() => {
  if (!identity.value) return "正在读取身份";
  return `${roleLabel(identity.value.role)} · ${identity.value.actor_id}`;
});
const identityDetail = computed(() => {
  if (!identity.value) return "复核写入前将核验后端身份边界。";
  const trust = identity.value.authenticated ? "身份已由服务端令牌验证" : "工程复核会话，不能记为医生签署";
  return `${identity.value.institution} · ${trust}`;
});

onMounted(refreshIdentity);

async function verifyToken() {
  const value = token.value.trim();
  if (value.length < 16 || loading.value) return;
  loading.value = true;
  error.value = "";
  setReviewAccessToken(value);
  try {
    identity.value = await apiClient.getReviewIdentity();
    token.value = "";
  } catch {
    clearReviewAccessToken();
    error.value = "复核令牌无效或身份配置未通过服务端校验。";
    await refreshIdentity(false);
  } finally {
    loading.value = false;
  }
}

async function disconnect() {
  clearReviewAccessToken();
  token.value = "";
  await refreshIdentity();
}

async function refreshIdentity(updateLoading = true) {
  if (updateLoading) loading.value = true;
  error.value = "";
  try {
    identity.value = await apiClient.getReviewIdentity();
  } catch {
    identity.value = null;
    error.value = "无法读取当前复核身份，请检查后端服务。";
  } finally {
    if (updateLoading) loading.value = false;
  }
}

function roleLabel(role: ReviewerRole): string {
  return {
    physician: "医生复核",
    project_reviewer: "项目复核",
    engineering_reviewer: "工程复核",
    legacy_unverified: "历史未核验",
  }[role];
}
</script>

<style scoped>
.identity-panel {
  display: grid;
  grid-template-columns: minmax(280px, 1fr) minmax(340px, auto);
  gap: 18px;
  align-items: center;
  max-width: var(--ov-content-standard);
  margin: 0 auto var(--ov-space-5);
  border: 1px solid color-mix(in srgb, var(--ov-warning) 36%, var(--ov-border));
  border-radius: var(--ov-radius-control);
  padding: 12px 14px;
  background: var(--ov-bg-warning);
}

.identity-panel--verified {
  border-color: color-mix(in srgb, var(--ov-success) 36%, var(--ov-border));
  background: var(--ov-bg-success);
}

.identity-summary {
  display: flex;
  gap: 10px;
  align-items: center;
  min-width: 0;
}

.identity-summary :deep(.app-icon) {
  width: 20px;
  height: 20px;
  color: var(--ov-warning);
}

.identity-panel--verified .identity-summary :deep(.app-icon) {
  color: var(--ov-success);
}

.identity-summary div {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.identity-summary span,
.identity-summary small {
  color: var(--ov-text-muted);
  font-size: 11px;
}

.identity-summary strong,
.identity-summary small {
  overflow-wrap: anywhere;
}

.identity-summary strong {
  color: var(--ov-text);
  font-size: 13px;
}

.identity-form {
  display: flex;
  gap: 8px;
  align-items: end;
}

.identity-form label {
  display: grid;
  gap: 4px;
  min-width: 240px;
}

.identity-form label span {
  color: var(--ov-text-muted);
  font-size: 10px;
}

.identity-form input {
  min-height: 34px;
  border: 1px solid var(--ov-border);
  border-radius: var(--ov-radius-control);
  padding: 6px 9px;
  background: var(--ov-bg-elevated);
  color: var(--ov-text);
}

.identity-error {
  grid-column: 1 / -1;
  margin: 0;
  color: var(--ov-danger);
  font-size: 12px;
}
</style>
