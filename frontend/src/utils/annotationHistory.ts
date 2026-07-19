import type { AnnotationOperation } from "@/types/annotation";

export const ANNOTATION_HISTORY_LIMIT = 100;

// Completed operations are immutable, so command history can share point arrays safely.
export type AnnotationHistoryEntry =
  | { kind: "append"; operation: AnnotationOperation }
  | { kind: "clear"; previousOperations: AnnotationOperation[] };

export interface AnnotationHistoryChange {
  operations: AnnotationOperation[];
  entry: AnnotationHistoryEntry;
}

export function appendAnnotationOperation(
  operations: AnnotationOperation[],
  operation: AnnotationOperation,
): AnnotationHistoryChange {
  return {
    operations: [...operations, operation],
    entry: { kind: "append", operation },
  };
}

export function clearAnnotationOperations(operations: AnnotationOperation[]): AnnotationHistoryChange {
  return {
    operations: [],
    entry: { kind: "clear", previousOperations: operations },
  };
}

export function undoAnnotationEntry(
  operations: AnnotationOperation[],
  entry: AnnotationHistoryEntry,
): AnnotationOperation[] {
  if (entry.kind === "clear") return entry.previousOperations;
  return operations.slice(0, -1);
}

export function redoAnnotationEntry(
  operations: AnnotationOperation[],
  entry: AnnotationHistoryEntry,
): AnnotationOperation[] {
  if (entry.kind === "clear") return [];
  return [...operations, entry.operation];
}

export function appendBoundedHistory(
  history: readonly AnnotationHistoryEntry[],
  entry: AnnotationHistoryEntry,
  limit = ANNOTATION_HISTORY_LIMIT,
): AnnotationHistoryEntry[] {
  const capacity = Math.max(1, Math.floor(limit));
  const retained = history.slice(Math.max(0, history.length - capacity + 1));
  return [...retained, entry];
}
