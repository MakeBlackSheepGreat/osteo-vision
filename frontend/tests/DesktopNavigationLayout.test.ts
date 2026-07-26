import fs from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

describe("desktop navigation layout", () => {
  it("uses the original persistent workstation top navigation", () => {
    const source = fs.readFileSync(path.resolve(process.cwd(), "src/App.vue"), "utf8");

    expect(source).toContain('class="app-top-nav"');
    expect(source).toContain('aria-label="顶部导航"');
    expect(source).toContain("<AppNavPills");
    expect(source).not.toContain("app-sidebar");
    expect(source).not.toContain("osteo-vision-sidebar-collapsed");
  });
});
