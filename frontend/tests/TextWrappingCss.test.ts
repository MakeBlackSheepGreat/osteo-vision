import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const sourceRoots = ["src/components", "src/pages", "src/styles"];
const forbiddenTextClippingPatterns = [
  /text-overflow\s*:\s*ellipsis/i,
  /white-space\s*:\s*nowrap/i,
  /-webkit-line-clamp\s*:/i,
  /line-clamp\s*:/i,
  /compactPath\s*\(/,
];

function listVueAndCssFiles(root: string): string[] {
  const entries = readdirSync(root, { withFileTypes: true });
  return entries.flatMap((entry) => {
    const path = join(root, entry.name);
    if (entry.isDirectory()) return listVueAndCssFiles(path);
    if (entry.name.endsWith(".vue") || entry.name.endsWith(".css")) return [path];
    return [];
  });
}

describe("frontend text wrapping CSS", () => {
  it("does not use ellipsis, forced single-line, line-clamp, or path compaction in visible UI", () => {
    const files = sourceRoots.flatMap((root) => listVueAndCssFiles(join(process.cwd(), root)));
    const violations = files.flatMap((file) => {
      const content = readFileSync(file, "utf8");
      return forbiddenTextClippingPatterns
        .filter((pattern) => pattern.test(content))
        .map((pattern) => `${file.replace(`${process.cwd()}\\`, "")}: ${pattern.source}`);
    });

    expect(violations).toEqual([]);
  });
});
