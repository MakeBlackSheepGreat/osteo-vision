import { describe, expect, it } from "vitest";

import type { AnnotationOperation } from "../src/types/annotation";
import {
  ANNOTATION_HISTORY_LIMIT,
  appendAnnotationOperation,
  appendBoundedHistory,
  clearAnnotationOperations,
  redoAnnotationEntry,
  type AnnotationHistoryEntry,
  undoAnnotationEntry,
} from "../src/utils/annotationHistory";

describe("annotationHistory", () => {
  it("retains one structurally shared operation per append entry within the bounded history", () => {
    let operations: AnnotationOperation[] = [];
    let history: AnnotationHistoryEntry[] = [];

    for (let operationIndex = 0; operationIndex < ANNOTATION_HISTORY_LIMIT + 25; operationIndex += 1) {
      const operation: AnnotationOperation = {
        tool: "brush",
        mode: "add",
        radius: 21,
        points: Array.from({ length: 2_000 }, (_, pointIndex) => ({
          x: pointIndex,
          y: operationIndex,
        })),
      };
      const change = appendAnnotationOperation(operations, operation);
      operations = change.operations;
      history = appendBoundedHistory(history, change.entry);
    }

    expect(history).toHaveLength(ANNOTATION_HISTORY_LIMIT);
    expect(history.every((entry) => entry.kind === "append" && operations.includes(entry.operation))).toBe(true);
    expect(history.at(-1)?.kind).toBe("append");
    const latest = history.at(-1) as Extract<AnnotationHistoryEntry, { kind: "append" }>;
    expect(latest.operation).toBe(operations.at(-1));

    const undone = undoAnnotationEntry(operations, latest);
    expect(undone).toHaveLength(operations.length - 1);
    expect(undone[0]).toBe(operations[0]);
    const redone = redoAnnotationEntry(undone, latest);
    expect(redone.at(-1)).toBe(latest.operation);
  });

  it("stores a clear operation as one shared boundary snapshot and restores it losslessly", () => {
    const operations: AnnotationOperation[] = [
      { tool: "polygon", mode: "add", points: [{ x: 10, y: 12 }, { x: 20, y: 12 }, { x: 15, y: 24 }] },
      { tool: "eraser", mode: "erase", radius: 8, points: [{ x: 16, y: 16 }] },
    ];
    const change = clearAnnotationOperations(operations);
    expect(change.operations).toEqual([]);
    expect(change.entry.kind).toBe("clear");
    if (change.entry.kind !== "clear") throw new Error("expected clear history entry");
    expect(change.entry.previousOperations).toBe(operations);

    const restored = undoAnnotationEntry(change.operations, change.entry);
    expect(restored).toBe(operations);
    expect(redoAnnotationEntry(restored, change.entry)).toEqual([]);
  });
});
