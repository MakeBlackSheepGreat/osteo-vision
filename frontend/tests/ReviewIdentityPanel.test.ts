import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";

import ReviewIdentityPanel from "../src/components/ReviewIdentityPanel.vue";
import { clearReviewAccessToken } from "../src/services/apiClient";

const engineeringIdentity = {
  actor_id: "engineering-local-session",
  role: "engineering_reviewer",
  institution: "Osteo Vision Engineering",
  auth_source: "local_unverified_session",
  authenticated: false,
};

describe("ReviewIdentityPanel", () => {
  afterEach(() => {
    clearReviewAccessToken();
    vi.unstubAllGlobals();
  });

  it("marks an unauthenticated session as engineering review", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: async () => engineeringIdentity }),
    );
    const wrapper = mount(ReviewIdentityPanel);
    await flushPromises();

    expect(wrapper.text()).toContain("工程复核 · engineering-local-session");
    expect(wrapper.text()).toContain("不能记为医生签署");
  });

  it("uses the verified Bearer token for physician identity", async () => {
    const physicianIdentity = {
      actor_id: "doctor-zhang-001",
      role: "physician",
      institution: "Example Stomatology Hospital",
      auth_source: "verified_identity_token",
      authenticated: true,
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => engineeringIdentity })
      .mockResolvedValueOnce({ ok: true, json: async () => physicianIdentity });
    vi.stubGlobal("fetch", fetchMock);
    const wrapper = mount(ReviewIdentityPanel);
    await flushPromises();

    await wrapper.get('input[type="password"]').setValue("physician-review-token-001");
    await wrapper.get("form").trigger("submit");
    await flushPromises();

    const headers = fetchMock.mock.calls[1][1]?.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer physician-review-token-001");
    expect(wrapper.text()).toContain("医生复核 · doctor-zhang-001");
    expect(wrapper.text()).toContain("身份已由服务端令牌验证");
  });
});
