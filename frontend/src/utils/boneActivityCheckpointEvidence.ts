interface FrameSelection {
  key?: string | null;
  frameIndex?: number | null;
}

function record(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function numericFrameIndex(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) return Number(value);
  return null;
}

function frameMatches(
  frame: Record<string, unknown>,
  arrayIndex: number,
  selection: FrameSelection,
): boolean {
  const selectedKey = selection.key?.trim() || "";
  const frameIndex = numericFrameIndex(frame.frame_index) ?? numericFrameIndex(frame.frame_order);
  const frameKey = typeof frame.frame_key === "string" ? frame.frame_key : "";
  const candidateId = typeof frame.candidate_id === "string" ? frame.candidate_id : "";
  const generatedKey = `${frameIndex ?? arrayIndex + 1}-${arrayIndex}`;
  if (selectedKey && [frameKey, candidateId, generatedKey].includes(selectedKey)) return true;
  return selection.frameIndex !== null
    && selection.frameIndex !== undefined
    && frameIndex === selection.frameIndex;
}

const evidenceKeys = [
  "bone_activity_checkpoint_evidence",
  "checkpoint_engineering_evidence",
  "bone_activity_runtime_evidence",
] as const;

function evidenceWithin(value: unknown): Record<string, unknown> | null {
  const node = record(value);
  if (!node) return null;
  if (String(node.schema_version || "").startsWith("osteo-vision-bone-activity-runtime-evidence")) {
    return node;
  }
  for (const key of evidenceKeys) {
    const direct = record(node[key]);
    if (direct) return direct;
  }
  for (const key of ["outputs", "video_signal_segmentation", "signal_masks", "lesion_evidence", "segmentation_mask"]) {
    const nested = evidenceWithin(node[key]);
    if (nested) return nested;
  }
  return null;
}

function frameCollections(run: Record<string, unknown>): Array<Array<Record<string, unknown>>> {
  const fusedOutputs = record(run.fused_outputs) ?? run;
  const collections: Array<Array<Record<string, unknown>>> = [];
  for (const key of ["frame_details", "hotspot_outputs", "frames", "keyframes"]) {
    const values = fusedOutputs[key];
    if (Array.isArray(values)) {
      collections.push(values.map(record).filter((item): item is Record<string, unknown> => Boolean(item)));
    }
  }
  const outputs = record(fusedOutputs.outputs);
  if (outputs) {
    for (const key of ["frame_details", "hotspot_outputs", "frames", "keyframes"]) {
      const values = outputs[key];
      if (Array.isArray(values)) {
        collections.push(values.map(record).filter((item): item is Record<string, unknown> => Boolean(item)));
      }
    }
  }
  return collections;
}

/** Selects checkpoint evidence for the active frame without borrowing evidence from another video frame. */
export function boneActivityCheckpointEvidenceForFrame(
  runValue: unknown,
  selection: FrameSelection,
): Record<string, unknown> | null {
  const run = record(runValue);
  if (!run) return null;
  const fusedOutputs = record(run.fused_outputs) ?? run;
  const hasSelection = Boolean(selection.key?.trim())
    || selection.frameIndex !== null && selection.frameIndex !== undefined;
  const collections = frameCollections(run);

  if (hasSelection) {
    for (const frames of collections) {
      const matched = frames.find((frame, index) => frameMatches(frame, index, selection));
      if (matched) return evidenceWithin(matched);
    }
    const mode = typeof fusedOutputs.mode === "string" ? fusedOutputs.mode : "";
    if (mode.includes("video") || collections.length > 0) return null;
  }

  return evidenceWithin(fusedOutputs) ?? evidenceWithin(run);
}
