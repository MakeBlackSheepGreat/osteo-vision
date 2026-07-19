<template>
  <main class="navigation-workspace">
    <header class="navigation-workspace__header">
      <div>
        <p>三维建模与术中导航</p>
        <h1>病例三维导航工作台</h1>
        <span>读取病例中的视频候选区、模型、配准和医生复核证据。</span>
      </div>
      <div class="navigation-workspace__actions">
        <RouterLink class="navigation-workspace__back" :to="surgeryRoute">
          <AppIcon name="video" />
          返回术中影像
        </RouterLink>
        <AppButton
          variant="secondary"
          size="sm"
          icon="load"
          :disabled="store.loading || !store.currentCase"
          :title="
            store.loading
              ? '正在同步病例数据'
              : store.currentCase
                ? '重新读取当前病例及三维证据'
                : '请先在病例档案中载入病例'
          "
          @click="refreshCase"
        >
          {{ store.loading ? "正在同步" : "同步病例数据" }}
        </AppButton>
      </div>
    </header>

    <p v-if="store.error" class="navigation-workspace__error">{{ store.error }}</p>

    <section v-if="!store.currentCase" class="navigation-empty-workbench" aria-live="polite">
      <header class="navigation-empty-workbench__notice">
        <AppIcon name="cube" variant="badge" tone="cyan" />
        <div>
          <h2>尚未载入病例</h2>
          <p>载入病例后可写入 CBCT/STL、检查三维模型，并记录配准与医生复核证据。</p>
        </div>
        <RouterLink to="/cases">前往病例档案</RouterLink>
      </header>

      <div class="navigation-empty-workbench__grid">
        <section class="navigation-empty-workbench__panel navigation-empty-workbench__imports" aria-label="CBCT 和 STL 导入">
          <header class="navigation-empty-workbench__panel-title">
            <AppIcon name="upload" />
            <div>
              <strong>CBCT / STL 导入</strong>
              <small>文件将写入当前病例证据链</small>
            </div>
          </header>
          <div class="navigation-empty-workbench__import-row">
            <div>
              <strong>CBCT 体数据</strong>
              <small>DICOM、NIfTI</small>
            </div>
            <AppButton
              size="sm"
              icon="folder"
              disabled
              data-requires-case="true"
              title="请先载入病例"
            >
              选择文件
            </AppButton>
          </div>
          <div class="navigation-empty-workbench__import-row">
            <div>
              <strong>表面模型</strong>
              <small>STL、GLB</small>
            </div>
            <AppButton
              size="sm"
              icon="folder"
              disabled
              data-requires-case="true"
              title="请先载入病例"
            >
              选择文件
            </AppButton>
          </div>
          <p>导入前需关联病例，确保来源、方向和处理记录可追溯。</p>
        </section>

        <section class="navigation-empty-workbench__panel navigation-empty-workbench__tree" aria-label="病例对象树">
          <header class="navigation-empty-workbench__panel-title">
            <AppIcon name="layers" />
            <div>
              <strong>病例对象树</strong>
              <small>模型、分割、标注与变换</small>
            </div>
          </header>
          <ul>
            <li>
              <span aria-hidden="true"></span>
              <div><strong>患者空间</strong><small>等待病例坐标系</small></div>
              <b>未载入</b>
            </li>
            <li>
              <span aria-hidden="true"></span>
              <div><strong>骨表面与分割</strong><small>等待 CBCT/STL</small></div>
              <b>0</b>
            </li>
            <li>
              <span aria-hidden="true"></span>
              <div><strong>候选区与标注</strong><small>等待影像分析证据</small></div>
              <b>0</b>
            </li>
            <li>
              <span aria-hidden="true"></span>
              <div><strong>坐标变换</strong><small>等待 L1/L2 验证</small></div>
              <b>0</b>
            </li>
          </ul>
        </section>

        <section
          class="navigation-empty-workbench__panel navigation-empty-workbench__viewport"
          aria-label="空三维视口"
          data-state="awaiting-case"
        >
          <header>
            <div><span>主检查视口</span><strong>三维场景</strong></div>
            <b>等待病例</b>
          </header>
          <div class="navigation-empty-workbench__viewport-empty">
            <AppIcon name="cube" variant="badge" tone="slate" />
            <strong>三维内容尚未载入</strong>
            <p>病例载入后，此处显示 CBCT 派生表面、STL 模型、视频候选区和复核标注。</p>
            <small>空间方向、模型来源和配准状态将在视口内持续显示。</small>
          </div>
          <footer>
            <AppButton
              size="sm"
              icon="expand"
              disabled
              data-requires-case="true"
              title="请先载入病例"
            >
              适应视图
            </AppButton>
            <AppButton
              size="sm"
              icon="move"
              disabled
              data-requires-case="true"
              title="请先载入病例"
            >
              自动旋转：关
            </AppButton>
          </footer>
        </section>

        <section class="navigation-empty-workbench__panel navigation-empty-workbench__checks" aria-label="建模检查">
          <header class="navigation-empty-workbench__panel-title">
            <AppIcon name="check" />
            <div>
              <strong>建模检查</strong>
              <small>生成表面前的必要门控</small>
            </div>
          </header>
          <ul>
            <li><span>体数据方向</span><strong>待检查</strong></li>
            <li><span>体素与物理坐标</span><strong>待检查</strong></li>
            <li><span>分割或代理来源</span><strong>待记录</strong></li>
            <li><span>表面连通性</span><strong>待检查</strong></li>
          </ul>
          <AppButton
            size="sm"
            icon="cube"
            block
            disabled
            data-requires-case="true"
            title="请先载入病例"
          >
            生成检查表面
          </AppButton>
        </section>

        <section class="navigation-empty-workbench__panel navigation-empty-workbench__review" aria-label="复核与导航状态">
          <header class="navigation-empty-workbench__panel-title">
            <AppIcon name="review" />
            <div>
              <strong>复核与导航状态</strong>
              <small>缺失证据时保持安全降级</small>
            </div>
          </header>
          <dl>
            <div><dt>医生复核</dt><dd>待病例</dd></div>
            <div><dt>空间配准</dt><dd>未配准</dd></div>
            <div><dt>导航级别</dt><dd>L0 参考</dd></div>
            <div><dt>导航显示</dt><dd>禁止就绪</dd></div>
          </dl>
          <p>完成模型来源核验、坐标配准、误差记录和医生复核后，方可提升验证级别。</p>
          <AppButton
            size="sm"
            icon="check"
            block
            disabled
            data-requires-case="true"
            title="请先载入病例"
          >
            提交医生复核
          </AppButton>
        </section>
      </div>
    </section>

    <template v-else>
      <section class="navigation-context" aria-label="三维导航数据联动状态">
        <div>
          <span>当前病例</span>
          <strong>{{ store.currentCase.title }}</strong>
          <small>{{ store.currentCase.case_id }}</small>
        </div>
        <div>
          <span>视频来源</span>
          <strong>{{ videoSourceLabel }}</strong>
          <small>{{ latestRunModeLabel }}</small>
        </div>
        <div>
          <span>候选区联动</span>
          <strong>{{ candidates.length }} 个</strong>
          <small>{{ selectedFrameLabel }}</small>
        </div>
        <div>
          <span>空间配准</span>
          <strong :class="{ ready: navigationReady }">{{ registrationLabel }}</strong>
          <small>{{ registrationErrorLabel }}</small>
        </div>
      </section>

      <NavigationSafetyStatusPanel :evidence="threeDEvidence" />

      <Suspense>
        <Anatomy3DPanel
          :case-id="store.currentCase.case_id"
          :candidates="candidates"
          :metrics="metrics"
          :mode-label="latestRunModeLabel"
          :three-d-evidence="threeDEvidence"
          @select-candidate-frame="selectCandidateFrame"
          @three-d-evidence-persisted="refreshCase"
        />
        <template #fallback>
          <section class="navigation-workspace__module-loading" role="status" aria-live="polite">
            <AppIcon name="cube" decorative />
            <div>
              <strong>正在载入三维检查视口</strong>
              <span>病例证据与安全状态保持可见。</span>
            </div>
          </section>
        </template>
      </Suspense>

      <header class="navigation-workspace__evidence-heading">
        <div><span>工程验证证据</span><strong>L1 静态配准与 L2 离线动态 AR</strong></div>
        <small>主三维检查完成后，在此记录标定、误差、变换链和受控回放结果。</small>
      </header>
      <L1RegistrationPanel :case-id="store.currentCase.case_id" :evidence="threeDEvidence" @completed="refreshCase" />
      <L2PoseReplayPanel
        :case-id="store.currentCase.case_id"
        :evidence="threeDEvidence"
        :video-inputs="store.currentCase.inputs"
        :case-admission-status="store.currentCase.intake_metadata?.admission_status"
        :case-authorization-status="store.currentCase.intake_metadata?.authorization_status"
        :case-deidentification-confirmed="store.currentCase.intake_metadata?.deidentification_confirmed"
        @completed="refreshCase"
      />
    </template>
  </main>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import AppButton from "@/components/AppButton.vue";
