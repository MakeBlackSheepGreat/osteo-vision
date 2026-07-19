import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import ReviewStateControls from "../src/components/ReviewStateControls.vue";

describe("review state controls", () => {
  it("requires an explicitly selected candidate before sending a review-state change", async () => {
    const wrapper = mount(ReviewStateControls, {
      props: {
        candidate: null,
      },
      global: {
        stubs: {
          SectionHeading: true,
        },
      },
    });

    expect(wrapper.text()).toContain("请先从候选区域中选择对象");
    expect(wrapper.findAll("button").every((button) => button.attributes("disabled") !== undefined)).toBe(true);

    await wrapper.setProps({
      candidate: {
        candidate_id: "candidate_review_001",
        run_id: "run_review_001",
        risk_type: "boundary_risk",
        status: "review_required",
        metadata: {},
      },
    });

    const acceptButton = wrapper.findAll("button")[0];
    expect(acceptButton.attributes("disabled")).toBeUndefined();
    await acceptButton.trigger("click");
    expect(wrapper.emitted("change")).toEqual([["accepted"]]);
  });

  it("locks all actions while the active review write is in progress", () => {
    const wrapper = mount(ReviewStateControls, {
      props: {
        disabled: true,
        candidate: {
          candidate_id: "candidate_review_001",
          run_id: "run_review_001",
          risk_type: "boundary_risk",
          status: "review_required",
          metadata: {},
        },
      },
      global: {
        stubs: {
          SectionHeading: true,
        },
      },
    });

    expect(wrapper.findAll("button").every((button) => button.attributes("disabled") !== undefined)).toBe(true);
    expect(wrapper.text()).toContain("当前复核对象");
  });
});
