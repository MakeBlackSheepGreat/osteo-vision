const artifactLabels: Record<string, string> = {
  report_json: "JSON 报告",
  report_md: "Markdown 报告",
  dicom_secondary_capture: "DICOM 二次捕获",
  quantification_csv: "量化 CSV",
  evidence_bundle: "证据包 ZIP",
  bundle_manifest: "证据包清单",
  overlay: "融合图",
  video_overlay: "分割叠加视频",
  video_mask: "分割掩膜视频",
  video_segmentation_manifest: "MP4 分割清单",
  probability_map: "概率图",
  heatmap: "热图",
  colorbar: "荧光色标",
  roi_mask: "ROI 掩膜",
};

export function artifactKindLabel(kind: string): string {
  return artifactLabels[kind] ?? kind;
}

export function formatArtifactBytes(value: unknown): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "暂无";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(2)} MB`;
}

