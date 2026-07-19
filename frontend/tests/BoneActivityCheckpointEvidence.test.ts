import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import BoneActivityCheckpointEvidencePanel from "@/components/BoneActivityCheckpointEvidencePanel.vue";
import { boneActivityCheckpointEvidenceForFrame } from "@/utils/boneActivityCheckpointEvidence";

const CHECKPOINT_SHA = "a".repeat(64);
const MANIFEST_SHA = "b".repeat(64);
const NPZ_SHA = "c".repeat(64);
const EVIDENCE_SHA = "d".repeat(64);

describe("BoneActivityCheckpointEvidencePanel", () => {
  it("shows checksum-bound proxy evidence while keeping every spatial output closed", () => {
    const wrapper = mount(BoneActivityCheckpointEvidencePanel, {
      props: {
        evidence: {
          schema_version: "osteo-vision-bone-activity-runtime-evidence-v1",
          model_id: "bone_activity_multitask_d074_proxy_candidate",
          engineering_inference_executed: true,
          spatial_candidates_available: false,
          spatial_effect_applied: false,
          proxy_checkpoint: true,
          runtime_replacement_allowed: false,
          training_domain: {
            target_domain: false,
            dataset_id: "D074-open-bone-fluorescence-proxy",
          },
          checkpoint_sha256: CHECKPOINT_SHA,
          manifest_sha256: MANIFEST_SHA,
          raw_engineering_outputs: {
            available: true,
            spatial_use_allowed: false,
            path: "artifacts/bone/raw_engineering_outputs.npz",
            sha256: NPZ_SHA,
          },
          evidence_manifest_path: "artifacts/bone/evidence.json",
          evidence_manifest_sha256: EVIDENCE_SHA,
          failure_reasons: [
            "non_target_domain_proxy",
            "dual_channel_registration_not_verified",
            "target_domain_input_not_verified",
          ],
          medical_boundary: "Bone-activity outputs remain research validation evidence requiring physician review.",
        },
        downloadUrl: (path: string) => `/download?path=${encodeURIComponent(path)}`,
      },
    });

    expect(wrapper.text()).toContain("骨活性 checkpoint 工程证据");
    expect(wrapper.text()).toContain("bone_activity_multitask_d074_proxy_candidate");
    expect(wrapper.text()).toContain("工程证据已生成");
    expect(wrapper.text()).toContain("已执行并保存证据");
    expect(wrapper.text()).toContain("非目标域代理 · D074-open-bone-fluorescence-proxy");
    expect(wrapper.text()).toContain("禁止替换比赛主线");
    expect(wrapper.text()).toContain(CHECKPOINT_SHA);
    expect(wrapper.text()).toContain(MANIFEST_SHA);
    expect(wrapper.text()).toContain(NPZ_SHA);
    expect(wrapper.text()).toContain(EVIDENCE_SHA);
    expect(wrapper.get('[data-testid="raw-npz-download"]').attributes("href")).toContain("raw_engineering_outputs.npz");
    expect(wrapper.get('[data-testid="evidence-json-download"]').attributes("href")).toContain("evidence.json");
    expect(wrapper.text()).toContain("当前 checkpoint 来源于非目标域代理数据");
    expect(wrapper.text()).toContain("白光与荧光配准证据未通过核验");
    expect(wrapper.text()).toContain("当前输入尚未通过目标域数据准入");
    expect(wrapper.text()).toContain("空间输出已关闭");
    expect(wrapper.text()).toContain("未生成低活性、过渡、高活性空间候选、面积比例或连续评分图层");
    expect(wrapper.text()).toContain("原始 NPZ 禁止直接用于空间判读");
    expect(wrapper.text()).toContain("骨活性输出仅作为研发验证证据，必须由医生复核");
    expect(wrapper.text()).toContain("不得作为诊断、切除范围或切除成功率依据");
    expect(wrapper.find("img").exists()).toBe(false);
  });

  it("fails closed without exposing download actions for missing artifacts", () => {
    const wrapper = mount(BoneActivityCheckpointEvidencePanel, {
      props: {
        evidence: {
          model_family: "dual_channel_bone_activity_multitask",
          engineering_inference_executed: false,
          spatial_candidates_available: false,
          proxy_checkpoint: true,
          failure_reasons: ["bone_activity_inference_failed"],
        },
        downloadUrl: (path: string) => `/download/${path}`,
      },
    });

    expect(wrapper.text()).toContain("安全关闭");
    expect(wrapper.text()).toContain("未执行或执行失败");
    expect(wrapper.text()).toContain("骨活性 checkpoint 工程推理失败");
    expect(wrapper.findAll("a")).toHaveLength(0);
  });

  it("shows the persisted input-domain fallback for proxy runs", () => {
    const wrapper = mount(BoneActivityCheckpointEvidencePanel, {
      props: {
        evidence: {
          engineering_inference_executed: true,
          spatial_candidates_available: false,
          proxy_checkpoint: true,
          input_domain: "D074 public fluorescence proxy",
        },
      },
    });

    expect(wrapper.text()).toContain("非目标域代理 · D074 public fluorescence proxy");
  });

  it("keeps promoted spatial candidates under physician review language", () => {
    const wrapper = mount(BoneActivityCheckpointEvidencePanel, {
      props: {
        evidence: {
          engineering_inference_executed: true,
          spatial_candidates_available: true,
          spatial_effect_applied: true,
          proxy_checkpoint: false,
          runtime_replacement_allowed: true,
          training_domain: { target_domain: true, dataset_ids: ["target-cohort-v1"] },
        },
      },
    });

    expect(wrapper.text()).toContain("医生复核候选已生成");
    expect(wrapper.text()).toContain("目标域 · target-cohort-v1");
    expect(wrapper.text()).toContain("空间候选等待医生复核");
    expect(wrapper.text()).toContain("仅作为医生复核图层");
  });
});

describe("boneActivityCheckpointEvidenceForFrame", () => {
  const evidence = (id: string) => ({
    schema_version: "osteo-vision-bone-activity-runtime-evidence-v1",
    evidence_id: id,
  });

  it("selects checkpoint evidence only from the active video frame", () => {
    const run = {
      fused_outputs: {
        mode: "video_file_keyframes",
        frame_details: [
          { frame_index: 4, bone_activity_checkpoint_evidence: evidence("frame-4") },
          { frame_index: 8, outputs: { bone_activity_checkpoint_evidence: evidence("frame-8") } },
        ],
      },
    };

    expect(boneActivityCheckpointEvidenceForFrame(run, { frameIndex: 8 })?.evidence_id).toBe("frame-8");
    expect(boneActivityCheckpointEvidenceForFrame(run, { frameIndex: 9 })).toBeNull();
  });

  it("reads run-level JPEG evidence from the nested outputs contract", () => {
    const run = {
      fused_outputs: {
        mode: "image_pair",
        outputs: { checkpoint_engineering_evidence: evidence("jpeg-run") },
      },
    };

    expect(boneActivityCheckpointEvidenceForFrame(run, {})?.evidence_id).toBe("jpeg-run");
    expect(boneActivityCheckpointEvidenceForFrame(run, { frameIndex: 1 })?.evidence_id).toBe("jpeg-run");
  });
});