import AppIcon from "@/components/AppIcon.vue";
import NavigationSafetyStatusPanel from "@/components/NavigationSafetyStatusPanel.vue";
import L1RegistrationPanel from "@/components/L1RegistrationPanel.vue";
import L2PoseReplayPanel from "@/components/L2PoseReplayPanel.vue";
import { useCaseStore } from "@/stores/caseStore";
import type { CandidateRegion, NavigationFrameSelection, ThreeDEvidence } from "@/types/case";
import { isRecord, stringFrom } from "@/utils/caseDisplay";

const Anatomy3DPanel = defineAsyncComponent(() => import("@/components/Anatomy3DPanel.vue"));

const store = useCaseStore();
const route = useRoute();
const router = useRouter();

const latestRun = computed(() => store.currentCase?.analysis_runs.at(-1) ?? null);
const candidates = computed<CandidateRegion[]>(() => latestRun.value?.candidate_regions ?? []);
const metrics = computed<Record<string, unknown>>(() => latestRun.value?.quantitative_summary ?? {});
const threeDEvidence = computed<ThreeDEvidence | null>(() => {
  const caseEvidence = store.currentCase?.three_d_evidence;
  if (isRecord(caseEvidence) && Object.keys(caseEvidence).length) return caseEvidence as ThreeDEvidence;
  const runEvidence = latestRun.value?.fused_outputs?.three_d_evidence;
  return isRecord(runEvidence) ? (runEvidence as ThreeDEvidence) : null;
});
const latestRunModeLabel = computed(() => {
  const mode = stringFrom(latestRun.value?.fused_outputs?.mode);
  return mode === "video_file_keyframes" ? "MP4 候选区空间证据" : "白光/荧光融合证据";
});
const videoSourceLabel = computed(() => {
  const videoInput = [...(store.currentCase?.inputs ?? [])].reverse().find((input) => input.channel === "video");
  if (!videoInput?.path) return "尚未导入 MP4";
  const normalized = videoInput.path.replace(/\\/g, "/");
  return normalized.split("/").at(-1) || videoInput.path;
});
const navigationReady = computed(() => {
  const value = threeDEvidence.value?.navigation_ready;
  const ready = value === true || (typeof value === "string" && ["true", "ready", "1"].includes(value.toLowerCase()));
  return ready && ["L1", "L2"].includes(String(threeDEvidence.value?.navigation_level)) && stringFrom(threeDEvidence.value?.registration_status).toLowerCase() === "registered";
});
const registrationLabel = computed(() => {
  if (navigationReady.value) return "导航前置条件已记录";
  const status = stringFrom(threeDEvidence.value?.registration_status).toLowerCase();
  if (status === "registered") return "配准已记录，仍需检查";
  return "未配准参考";
});
const registrationErrorLabel = computed(() => {
  const value = threeDEvidence.value?.registration_error_mm;
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? `配准误差 ${parsed.toFixed(2)} mm` : "配准误差未记录";
});
const selectedFrame = computed(() => {
  const selection = store.navigationFrameSelection;
  return selection?.caseId === store.currentCase?.case_id ? selection : null;
});
const selectedFrameLabel = computed(() => {
  const selection = selectedFrame.value;
  if (!selection) return "从三维候选区选择后可回到视频帧";
  if (selection.timestampSec !== null) return `已选择 ${selection.timestampSec.toFixed(2)} s`;
  if (selection.frameIndex !== null) return `已选择帧 ${selection.frameIndex}`;
  return "已选择视频候选区";
});
const surgeryRoute = computed(() => {
  const caseId = store.currentCase?.case_id || stringQuery(route.query.caseId);
  const selection = selectedFrame.value;
  return {
    path: "/case",
    query: {
      ...(caseId ? { caseId } : {}),
      ...(selection?.candidateId ? { candidateId: selection.candidateId } : {}),
      ...(selection?.frameKey ? { frameKey: selection.frameKey } : {}),
      ...(selection?.frameIndex !== null && selection?.frameIndex !== undefined
        ? { frameIndex: String(selection.frameIndex) }
        : {}),
      ...(selection?.timestampSec !== null && selection?.timestampSec !== undefined
        ? { timestampSec: String(selection.timestampSec) }
        : {}),
    },
  };
});

