<template>
  <AppPageShell class="showcase-page" width="wide">
    <header class="showcase-page__header">
      <div class="ov-title-lead">
        <AppIcon name="layers" variant="badge" tone="blue" />
        <div class="showcase-page__title">
          <p>挑战杯工程展示</p>
          <h1>荧光-三维证据闭环工作站</h1>
          <span>术前三维参考、术中荧光判读与复核证据。</span>
        </div>
      </div>
      <div class="showcase-page__actions" aria-label="展示页快捷入口">
        <RouterLink to="/case">
          <AppIcon name="video" />
          进入病例工作台
        </RouterLink>
        <RouterLink to="/navigation">
          <AppIcon name="cube" />
          打开三维工作台
        </RouterLink>
      </div>
    </header>

    <section class="showcase-flow" aria-label="工程展示闭环">
      <article v-for="stage in flowStages" :key="stage.step" class="showcase-flow__stage" :class="`is-${stage.tone}`">
        <span class="showcase-flow__step">{{ stage.step }}</span>
        <AppIcon :name="stage.icon" variant="badge" :tone="stage.iconTone" />
        <div>
          <small>{{ stage.eyebrow }}</small>
          <strong>{{ stage.title }}</strong>
        </div>
      </article>
    </section>

    <section class="showcase-workspace" aria-label="术前三维与术中荧光展示">
      <article class="showcase-workspace__three-d ov-card">
        <header class="showcase-panel-heading">
          <div>
            <span>术前工程规划</span>
            <strong>CBCT 解剖参考与复核方案快照</strong>
          </div>
          <small>L0 未配准参考</small>
        </header>
        <section class="showcase-planning-snapshot" aria-label="术前三维工程复核方案快照">
          <header>
            <div>
              <span>工程复核方案快照</span>
              <strong>从公开解剖参考到安全空间状态的可检查链</strong>
            </div>
            <small>展示状态可点击核对</small>
          </header>
          <div class="showcase-planning-snapshot__body">
            <div class="showcase-planning-snapshot__rail" role="tablist" aria-label="术前工程复核焦点">
              <button
                v-for="focus in planningFocuses"
                :key="focus.key"
                type="button"
                role="tab"
                :aria-selected="activePlanningFocus === focus.key"
                :class="[`is-${focus.tone}`, { 'is-active': activePlanningFocus === focus.key }]"
                @click="activePlanningFocus = focus.key"
              >
                <span class="showcase-planning-snapshot__index">{{ focus.index }}</span>
                <AppIcon :name="focus.icon" />
                <span>
                  <strong>{{ focus.title }}</strong>
                  <small>{{ focus.state }}</small>
                </span>
              </button>
            </div>
            <aside class="showcase-planning-snapshot__detail" role="status" aria-live="polite">
              <div>
                <span>当前复核焦点</span>
                <strong>{{ activePlanning.title }}</strong>
              </div>
              <dl>
                <div v-for="item in activePlanning.evidence" :key="item.label">
                  <dt>{{ item.label }}</dt>
                  <dd>{{ item.value }}</dd>
                </div>
              </dl>
            </aside>
          </div>
        </section>
        <ThreeDRendererRuntimeEmbed
          class="showcase-workspace__anatomy"
          reference-id="d024"
        />
        <p class="showcase-source-note">
          D024 公开 CBCT 解剖参考，当前保持 L0 未配准状态。
        </p>
      </article>

      <article class="showcase-workspace__vision ov-card">
        <header class="showcase-panel-heading">
          <div>
            <span>术中荧光判读</span>
            <strong>公开 ICG 视频关键帧证据</strong>
          </div>
          <small>工程验证</small>
        </header>

        <div class="showcase-vision-tabs" role="tablist" aria-label="关键帧证据图层">
          <button
            v-for="view in evidenceViews"
            :key="view.key"
            type="button"
            role="tab"
            :aria-selected="activeEvidenceView === view.key"
            :class="{ 'is-active': activeEvidenceView === view.key }"
            @click="activeEvidenceView = view.key"
          >
            {{ view.label }}
          </button>
        </div>

        <figure class="showcase-vision-frame">
          <img :src="activeEvidence.image" :alt="activeEvidence.alt" />
          <figcaption>
            <strong>{{ activeEvidence.title }}</strong>
          </figcaption>
        </figure>

        <dl class="showcase-vision-metrics">
          <div>
            <dt>数据来源</dt>
            <dd>公开人体骨移植 ICG 视频</dd>
          </div>
          <div>
            <dt>处理路径</dt>
            <dd>关键帧分割与时序量化</dd>
          </div>
          <div>
            <dt>模型输出</dt>
            <dd>信号、风险与不确定性</dd>
          </div>
          <div>
            <dt>复核状态</dt>
            <dd>医生复核待接入</dd>
          </div>
        </dl>

        <p class="showcase-source-note">
          D083 公开 ICG 骨移植视频，CC BY 4.0，非目标域工程验证。
        </p>
      </article>
    </section>

    <section class="showcase-evidence" aria-label="运行性能与安全闭环">
      <article class="showcase-evidence__metrics ov-card">
        <header class="showcase-panel-heading">
          <div>
            <span>运行可行性</span>
            <strong>双路径性能证据</strong>
          </div>
          <AppIcon name="target" />
        </header>
        <div class="showcase-metric-grid">
          <div v-for="metric in runtimeMetrics" :key="metric.label" :class="`is-${metric.tone}`">
            <span>{{ metric.label }}</span>
            <strong>{{ metric.value }}</strong>
          </div>
        </div>
      </article>

      <article class="showcase-evidence__safety ov-card">
        <header class="showcase-panel-heading">
          <div>
            <span>患者安全闭环</span>
            <strong>证据缺失时自动降级</strong>
          </div>
          <AppIcon name="review" />
        </header>
        <ol class="showcase-safety-list">
          <li v-for="item in safetyItems" :key="item.title">
            <span :class="`is-${item.tone}`">{{ item.index }}</span>
            <div>
              <strong>{{ item.title }}</strong>
            </div>
          </li>
        </ol>
      </article>
    </section>

    <section class="showcase-validation" aria-label="空间工程验证与回顾证据">
      <article class="showcase-validation__spatial ov-card">
        <header class="showcase-panel-heading">
          <div>
            <span>离线空间工程验证</span>
            <strong>从术前参考到可回放空间链</strong>
          </div>
          <small>工程验证 / 非临床导航</small>
        </header>
        <ol class="showcase-spatial-list">
          <li v-for="item in spatialValidationItems" :key="item.stage">
            <span>{{ item.stage }}</span>
            <div>
              <strong>{{ item.title }}</strong>
            </div>
            <em :class="`is-${item.tone}`">{{ item.status }}</em>
          </li>
        </ol>
        <p class="showcase-source-note">
          L1/L2 为离线工程验证；当前展示保持 L0 未配准参考。
        </p>
      </article>

      <article class="showcase-validation__review ov-card">
        <header class="showcase-panel-heading">
          <div>
            <span>回顾验证与证据回流</span>
            <strong>每次展示都能回到原始输入核对</strong>
          </div>
          <AppIcon name="clipboard" />
        </header>
        <dl class="showcase-review-grid">
          <div v-for="item in reviewEvidenceItems" :key="item.label">
            <dt>{{ item.label }}</dt>
            <dd>{{ item.value }}</dd>
          </div>
        </dl>
        <p class="showcase-source-note">
          原始文件、处理参数、模型身份与复核状态均可回到病例记录核对。
        </p>
      </article>
    </section>

  </AppPageShell>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";

