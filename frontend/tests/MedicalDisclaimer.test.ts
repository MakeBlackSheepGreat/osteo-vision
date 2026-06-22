import { describe, expect, it } from "vitest";

describe("medical disclaimer wording", () => {
  it("keeps physician review boundary visible", () => {
    const text = "输出仅作为医生复核参考，不能替代临床诊断结论。";
    expect(text).toContain("医生复核");
    expect(text).toContain("不能替代临床诊断");
  });
});