watch(
  () => route.query.caseId,
  async (value) => {
    const caseId = stringQuery(value);
    if (!caseId || store.currentCase?.case_id === caseId) return;
    await store.loadCase(caseId);
  },
  { immediate: true },
);

async function refreshCase() {
  const caseId = store.currentCase?.case_id || stringQuery(route.query.caseId);
  if (caseId) await store.loadCase(caseId);
}

function selectCandidateFrame(payload: Omit<NavigationFrameSelection, "caseId">) {
  const caseId = store.currentCase?.case_id;
  if (!caseId) return;
  const selection: NavigationFrameSelection = { caseId, ...payload };
  store.selectNavigationFrame(selection);
  void router.replace({
    path: "/navigation",
    query: {
      caseId,
      candidateId: payload.candidateId,
      ...(payload.frameKey ? { frameKey: payload.frameKey } : {}),
      ...(payload.frameIndex !== null ? { frameIndex: String(payload.frameIndex) } : {}),
      ...(payload.timestampSec !== null ? { timestampSec: String(payload.timestampSec) } : {}),
    },
  });
}

function stringQuery(value: unknown): string {
  if (Array.isArray(value)) return typeof value[0] === "string" ? value[0] : "";
  return typeof value === "string" ? value : "";
}
</script>

<style scoped>
.navigation-workspace {
  min-height: 100dvh;
  padding: var(--ov-page-top) var(--ov-page-inline) var(--ov-page-bottom);
  background: var(--ov-shell-background);
  color: var(--ov-text);
}