import AppIcon from "@/components/AppIcon.vue";
import AppPageShell from "@/components/AppPageShell.vue";
import type { AppIconName } from "@/components/appIcons";
import ThreeDRendererRuntimeEmbed from "@/components/ThreeDRendererRuntimeEmbed.vue";

type EvidenceViewKey = "raw" | "overlay" | "risk" | "uncertainty";
type PlanningFocusKey = "reference" | "review" | "guard";

const activeEvidenceView = ref<EvidenceViewKey>("overlay");
const activePlanningFocus = ref<PlanningFocusKey>("reference");

const flowStages: Array<{
  step: string;
  eyebrow: string;
  title: string;
  detail: string;
  icon: AppIconName;
  iconTone: "cyan" | "green" | "amber";
  tone: "cyan" | "green" | "amber";
}> = [
  {
    step: "01",
    eyebrow: "术前参考",
    title: "三维参考与复核规划",
    detail: "CBCT/STL、对象树、下颌曲线和复核平面进入同一三维工作区并保留安全状态。",
    icon: "cube",
    iconTone: "cyan",
    tone: "cyan",
  },
  {
    step: "02",
    eyebrow: "术中判读",
    title: "荧光融合与 AI 候选提示",
    detail: "原始图像、荧光信号、风险和不确定性按关键帧证据统一呈现。",
    icon: "video",
    iconTone: "green",
    tone: "green",
  },
  {
    step: "03",
    eyebrow: "空间工程",
    title: "离线空间链验证",
    detail: "L1 静态仿体与 L2 离线 AR 回放保留工程状态，未满足条件时锁定为 L0 参考。",
    icon: "target",
    iconTone: "cyan",
    tone: "cyan",
  },
  {
    step: "04",
    eyebrow: "回顾验证",
    title: "医生复核与安全降级",
    detail: "复核、配准、误差或数据链缺失时保留原因并回退至安全参考状态。",
    icon: "review",
    iconTone: "amber",
    tone: "amber",
  },
];

