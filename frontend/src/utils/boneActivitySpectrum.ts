interface FrameSelection {
  key?: string | null;
  frameIndex?: number | null;
}

function record(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function spectrumWithin(value: unknown): Record<string, unknown> | null {
  const node = record(value);
  if (!node) return null;
  const direct = record(node.bone_activity_spectrum);
  if (direct) return direct;
  for (const key of ["video_signal_segmentation", "signal_masks", "lesion_evidence", "segmentation_mask"]) {
    const nested = record(node[key]);
    if (!nested) continue;
    const found = spectrumWithin(nested);
    if (found) return found;
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
    if (Array.isArray(values)) collections.push(values.map(record).filter((item): item is Record<string, unknown> => Boolean(item)));
  }
  const outputs = record(fusedOutputs.outputs);
  if (outputs) {
    for (const key of ["frame_details", "hotspot_outputs", "frames", "keyframes"]) {
      const values = outputs[key];
      if (Array.isArray(values)) collections.push(values.map(record).filter((item): item is Record<string, unknown> => Boolean(item)));
    }
  }
  return collections;
}

/** Selects activity evidence bound to the active frame and never falls through to another frame. */
export function boneActivitySpectrumForFrame(
  runValue: unknown,
  selection: FrameSelection,
): Record<string, unknown> | null {
  const run = record(runValue);
  if (!run) return null;
  const hasSelection = Boolean(selection.key?.trim()) || selection.frameIndex !== null && selection.frameIndex !== undefined;
  const collections = frameCollections(run);

  if (hasSelection) {
    for (const frames of collections) {
      const matched = frames.find((frame, index) => frameMatches(frame, index, selection));
      if (matched) return spectrumWithin(matched);
    }
    return null;
  }

  const fusedOutputs = record(run.fused_outputs);
  return spectrumWithin(fusedOutputs) ?? spectrumWithin(run);
}
