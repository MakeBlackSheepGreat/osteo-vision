interface FrameSelection {
  key?: string | null;
  frameIndex?: number | null;
}

function record(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function evidenceWithin(value: unknown): Record<string, unknown> | null {
  const node = record(value);
  if (!node) return null;
  const direct = record(node.patient_conditioning_evidence);
  if (direct) return direct;
  for (const key of ["video_signal_segmentation", "signal_masks", "lesion_evidence", "segmentation_mask"]) {
    const nested = evidenceWithin(node[key]);
    if (nested) return nested;
  }
  return null;
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

function frameCollections(run: Record<string, unknown>): Array<Array<Record<string, unknown>>> {
  const fusedOutputs = record(run.fused_outputs) ?? run;
  const collections: Array<Array<Record<string, unknown>>> = [];
  for (const key of ["frame_details", "hotspot_outputs", "frames", "keyframes"]) {
    const values = fusedOutputs[key];
    if (Array.isArray(values)) {
      collections.push(values.map(record).filter((item): item is Record<string, unknown> => Boolean(item)));
    }
  }
  return collections;
}

/** Keeps patient-conditioning evidence bound to the selected frame. */
export function patientConditioningEvidenceForFrame(
  runValue: unknown,
  selection: FrameSelection,
): Record<string, unknown> | null {
  const run = record(runValue);
  if (!run) return null;
  const hasSelection = Boolean(selection.key?.trim())
    || selection.frameIndex !== null && selection.frameIndex !== undefined;
  if (hasSelection) {
    for (const frames of frameCollections(run)) {
      const matched = frames.find((frame, index) => frameMatches(frame, index, selection));
      if (matched) return evidenceWithin(matched);
    }
    return null;
  }
  return evidenceWithin(record(run.fused_outputs)) ?? evidenceWithin(run);
}