const evidenceViews: Array<{
  key: EvidenceViewKey;
  label: string;
  image: string;
  alt: string;
  title: string;
  detail: string;
}> = [
  {
    key: "raw",
    label: "原始荧光帧",
    image: "/showcase/d083_frame_05_raw.jpg",
    alt: "公开人体骨移植 ICG 视频的原始荧光关键帧",
    title: "原始荧光关键帧",
    detail: "保留原始信号，用于后续配准、量化与复核核对。",
  },
  {
    key: "overlay",
    label: "候选叠加",
    image: "/showcase/d083_frame_05_overlay.png",
    alt: "公开人体骨移植 ICG 视频关键帧的绿色候选叠加图",
    title: "信号候选叠加",
    detail: "关键帧候选区以叠加图呈现，供医生结合原始图像复核。",
  },
  {
    key: "risk",
    label: "风险提示",
    image: "/showcase/d083_frame_05_risk.png",
    alt: "公开人体骨移植 ICG 视频关键帧的风险提示图",
    title: "风险提示层",
    detail: "风险图保留为工程候选，空间解释需经过医生复核。",
  },
  {
    key: "uncertainty",
    label: "不确定性",
    image: "/showcase/d083_frame_05_uncertainty.png",
    alt: "公开人体骨移植 ICG 视频关键帧的不确定性图",
    title: "不确定性图层",
    detail: "低置信或质量受限区域进入复核优先队列。",
  },
];

const activeEvidence = computed(() => evidenceViews.find((view) => view.key === activeEvidenceView.value) ?? evidenceViews[0]);