.navigation-workspace__header,
.navigation-context,
.navigation-workspace > .anatomy-3d,
.navigation-workspace__module-loading,
.navigation-empty-workbench,
.navigation-workspace__evidence-heading,
.navigation-workspace__error {
  width: min(100%, var(--ov-content-wide));
  margin-right: auto;
  margin-left: auto;
}

.navigation-workspace__module-loading {
  display: flex;
  gap: 12px;
  align-items: center;
  min-height: 220px;
  border: 1px solid var(--ov-border);
  border-radius: 7px;
  padding: 24px;
  background-color: var(--ov-bg-panel);
  background-image:
    linear-gradient(var(--ov-grid-line) 1px, transparent 1px),
    linear-gradient(90deg, var(--ov-grid-line) 1px, transparent 1px);
  background-size: 28px 28px;
}

.navigation-workspace__module-loading > .app-icon {
  width: 34px;
  height: 34px;
  color: var(--ov-primary-strong);
}

.navigation-workspace__module-loading > div {
  display: grid;
  gap: 4px;
}

.navigation-workspace__module-loading strong {
  font-size: 14px;
}

.navigation-workspace__module-loading span {
  color: var(--ov-text-secondary);
  font-size: 12px;
}

.navigation-workspace__header {
  display: flex;
  gap: 24px;
  align-items: end;
  justify-content: space-between;
  margin-bottom: 20px;
  border-bottom: 1px solid var(--ov-border);
  padding: 0 4px 18px;
}

