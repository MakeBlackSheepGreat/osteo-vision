import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

describe("case workspace live preview retention", () => {
  it("keeps right-side live result panels bound to the last displayable frame during the next inference", () => {
    const source = readFileSync(resolve(process.cwd(), "src/pages/CaseWorkspacePage.vue"), "utf8");

    expect(source).toContain("if (!result || !liveFrameIsDisplayable.value) return [];");
  });

  it("keeps file playback and browser camera state mutually exclusive", () => {
    const source = readFileSync(resolve(process.cwd(), "src/pages/CaseWorkspacePage.vue"), "utf8");

    expect(source).toContain('const videoInputSource = ref<"file" | "camera">("file");');
    expect(source).toContain(':video-playback="videoInputSource === \'file\' ? videoPlaybackAnalysis : null"');
    expect(source).toContain(':camera-stream="videoInputSource === \'camera\' ? cameraStream : null"');
    expect(source).toContain("analysisWorkspaceCardRef.value?.pausePlayback();");
    expect(source).toContain("stopCameraInput();");
  });
});