const planningFocuses: Array<{
  key: PlanningFocusKey;
  index: string;
  title: string;
  state: string;
  detail: string;
  boundary: string;
  icon: AppIconName;
  tone: "cyan" | "green" | "amber";
  evidence: Array<{ label: string; value: string }>;
}> = [
  {
    key: "reference",
    index: "01",
    title: "公开解剖参考",
    state: "D024 已接入",
    detail: "公开 CBCT 标签导出的下颌 STL 已进入三维参考层，支持对象、来源和方向信息核对。",
    boundary: "该模型属于公开异域解剖参考，不代表真实患者病灶或切除范围。",
    icon: "cube",
    tone: "cyan",
    evidence: [
      { label: "模型来源", value: "D024 公开 CBCT 解剖参考" },
      { label: "坐标参考", value: "DICOM LPS 显示参考" },
    ],
  },
  {
    key: "review",
    index: "02",
    title: "曲线与复核平面",
    state: "未配准示意",
    detail: "下颌曲线与复核平面在工作站中作为工程检查元素管理，用于组织对象树、复核步骤和后续标注接口。",
    boundary: "当前只保留规划界面与复核记录能力，不输出切除边界、手术路径或空间定位。",
    icon: "layers",
    tone: "green",
    evidence: [
      { label: "标注状态", value: "示意未配准" },
      { label: "复核用途", value: "曲线、平面与几何检查" },
    ],
  },
  {
    key: "guard",
    index: "03",
    title: "空间安全门控",
    state: "L0 安全锁定",
    detail: "坐标变换、误差记录和医生复核尚未齐备，平台将三维内容维持为可回顾的未配准参考。",
    boundary: "真实导航前置条件缺失时，界面锁定空间映射，并保留原因供后续工程验证追溯。",
    icon: "alert",
    tone: "amber",
    evidence: [
      { label: "配准状态", value: "未配准" },
      { label: "当前输出", value: "L0 未配准参考（非导航）" },
    ],
  },
];

const activePlanning = computed(
  () => planningFocuses.find((focus) => focus.key === activePlanningFocus.value) ?? planningFocuses[0],
);

const runtimeMetrics = [
  { label: "4K 全证据", value: "5.78 s", detail: "端到端 P95，分块路径", tone: "cyan" },
  { label: "连续帧输出", value: "176 ms", detail: "服务端端到端 P95", tone: "green" },
  { label: "代理模型", value: "Dice 0.9177", detail: "公开离体荧光代理测试集", tone: "amber" },
  { label: "证据输出", value: "5 类", detail: "JSON、CSV、Markdown、DICOM SC、ZIP", tone: "cyan" },
];

const safetyItems = [
  { index: "A", title: "原始输入留存", detail: "文件来源、SHA256、通道关系和质量检查进入病例证据链。", tone: "cyan" },
  { index: "B", title: "模型结果受限", detail: "候选区、风险与不确定性保持医生复核边界。", tone: "green" },
  { index: "C", title: "空间状态降级", detail: "标定、误差或复核条件缺失时维持 L0 未配准参考。", tone: "amber" },
];

const spatialValidationItems = [
  {
    stage: "L1",
    title: "静态数字仿体配准",
    detail: "离线 manifest、坐标变换、误差字段与篡改拒绝共同完成软件链验证。",
    status: "已完成工程门控",
    tone: "cyan",
  },
  {
    stage: "L2",
    title: "离线动态 AR 回放",
    detail: "受控位姿记录与视频帧关联进入回放验证，缺失证据时自动停止空间映射。",
    status: "已完成工程门控",
    tone: "green",
  },
  {
    stage: "L0",
    title: "当前挑战杯展示状态",
    detail: "公开三维参考用于复核与证据讲解，空间关系保持未配准并由医生后续确认。",
    status: "安全锁定",
    tone: "amber",
  },
];

const reviewEvidenceItems = [
  { label: "输入完整性", value: "来源 + SHA256", detail: "通道关系与质量检查" },
  { label: "运行身份", value: "模型 + 阈值", detail: "配置与 checkpoint 留痕" },
  { label: "复核状态", value: "医生待接入", detail: "候选区保留人工修改入口" },
  { label: "结果交付", value: "5 类证据输出", detail: "JSON、CSV、Markdown、DICOM SC、ZIP" },
];
</script>

<style scoped>
.showcase-page {
  display: grid;
  gap: 16px;
  width: min(100%, var(--ov-content-wide));
  margin: 0 auto;
  padding: var(--ov-page-top) var(--ov-page-inline) var(--ov-page-bottom);
}

.showcase-page__header,
.showcase-panel-heading,
.showcase-page__actions,
.showcase-flow,
.showcase-workspace,
.showcase-evidence,
.showcase-validation,
.showcase-metric-grid,
.showcase-vision-metrics,
.showcase-review-grid {
  min-width: 0;
}

.showcase-page__header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 16px;
  align-items: end;
}

.showcase-page__title {
  display: grid;
  gap: 4px;
}