.navigation-workspace__header > div:first-child {
  min-width: 0;
}

.navigation-workspace__header p,
.navigation-workspace__header h1,
.navigation-workspace__header span {
  margin: 0;
}

.navigation-workspace__header p {
  color: var(--ov-primary-strong);
  font-size: 12px;
  font-weight: 900;
}

.navigation-workspace__header h1 {
  margin-top: 3px;
  color: var(--ov-text);
  font-size: var(--ov-font-workspace-title);
  line-height: 1.2;
}

.navigation-workspace__header span {
  display: block;
  margin-top: 5px;
  color: var(--ov-text-secondary);
  font-size: 13px;
  line-height: 1.45;
}

.navigation-workspace__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.navigation-workspace__back,
.navigation-empty-workbench__notice > a {
  display: inline-flex;
  gap: 7px;
  align-items: center;
  justify-content: center;
  min-height: 34px;
  border: 1px solid var(--ov-primary);
  border-radius: 6px;
  padding: 7px 11px;
  background: var(--ov-button-primary-bg);
  color: var(--ov-text-on-primary);
  font-size: 13px;
  font-weight: 800;
  text-decoration: none;
}

.navigation-workspace__back :deep(.app-icon) {
  width: 16px;
  height: 16px;
}

.navigation-context {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-bottom: 16px;
  border: 1px solid var(--ov-border);
  border-radius: 7px;
  background: var(--ov-bg-elevated);
}

.navigation-context > div {
  display: grid;
  gap: 2px;
  min-width: 0;
  border-right: 1px solid var(--ov-border-subtle);
  padding: 12px 14px;
}

.navigation-context > div:last-child {
  border-right: 0;
}

