from __future__ import annotations

from src.core.warnings import DISCLAIMER_TEXT

DISCLAIMER_VERSION = "platform-safety-v1"
LEGACY_DISCLAIMER_VERSION = "research-prototype-v1"  # 旧版本兼容：读取历史病例时保留识别能力，不作为本项目当前自称。

PLATFORM_SAFETY_DISCLAIMER = DISCLAIMER_TEXT

ICG_SIGNAL_LIMITATION = (
    "ICG fluorescence is treated as a perfusion, vascular permeability, and tissue-viability signal. "
    "It is not a jaw osteomyelitis-specific probe."
)

PROHIBITED_CLAIM_TERMS = (
    "automatic diagnosis",
    "definitive diagnosis",
    "definitive surgical instruction",
    "automatic resection boundary",
)


def disclaimer_context() -> dict[str, str]:
    return {
        "disclaimer_version": DISCLAIMER_VERSION,
        "disclaimer": PLATFORM_SAFETY_DISCLAIMER,
        "icg_signal_limitation": ICG_SIGNAL_LIMITATION,
    }