.showcase-page__title p,
.showcase-panel-heading span {
  margin: 0;
  color: var(--ov-primary-strong);
  font-size: 12px;
  font-weight: 720;
}

.showcase-page__title h1 {
  margin: 0;
  color: var(--ov-text);
  font-size: 30px;
  line-height: 1.2;
}

.showcase-page__title > span {
  max-width: 680px;
  color: var(--ov-text-secondary);
  font-size: 13px;
  line-height: 1.45;
}

.showcase-page__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.showcase-page__actions a {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  min-height: 38px;
  border: 1px solid var(--ov-border);
  border-radius: var(--ov-radius-control);
  padding: 8px 12px;
  background: var(--ov-bg-elevated);
  color: var(--ov-text);
  font-size: 13px;
  font-weight: 680;
  text-decoration: none;
}

.showcase-page__actions a:hover {
  border-color: var(--ov-border-accent);
  background: var(--ov-bg-hover);
}

.showcase-page__actions :deep(.app-icon) {
  width: 17px;
  height: 17px;
  color: var(--ov-primary-strong);
}

.showcase-flow {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.showcase-flow__stage {
  display: grid;
  grid-template-columns: auto auto minmax(0, 1fr);
  gap: 9px;
  align-items: center;
  min-height: 88px;
  border: 1px solid var(--ov-border);
  border-left: 4px solid var(--ov-border-accent);
  border-radius: var(--ov-radius-surface);
  padding: 11px 12px;
  background: var(--ov-bg-elevated);
  box-shadow: var(--ov-shadow);
}

.showcase-flow__stage.is-green {
  border-left-color: var(--ov-success);
}

.showcase-flow__stage.is-amber {
  border-left-color: var(--ov-warning);
}

.showcase-flow__step {
  color: var(--ov-text-muted);
  font-size: 12px;
  font-weight: 760;
}

.showcase-flow__stage :deep(.app-icon) {
  width: 30px;
  height: 30px;
}

.showcase-flow__stage div {
  display: grid;
  gap: 2px;
}

.showcase-flow__stage small {
  color: var(--ov-text-muted);
  font-size: 11px;
}

.showcase-flow__stage strong {
  color: var(--ov-text);
  font-size: 14px;
  line-height: 1.35;
}

.showcase-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(420px, 0.7fr);
  gap: 12px;
  align-items: stretch;
}

.showcase-workspace__three-d,
.showcase-workspace__vision,
.showcase-evidence__metrics,
.showcase-evidence__safety {
  overflow: hidden;
}

.showcase-workspace__vision {
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr) auto auto;
}

.showcase-panel-heading {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--ov-border-subtle);
  min-height: 66px;
  padding: 12px 14px;
}

.showcase-panel-heading > div {
  display: grid;
  gap: 3px;
}

.showcase-panel-heading strong {
  color: var(--ov-text);
  font-size: 16px;
  line-height: 1.3;
}

.showcase-panel-heading > small {
  flex: 0 0 auto;
  border: 1px solid var(--ov-border);
  border-radius: 4px;
  padding: 4px 7px;
  color: var(--ov-text-secondary);
  font-size: 11px;
  font-weight: 700;
}

.showcase-panel-heading > :deep(.app-icon) {
  width: 24px;
  height: 24px;
  color: var(--ov-primary-strong);
}

.showcase-planning-snapshot {
  border-bottom: 1px solid var(--ov-border-subtle);
  background: var(--ov-bg-soft);
}

.showcase-planning-snapshot > header {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--ov-border-subtle);
  padding: 10px 14px;
}

.showcase-planning-snapshot > header > div,
.showcase-planning-snapshot__detail > div {
  display: grid;
  gap: 3px;
}

.showcase-planning-snapshot > header span,
.showcase-planning-snapshot__detail > div > span {
  color: var(--ov-primary-strong);
  font-size: 11px;
  font-weight: 720;
  line-height: 1.35;
}

.showcase-planning-snapshot > header strong,
.showcase-planning-snapshot__detail > div > strong {
  color: var(--ov-text);
  font-size: 14px;
  line-height: 1.4;
}

