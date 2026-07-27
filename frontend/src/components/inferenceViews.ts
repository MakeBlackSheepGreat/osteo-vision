export type InferenceViewKey = "signal" | "risk" | "uncertainty";

export type InferenceViewSources = Partial<Record<InferenceViewKey, string>>;

export const inferenceViewOptions: Array<{
  key: InferenceViewKey;
  label: string;
  shortLabel: string;
  alt: string;
}> = [
  {
    key: "signal",
    label: "信号候选分割",
    shortLabel: "信号候选分割",
    alt: "当前帧荧光或灌注信号候选分割",
  },
  {
    key: "risk",
    label: "边界风险",
    shortLabel: "边界风险",
    alt: "当前帧边界风险提示",
  },
  {
    key: "uncertainty",
    label: "不确定区域",
    shortLabel: "不确定区域",
    alt: "当前帧低置信或质量受限区域",
  },
];
