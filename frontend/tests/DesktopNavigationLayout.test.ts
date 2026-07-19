import fs from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

describe("desktop navigation layout", () => {
  it("wraps the full clinical navigation at narrower workstation widths", () => {
    const source = fs.readFileSync(path.resolve(process.cwd(), "src/App.vue"), "utf8");
    const workstationRule = source.match(/@media \(max-width: 1120px\) \{([\s\S]*?)\n\}/)?.[1] ?? "";

    expect(workstationRule).toContain("flex-wrap: wrap");
    expect(workstationRule).toContain("grid-template-columns: repeat(auto-fit, minmax(146px, 1fr))");
    expect(source).not.toContain("@media (min-width: 861px) and (max-width: 1120px)");
  });
});