.showcase-planning-snapshot > header > small {
  color: var(--ov-text-muted);
  font-size: 11px;
  font-weight: 650;
  text-align: right;
}

.showcase-planning-snapshot__body {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(270px, 0.7fr);
  min-width: 0;
}

.showcase-planning-snapshot__rail {
  position: relative;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  align-items: stretch;
  min-width: 0;
}

.showcase-planning-snapshot__rail::before {
  position: absolute;
  top: 30px;
  right: 14%;
  left: 14%;
  height: 1px;
  background: var(--ov-border-strong);
  content: "";
}

.showcase-planning-snapshot__rail button {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: auto auto minmax(0, 1fr);
  gap: 7px;
  align-content: start;
  align-items: center;
  min-height: 84px;
  border: 0;
  border-bottom: 3px solid var(--ov-primary-strong);
  padding: 10px 8px 8px;
  background: transparent;
  color: var(--ov-text);
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.showcase-planning-snapshot__rail button.is-green {
  border-bottom-color: var(--ov-success);
}

.showcase-planning-snapshot__rail button.is-amber {
  border-bottom-color: var(--ov-warning);
}

.showcase-planning-snapshot__rail button:hover,
.showcase-planning-snapshot__rail button.is-active {
  background: var(--ov-bg-selected);
}

.showcase-planning-snapshot__rail button:focus-visible {
  outline: 2px solid var(--ov-border-accent);
  outline-offset: -2px;
}

.showcase-planning-snapshot__index {
  align-self: start;
  color: var(--ov-text-muted);
  font-size: 10px;
  font-weight: 780;
  line-height: 1.4;
}

.showcase-planning-snapshot__rail :deep(.app-icon) {
  display: grid;
  width: 27px;
  height: 27px;
  place-items: center;
  border: 1px solid var(--ov-border-accent);
  border-radius: 50%;
  padding: 5px;
  background: var(--ov-bg-elevated);
  color: var(--ov-primary-strong);
}

.showcase-planning-snapshot__rail button.is-green :deep(.app-icon) {
  border-color: color-mix(in srgb, var(--ov-success) 45%, var(--ov-border));
  color: var(--ov-success);
}

.showcase-planning-snapshot__rail button.is-amber :deep(.app-icon) {
  border-color: color-mix(in srgb, var(--ov-warning) 45%, var(--ov-border));
  color: var(--ov-warning);
}

.showcase-planning-snapshot__rail button > span:last-child {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.showcase-planning-snapshot__rail strong,
.showcase-planning-snapshot__rail small {
  min-width: 0;
  overflow-wrap: anywhere;
}

.showcase-planning-snapshot__rail strong {
  color: var(--ov-text);
  font-size: 12px;
  line-height: 1.35;
}

.showcase-planning-snapshot__rail small {
  color: var(--ov-text-muted);
  font-size: 10px;
  font-weight: 650;
  line-height: 1.35;
}

.showcase-planning-snapshot__detail {
  display: grid;
  gap: 6px;
  min-width: 0;
  border-left: 1px solid var(--ov-border-subtle);
  padding: 10px 12px;
  background: var(--ov-bg-elevated);
}

.showcase-planning-snapshot__detail small,
.showcase-planning-snapshot__detail dt,
.showcase-planning-snapshot__detail dd {
  min-width: 0;
  margin: 0;
  overflow-wrap: anywhere;
}

.showcase-planning-snapshot__detail dl {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
  margin: 0;
}

.showcase-planning-snapshot__detail dl div {
  display: grid;
  gap: 2px;
  border-top: 1px solid var(--ov-border-subtle);
  padding-top: 6px;
}

.showcase-planning-snapshot__detail dt {
  color: var(--ov-text-muted);
  font-size: 10px;
}

.showcase-planning-snapshot__detail dd {
  color: var(--ov-text);
  font-size: 11px;
  font-weight: 680;
  line-height: 1.4;
}

.showcase-workspace__anatomy {
  border: 0;
  border-radius: 0;
}

.showcase-source-note {
  margin: 0;
  border-top: 1px solid var(--ov-border-subtle);
  padding: 8px 14px 10px;
  color: var(--ov-text-muted);
  font-size: 11px;
  line-height: 1.4;
}

.showcase-vision-tabs {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 4px;
  padding: 10px 12px 0;
}

.showcase-vision-tabs button {
  min-height: 34px;
  border: 1px solid var(--ov-border);
  border-radius: 5px;
  padding: 6px 8px;
  background: var(--ov-bg-control);
  color: var(--ov-text-secondary);
  font: inherit;
  font-size: 12px;
  font-weight: 680;
  cursor: pointer;
}

.showcase-vision-tabs button:hover,
.showcase-vision-tabs button.is-active {
  border-color: var(--ov-border-accent);
  background: var(--ov-bg-selected);
  color: var(--ov-primary);
}

.showcase-vision-frame {
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  gap: 6px;
  min-height: 0;
  margin: 10px 12px 0;
}

.showcase-vision-frame img {
  display: block;
  width: 100%;
  min-height: 0;
  height: 100%;
  border: 1px solid var(--ov-border-strong);
  border-radius: 6px;
  background: var(--ov-bg-media);
  object-fit: contain;
}

.showcase-vision-frame figcaption {
  min-height: 20px;
}

.showcase-vision-frame figcaption strong {
  color: var(--ov-text);
  font-size: 14px;
}

.showcase-vision-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
  margin: 10px 12px;
}

.showcase-vision-metrics div {
  display: grid;
  gap: 2px;
  min-height: 50px;
  border: 1px solid var(--ov-border-subtle);
  border-radius: 5px;
  padding: 9px 10px;
  background: var(--ov-bg-soft);
}

.showcase-vision-metrics dt {
  color: var(--ov-text-muted);
  font-size: 11px;
}

.showcase-vision-metrics dd {
  margin: 0;
  color: var(--ov-text);
  font-size: 12px;
  font-weight: 650;
  line-height: 1.4;
}

.showcase-evidence {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.showcase-validation {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.showcase-evidence > article,
.showcase-validation > article {
  min-height: 270px;
}

.showcase-evidence__metrics,
.showcase-evidence__safety {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
}

.showcase-validation__spatial,
.showcase-validation__review {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
}

.showcase-validation__spatial,
.showcase-validation__review {
  overflow: hidden;
}

.showcase-spatial-list {
  display: grid;
  grid-template-rows: repeat(3, minmax(0, 1fr));
  gap: 0;
  margin: 0;
  padding: 0 18px;
  list-style: none;
}

.showcase-spatial-list li {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  border-bottom: 1px solid var(--ov-border-subtle);
  padding: 8px 0;
}

.showcase-spatial-list li > span {
  display: grid;
  width: 32px;
  height: 28px;
  place-items: center;
  border: 1px solid var(--ov-border-accent);
  border-radius: 4px;
  background: var(--ov-bg-info);
  color: var(--ov-primary);
  font-size: 11px;
  font-weight: 780;
}

.showcase-spatial-list li > div {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.showcase-spatial-list strong,
.showcase-spatial-list small {
  min-width: 0;
  overflow-wrap: anywhere;
}

.showcase-spatial-list strong {
  color: var(--ov-text);
  font-size: 13px;
  line-height: 1.35;
}

.showcase-spatial-list em {
  max-width: 110px;
  border: 1px solid var(--ov-border);
  border-radius: 4px;
  padding: 4px 6px;
  color: var(--ov-text-secondary);
  font-size: 10px;
  font-style: normal;
  font-weight: 700;
  line-height: 1.35;
  text-align: center;
}

.showcase-spatial-list em.is-cyan {
  border-color: var(--ov-border-accent);
  background: var(--ov-bg-info);
  color: var(--ov-primary);
}

.showcase-spatial-list em.is-green {
  border-color: color-mix(in srgb, var(--ov-success) 45%, var(--ov-border));
  background: var(--ov-bg-success);
  color: var(--ov-success);
}

.showcase-spatial-list em.is-amber {
  border-color: color-mix(in srgb, var(--ov-warning) 45%, var(--ov-border));
  background: var(--ov-bg-warning);
  color: var(--ov-warning);
}

.showcase-review-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  grid-template-rows: repeat(2, minmax(0, 1fr));
  gap: 6px;
  margin: 0;
  padding: 12px 14px;
}

.showcase-review-grid div {
  display: grid;
  gap: 2px;
  min-height: 68px;
  border: 1px solid var(--ov-border-subtle);
  border-top: 3px solid var(--ov-primary-strong);
  border-radius: 5px;
  padding: 11px 12px;
  background: var(--ov-bg-soft);
}

.showcase-review-grid dt,
.showcase-review-grid dd,
.showcase-review-grid small {
  min-width: 0;
  margin: 0;
  overflow-wrap: anywhere;
}

.showcase-review-grid dt {
  color: var(--ov-text-muted);
  font-size: 11px;
  line-height: 1.35;
}

.showcase-review-grid dd {
  color: var(--ov-text);
  font-size: 14px;
  font-weight: 720;
  line-height: 1.35;
}

.showcase-metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 6px;
  padding: 12px 14px;
  align-items: stretch;
}

.showcase-metric-grid div {
  display: grid;
  gap: 3px;
  min-height: 76px;
  border: 1px solid var(--ov-border-subtle);
  border-top: 3px solid var(--ov-primary-strong);
  border-radius: 5px;
  padding: 13px;
  background: var(--ov-bg-soft);
}

.showcase-metric-grid div.is-green {
  border-top-color: var(--ov-success);
}

.showcase-metric-grid div.is-amber {
  border-top-color: var(--ov-warning);
}

.showcase-metric-grid span {
  color: var(--ov-text-muted);
  font-size: 12px;
  line-height: 1.45;
}

.showcase-metric-grid strong {
  color: var(--ov-text);
  font-size: 22px;
  line-height: 1.1;
}

.showcase-safety-list {
  display: grid;
  grid-template-rows: repeat(3, minmax(0, 1fr));
  gap: 0;
  margin: 0;
  padding: 0 14px 4px;
  list-style: none;
}

.showcase-safety-list li {
  display: grid;
  grid-template-columns: 26px minmax(0, 1fr);
  gap: 10px;
  align-items: start;
  border-bottom: 1px solid var(--ov-border-subtle);
  padding: 8px 0;
}

.showcase-safety-list li:last-child {
  border-bottom: 0;
}

.showcase-safety-list li > span {
  display: grid;
  width: 26px;
  height: 26px;
  place-items: center;
  border-radius: 50%;
  background: var(--ov-bg-info);
  color: var(--ov-primary);
  font-size: 12px;
  font-weight: 760;
}

.showcase-safety-list li > span.is-green {
  background: var(--ov-bg-success);
  color: var(--ov-success);
}

.showcase-safety-list li > span.is-amber {
  background: var(--ov-bg-warning);
  color: var(--ov-warning);
}

.showcase-safety-list li > div {
  display: grid;
  gap: 3px;
}

.showcase-safety-list strong {
  color: var(--ov-text);
  font-size: 14px;
}

@media (max-width: 1280px) {
  .showcase-workspace,
  .showcase-evidence,
  .showcase-validation {
    grid-template-columns: 1fr;
  }

  .showcase-workspace__three-d {
    min-width: 0;
  }
}

@media (max-width: 1360px) {
  .showcase-flow {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .showcase-planning-snapshot__body {
    grid-template-columns: 1fr;
  }

  .showcase-planning-snapshot__detail {
    border-top: 1px solid var(--ov-border-subtle);
    border-left: 0;
  }
}

@media (max-width: 980px) {
  .showcase-page__header,
  .showcase-flow,
  .showcase-metric-grid {
    grid-template-columns: 1fr;
  }

  .showcase-review-grid {
    grid-template-columns: 1fr;
  }

  .showcase-page__actions {
    justify-content: flex-start;
  }
}
</style>