.navigation-context span,
.navigation-context small {
  color: var(--ov-text-muted);
  font-size: 11px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.navigation-context strong {
  color: var(--ov-text);
  font-size: 13px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.navigation-context strong.ready {
  color: var(--ov-success);
}

.navigation-empty-workbench {
  display: grid;
  gap: 14px;
}

.navigation-empty-workbench__notice {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 14px;
  align-items: center;
  border: 1px solid var(--ov-border);
  border-radius: 7px;
  padding: 14px 16px;
  background: var(--ov-bg-elevated);
}

.navigation-empty-workbench__notice > .app-icon {
  width: 40px;
  height: 40px;
}

.navigation-empty-workbench__notice h2,
.navigation-empty-workbench__notice p {
  margin: 0;
}

.navigation-empty-workbench__notice h2 {
  font-size: 17px;
}

.navigation-empty-workbench__notice p {
  margin-top: 4px;
  color: var(--ov-text-secondary);
  font-size: 13px;
  line-height: 1.45;
}

.navigation-empty-workbench__grid {
  display: grid;
  grid-template-areas:
    "imports viewport checks"
    "tree viewport review";
  grid-template-columns: minmax(230px, 0.72fr) minmax(520px, 1.75fr) minmax(250px, 0.82fr);
  gap: 14px;
  align-items: stretch;
  min-height: 620px;
}

.navigation-empty-workbench__panel {
  min-width: 0;
  border: 1px solid var(--ov-border);
  border-radius: 7px;
  background: var(--ov-bg-elevated);
}

.navigation-empty-workbench__imports {
  grid-area: imports;
  display: grid;
  gap: 12px;
  align-content: start;
  padding: 14px;
}

.navigation-empty-workbench__tree {
  grid-area: tree;
  padding: 14px;
}

.navigation-empty-workbench__viewport {
  grid-area: viewport;
}

.navigation-empty-workbench__checks {
  grid-area: checks;
}

.navigation-empty-workbench__review {
  grid-area: review;
}

.navigation-empty-workbench__panel-title {
  display: flex;
  gap: 9px;
  align-items: center;
}

.navigation-empty-workbench__panel-title > .app-icon {
  width: 17px;
  height: 17px;
  color: var(--ov-primary-strong);
}

.navigation-empty-workbench__panel-title > div {
  display: grid;
  gap: 2px;
}

.navigation-empty-workbench__panel-title strong {
  color: var(--ov-text);
  font-size: 13px;
  line-height: 1.35;
}

.navigation-empty-workbench__panel-title small {
  color: var(--ov-text-muted);
  font-size: 11px;
  line-height: 1.35;
}

.navigation-empty-workbench__import-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 9px;
  align-items: center;
  border-top: 1px solid var(--ov-border-subtle);
  padding-top: 10px;
}

.navigation-empty-workbench__import-row > div {
  display: grid;
  gap: 2px;
}

.navigation-empty-workbench__import-row strong {
  font-size: 12px;
}

.navigation-empty-workbench__import-row small,
.navigation-empty-workbench__imports > p {
  color: var(--ov-text-muted);
  font-size: 11px;
  line-height: 1.45;
}

.navigation-empty-workbench__imports > p {
  margin: 0;
  border-left: 2px solid var(--ov-border-strong);
  padding-left: 8px;
}

.navigation-empty-workbench__tree ul,
.navigation-empty-workbench__checks ul {
  display: grid;
  gap: 0;
  margin: 12px 0 0;
  padding: 0;
  list-style: none;
}

.navigation-empty-workbench__tree li {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
  border-top: 1px solid var(--ov-border-subtle);
  padding: 10px 0;
}

.navigation-empty-workbench__tree li > span {
  width: 9px;
  height: 9px;
  border: 2px solid var(--ov-border-strong);
  border-radius: 2px;
  background: var(--ov-bg-soft);
}

.navigation-empty-workbench__tree li > div {
  display: grid;
  gap: 2px;
}

.navigation-empty-workbench__tree li strong,
.navigation-empty-workbench__tree li small {
  line-height: 1.35;
}

.navigation-empty-workbench__tree li strong {
  font-size: 12px;
}

.navigation-empty-workbench__tree li small {
  color: var(--ov-text-muted);
  font-size: 10px;
}

.navigation-empty-workbench__tree li b {
  color: var(--ov-text-muted);
  font-size: 10px;
}

.navigation-empty-workbench__viewport {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  overflow: hidden;
  min-height: 620px;
  background-color: var(--ov-bg-panel);
  background-image:
    linear-gradient(var(--ov-grid-line) 1px, transparent 1px),
    linear-gradient(90deg, var(--ov-grid-line) 1px, transparent 1px);
  background-size: 28px 28px;
}

.navigation-empty-workbench__viewport > header,
.navigation-empty-workbench__viewport > footer {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--ov-border);
  padding: 11px 13px;
  background: var(--ov-bg-elevated);
}

.navigation-empty-workbench__viewport > header > div {
  display: grid;
  gap: 2px;
}

.navigation-empty-workbench__viewport > header span {
  color: var(--ov-text-muted);
  font-size: 10px;
}

