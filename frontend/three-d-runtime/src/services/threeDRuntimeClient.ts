import type { ThreeDRuntimeSnapshot } from "../types";

const API_BASE_URL = import.meta.env.VITE_OSTEO_API_URL?.trim() || "http://127.0.0.1:8001";
export const THREE_D_RUNTIME_SNAPSHOT_SCHEMA = "osteo-vision-three-d-runtime-snapshot-v2";

export class ThreeDRuntimeApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ThreeDRuntimeApiError";
  }
}

export async function fetchCaseSnapshot(caseId: string): Promise<ThreeDRuntimeSnapshot> {
  return fetchSnapshot(`/three-d-runtime/v1/cases/${encodeURIComponent(caseId)}/snapshot`);
}

export async function fetchReferenceSnapshot(referenceId: string): Promise<ThreeDRuntimeSnapshot> {
  return fetchSnapshot(`/three-d-runtime/v1/references/${encodeURIComponent(referenceId)}/snapshot`);
}

export function resolveAssetUrl(assetUrl: string): string {
  if (/^https?:\/\//i.test(assetUrl)) return assetUrl;
  return `${API_BASE_URL}${assetUrl.startsWith("/") ? assetUrl : `/${assetUrl}`}`;
}

async function fetchSnapshot(path: string): Promise<ThreeDRuntimeSnapshot> {
  const response = await fetch(`${API_BASE_URL}${path}`, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = typeof payload?.detail === "string" ? payload.detail : "三维运行时快照读取失败";
    throw new ThreeDRuntimeApiError(response.status, detail);
  }
  const raw = await response.text();
  let snapshot: ThreeDRuntimeSnapshot;
  try {
    snapshot = JSON.parse(raw) as ThreeDRuntimeSnapshot;
  } catch {
    throw new ThreeDRuntimeApiError(502, "三维运行时快照不是有效 JSON。");
  }
  await verifySnapshot(snapshot);
  return snapshot;
}

export async function snapshotSha256(snapshot: Omit<ThreeDRuntimeSnapshot, "snapshot_sha256">): Promise<string> {
  if (!globalThis.crypto?.subtle) {
    throw new ThreeDRuntimeApiError(503, "浏览器未提供 SubtleCrypto，无法验证三维场景快照。");
  }
  const digest = await globalThis.crypto.subtle.digest(
    "SHA-256",
    canonicalSnapshotBytes(snapshot) as unknown as BufferSource,
  );
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function verifySnapshot(snapshot: ThreeDRuntimeSnapshot): Promise<void> {
  if (snapshot.schema_version !== THREE_D_RUNTIME_SNAPSHOT_SCHEMA) {
    throw new ThreeDRuntimeApiError(409, "三维运行时快照版本不受支持，已拒绝载入。");
  }
  if (!snapshot.snapshot_sha256 || !/^[a-f0-9]{64}$/i.test(snapshot.snapshot_sha256)) {
    throw new ThreeDRuntimeApiError(409, "三维运行时快照缺少有效 SHA256，已拒绝载入。");
  }
  const { snapshot_sha256: expectedSha256, ...unsigned } = snapshot;
  const actualSha256 = await snapshotSha256(unsigned);
  if (actualSha256.toLowerCase() !== expectedSha256.toLowerCase()) {
    throw new ThreeDRuntimeApiError(409, "三维运行时快照 SHA256 不一致，已拒绝载入。");
  }
}

function canonicalSnapshotBytes(value: unknown): Uint8Array {
  const encoder = new TextEncoder();
  const chunks: Uint8Array[] = [];

  const appendText = (text: string) => chunks.push(encoder.encode(text));
  const appendString = (text: string) => {
    const encoded = encoder.encode(text);
    appendText(`s${encoded.byteLength}:`);
    chunks.push(encoded);
  };
  const appendNumber = (number: number) => {
    if (!Number.isFinite(number)) {
      throw new ThreeDRuntimeApiError(409, "三维场景快照包含非有限数值，已拒绝载入。");
    }
    const buffer = new ArrayBuffer(8);
    const view = new DataView(buffer);
    view.setFloat64(0, number, false);
    const hex = Array.from(new Uint8Array(buffer), (byte) => byte.toString(16).padStart(2, "0")).join("");
    appendText(`d${hex};`);
  };
  const appendValue = (item: unknown): void => {
    if (item === null) {
      appendText("n;");
      return;
    }
    if (typeof item === "boolean") {
      appendText(item ? "b1;" : "b0;");
      return;
    }
    if (typeof item === "number") {
      appendNumber(item);
      return;
    }
    if (typeof item === "string") {
      appendString(item);
      return;
    }
    if (Array.isArray(item)) {
      appendText(`a${item.length}[`);
      item.forEach(appendValue);
      appendText("]");
      return;
    }
    if (item && typeof item === "object") {
      const record = item as Record<string, unknown>;
      const keys = Object.keys(record).sort(compareUtf8);
      appendText(`o${keys.length}{`);
      keys.forEach((key) => {
        appendString(key);
        appendValue(record[key]);
      });
      appendText("}");
      return;
    }
    throw new ThreeDRuntimeApiError(409, "三维场景快照包含不受支持的值类型，已拒绝载入。");
  };

  appendValue(value);
  return concatChunks(chunks);
}

function compareUtf8(left: string, right: string): number {
  const leftBytes = new TextEncoder().encode(left);
  const rightBytes = new TextEncoder().encode(right);
  const sharedLength = Math.min(leftBytes.length, rightBytes.length);
  for (let index = 0; index < sharedLength; index += 1) {
    if (leftBytes[index] !== rightBytes[index]) return leftBytes[index] - rightBytes[index];
  }
  return leftBytes.length - rightBytes.length;
}

function concatChunks(chunks: Uint8Array[]): Uint8Array {
  const length = chunks.reduce((total, chunk) => total + chunk.byteLength, 0);
  const result = new Uint8Array(length);
  let offset = 0;
  chunks.forEach((chunk) => {
    result.set(chunk, offset);
    offset += chunk.byteLength;
  });
  return result;
}
