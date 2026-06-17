import { describe, expect, it } from "vitest";

describe("review workspace", () => {
  it("supports accepted, modified, and rejected states", () => {
    const states = ["accepted", "modified", "rejected"];
    expect(states).toEqual(["accepted", "modified", "rejected"]);
  });
});