.navigation-empty-workbench__viewport > header strong {
  font-size: 13px;
}

.navigation-empty-workbench__viewport > header b {
  border: 1px solid var(--ov-border-strong);
  border-radius: 4px;
  padding: 4px 7px;
  background: var(--ov-bg-soft);
  color: var(--ov-text-muted);
  font-size: 10px;
}

.navigation-empty-workbench__viewport > footer {
  justify-content: flex-end;
  border-top: 1px solid var(--ov-border);
  border-bottom: 0;
}

.navigation-empty-workbench__viewport-empty {
  display: grid;
  place-content: center;
  justify-items: center;
  width: min(100%, 470px);
  margin: auto;
  padding: 32px;
  text-align: center;
}

.navigation-empty-workbench__viewport-empty > .app-icon {
  width: 50px;
  height: 50px;
  margin-bottom: 12px;
}

.navigation-empty-workbench__viewport-empty strong {
  font-size: 15px;
}

.navigation-empty-workbench__viewport-empty p,
.navigation-empty-workbench__viewport-empty small {
  margin: 7px 0 0;
  color: var(--ov-text-secondary);
  font-size: 12px;
  line-height: 1.55;
}

.navigation-empty-workbench__viewport-empty small {
  color: var(--ov-text-muted);
  font-size: 10px;
}

.navigation-empty-workbench__checks,
.navigation-empty-workbench__review {
  display: grid;
  gap: 12px;
  align-content: start;
  padding: 14px;
}

.navigation-empty-workbench__checks li {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
  border-top: 1px solid var(--ov-border-subtle);
  padding: 9px 0;
  color: var(--ov-text-secondary);
  font-size: 11px;
}

.navigation-empty-workbench__checks li strong {
  color: var(--ov-warning);
  font-size: 10px;
}

.navigation-empty-workbench__review dl {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin: 0;
}

.navigation-empty-workbench__review dl > div {
  display: grid;
  gap: 3px;
  border-left: 2px solid var(--ov-border-strong);
  padding-left: 8px;
}

.navigation-empty-workbench__review dt {
  color: var(--ov-text-muted);
  font-size: 10px;
}

.navigation-empty-workbench__review dd {
  margin: 0;
  color: var(--ov-text);
  font-size: 11px;
  font-weight: 800;
}

.navigation-empty-workbench__review > p {
  margin: 0;
  color: var(--ov-text-muted);
  font-size: 11px;
  line-height: 1.5;
}

.navigation-workspace__evidence-heading {
  display: flex;
  gap: 18px;
  align-items: end;
  justify-content: space-between;
  margin-top: 20px;
  margin-bottom: 10px;
  border-top: 1px solid var(--ov-border);
  padding: 16px 4px 0;
}

.navigation-workspace__evidence-heading > div {
  display: grid;
  gap: 2px;
}

.navigation-workspace__evidence-heading span,
.navigation-workspace__evidence-heading small {
  color: var(--ov-text-muted);
  font-size: 11px;
  line-height: 1.4;
}

.navigation-workspace__evidence-heading strong {
  color: var(--ov-text);
  font-size: 14px;
}

.navigation-workspace__error {
  margin-bottom: 10px;
  border-left: 3px solid var(--ov-danger);
  padding: 7px 10px;
  background: var(--ov-bg-danger);
  color: var(--ov-danger);
  font-size: 13px;
}

@media (max-width: 1180px) {
  .navigation-context {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .navigation-context > div:nth-child(2) {
    border-right: 0;
  }

  .navigation-context > div:nth-child(-n + 2) {
    border-bottom: 1px solid var(--ov-border-subtle);
  }
}

@media (max-width: 1320px) {
  .navigation-empty-workbench__grid {
    grid-template-areas:
      "imports viewport"
      "tree viewport"
      "checks review";
    grid-template-columns: minmax(250px, 0.78fr) minmax(0, 1.7fr);
  }
}
</style>
