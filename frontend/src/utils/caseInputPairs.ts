import type { CaseInputAsset } from "@/types/case";

export interface CaseImagePair {
  key: string;
  pairId: string;
  batchId: string;
  whiteLight: CaseInputAsset;
  fluorescence: CaseInputAsset;
  deviceOverlay?: CaseInputAsset;
}

export function caseImagePairs(inputs: CaseInputAsset[]): CaseImagePair[] {
  const groups = new Map<
    string,
    {
      pairId: string;
      batchId: string;
      whiteLight: CaseInputAsset[];
      fluorescence: CaseInputAsset[];
      deviceOverlay: CaseInputAsset[];
      lastIndex: number;
    }
  >();

  inputs.forEach((asset, index) => {
    if (!["white_light", "fluorescence", "device_overlay"].includes(asset.channel)) return;
    const pairId = metadataString(asset, "pair_id");
    if (!pairId) return;
    const batchId = metadataString(asset, "batch_id");
    const key = imagePairKey(batchId, pairId);
    const group = groups.get(key) ?? {
      pairId,
      batchId,
      whiteLight: [],
      fluorescence: [],
      deviceOverlay: [],
      lastIndex: index,
    };
    if (asset.channel === "white_light") group.whiteLight.push(asset);
    else if (asset.channel === "fluorescence") group.fluorescence.push(asset);
    else group.deviceOverlay.push(asset);
    group.lastIndex = index;
    groups.set(key, group);
  });

  return [...groups.entries()]
    .filter(([, group]) => group.whiteLight.length === 1 && group.fluorescence.length === 1)
    .sort(([, left], [, right]) => left.lastIndex - right.lastIndex)
    .map(([key, group]) => ({
      key,
      pairId: group.pairId,
      batchId: group.batchId,
      whiteLight: group.whiteLight[0],
      fluorescence: group.fluorescence[0],
      deviceOverlay: group.deviceOverlay.at(-1),
    }));
}

export function selectedImageInputIds(
  inputs: CaseInputAsset[],
  whiteLightPath: string,
  fluorescencePath: string,
  deviceOverlayPath = "",
): string[] {
  const whiteLight = findLatestInput(inputs, "white_light", whiteLightPath);
  const fluorescence = findLatestInput(inputs, "fluorescence", fluorescencePath);
  if (!whiteLight || !fluorescence) return [];

  const whitePairId = metadataString(whiteLight, "pair_id");
  const fluorescencePairId = metadataString(fluorescence, "pair_id");
  const whiteBatchId = metadataString(whiteLight, "batch_id");
  const fluorescenceBatchId = metadataString(fluorescence, "batch_id");
  const hasPairMetadata = Boolean(whitePairId || fluorescencePairId);
  if (
    hasPairMetadata &&
    (!whitePairId ||
      !fluorescencePairId ||
      imagePairKey(whiteBatchId, whitePairId) !== imagePairKey(fluorescenceBatchId, fluorescencePairId))
  ) {
    return [];
  }
  const selected = [whiteLight.input_id, fluorescence.input_id];
  const overlay = findLatestInput(inputs, "device_overlay", deviceOverlayPath);
  if (overlay) selected.push(overlay.input_id);
  return selected;
}

export function imagePairLabel(pair: CaseImagePair): string {
  return pair.batchId ? `${pair.pairId} · 批次 ${pair.batchId}` : pair.pairId;
}

function findLatestInput(
  inputs: CaseInputAsset[],
  channel: "white_light" | "fluorescence" | "device_overlay",
  path: string,
): CaseInputAsset | undefined {
  return [...inputs].reverse().find((asset) => asset.channel === channel && asset.path === path);
}

function metadataString(asset: CaseInputAsset, key: string): string {
  const value = asset.metadata[key];
  return typeof value === "string" ? value.trim() : "";
}

function imagePairKey(batchId: string, pairId: string): string {
  return JSON.stringify([batchId, pairId]);
}
