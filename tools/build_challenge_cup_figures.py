"""Build traceable visual assets for the Challenge Cup software report draft."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "research" / "reports" / "submission" / "challenge_cup_report_draft_20260721" / "assets"
SOURCE_ASSET_DIR = OUTPUT_DIR / "sources"
FONT_REGULAR = Path(r"C:\Windows\Fonts\msyh.ttc")
FONT_BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")
D083_TIMELINE_MANIFEST = SOURCE_ASSET_DIR / "d083_frame_details_manifest.json"
D083_PANEL_SOURCES = (
    SOURCE_ASSET_DIR / "d083_frame_05_raw.jpg",
    SOURCE_ASSET_DIR / "d083_frame_05_overlay.png",
    SOURCE_ASSET_DIR / "d083_frame_05_risk.png",
    SOURCE_ASSET_DIR / "d083_frame_05_uncertainty.png",
)
COMPETITION_4K_INPUTS = (
    SOURCE_ASSET_DIR / "competition_white_4k.jpg",
    SOURCE_ASSET_DIR / "competition_icg_4k.jpg",
)
D074_PROXY_REPORT = SOURCE_ASSET_DIR / "bone_activity_multitask_d074_proxy_20260719.json"
SHOWCASE_SCREENSHOT = SOURCE_ASSET_DIR / "challenge_cup_showcase_20260722.png"
RUNTIME_4K_REPORT = (
    ROOT / "research" / "reports" / "modeling" / "keyframe_residual_attention_4k_runtime_gate_20260715_zh.md"
)
RUNTIME_LIVE_REPORT = (
    ROOT / "research" / "reports" / "modeling" / "keyframe_residual_attention_live_fast_runtime_gate_20260715_zh.md"
)

CANVAS = (2200, 1240)
INK = "#193542"
MUTED = "#5E7480"
PAPER = "#F8FBFC"
LINE = "#C7D6DB"
TEAL = "#007C7A"
TEAL_LIGHT = "#E2F2F0"
CYAN = "#087FAE"
CYAN_LIGHT = "#E4F3F8"
GREEN = "#27775E"
GREEN_LIGHT = "#E4F1EB"
AMBER = "#A86E13"
AMBER_LIGHT = "#FFF2DB"
RED = "#B64A45"
RED_LIGHT = "#FBE9E7"


@lru_cache(maxsize=None)
def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    font_path = FONT_BOLD if bold else FONT_REGULAR
    return ImageFont.truetype(str(font_path), size=size)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def new_canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", CANVAS, PAPER)
    return image, ImageDraw.Draw(image)


def rounded(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    *,
    fill: str,
    outline: str = LINE,
    width: int = 3,
    radius: int = 24,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    value: str,
    *,
    size: int = 34,
    color: str = INK,
    bold: bool = False,
    anchor: str = "la",
) -> None:
    draw.text(xy, value, font=font(size, bold=bold), fill=color, anchor=anchor)


def wrapped_lines(value: str, max_width: int, text_font: ImageFont.FreeTypeFont) -> list[str]:
    lines: list[str] = []
    current = ""
    for character in value:
        candidate = current + character
        if current and text_font.getlength(candidate) > max_width:
            lines.append(current)
            current = character
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def wrapped(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    value: str,
    *,
    width: int,
    size: int = 28,
    color: str = INK,
    bold: bool = False,
    spacing: int = 12,
) -> int:
    text_font = font(size, bold=bold)
    y = xy[1]
    for line in wrapped_lines(value, width, text_font):
        draw.text((xy[0], y), line, font=text_font, fill=color)
        y += size + spacing
    return y


def arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    color: str = TEAL,
    width: int = 8,
) -> None:
    draw.line((start, end), fill=color, width=width)
    x1, y1 = end
    draw.polygon([(x1, y1), (x1 - 20, y1 - 14), (x1 - 20, y1 + 14)], fill=color)


def title(draw: ImageDraw.ImageDraw, number: str, heading: str, subtitle: str) -> None:
    text(draw, (90, 76), number, size=26, color=TEAL, bold=True)
    text(draw, (90, 124), heading, size=58, color=INK, bold=True)
    text(draw, (90, 204), subtitle, size=29, color=MUTED)
    draw.line((90, 264, CANVAS[0] - 90, 264), fill=LINE, width=3)


def footer(draw: ImageDraw.ImageDraw, label: str) -> None:
    draw.line((90, CANVAS[1] - 100, CANVAS[0] - 90, CANVAS[1] - 100), fill=LINE, width=2)
    text(draw, (90, CANVAS[1] - 58), label, size=23, color=MUTED)


def step_card(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    *,
    index: str,
    heading: str,
    detail: str,
    fill: str,
    accent: str,
) -> None:
    rounded(draw, box, fill=fill, outline=accent, width=4)
    x1, y1, x2, _ = box
    draw.ellipse((x1 + 34, y1 + 34, x1 + 110, y1 + 110), fill=accent)
    text(draw, (x1 + 72, y1 + 72), index, size=27, color="white", bold=True, anchor="mm")
    text(draw, (x1 + 138, y1 + 34), heading, size=34, color=INK, bold=True)
    wrapped(
        draw,
        (x1 + 138, y1 + 90),
        detail,
        width=x2 - x1 - 174,
        size=25,
        color=MUTED,
        spacing=8,
    )


def build_architecture(path: Path) -> None:
    image, draw = new_canvas()
    title(
        draw,
        "FIG 2",
        "荧光-三维证据闭环平台总体架构",
        "从赛题方文件输入到医生复核与可追溯证据输出的工程工作流",
    )

    cards = [
        (
            "01",
            "4K 多源输入",
            "JPEG 原彩图、原始荧光图与可选设备叠加图；MP4 视频、离线元数据和 CBCT/STL 参考。",
            CYAN_LIGHT,
            CYAN,
        ),
        (
            "02",
            "荧光融合与量化",
            "通道校验、配准、背景扣除、归一化、伪彩、ROI 定量与三通道质控。",
            TEAL_LIGHT,
            TEAL,
        ),
        (
            "03",
            "AI 辅助判读",
            "信号候选、边界风险、不确定性和关键帧时序证据；患者条件经安全门受限接入。",
            GREEN_LIGHT,
            GREEN,
        ),
        (
            "04",
            "医生复核与证据包",
            "人工标注、版本审计、L0 安全降级、JSON/CSV/Markdown/DICOM SC/ZIP 导出。",
            AMBER_LIGHT,
            AMBER,
        ),
    ]
    card_y = 366
    card_width = 480
    for index, card in enumerate(cards):
        x = 90 + index * 530
        step_card(
            draw,
            (x, card_y, x + card_width, card_y + 306),
            index=card[0],
            heading=card[1],
            detail=card[2],
            fill=card[3],
            accent=card[4],
        )
        if index < len(cards) - 1:
            arrow(
                draw,
                (x + card_width + 12, card_y + 153),
                (x + 518, card_y + 153),
                color=TEAL,
            )

    rounded(draw, (90, 770, 2110, 1080), fill="#FFFFFF", outline=LINE, width=3)
    text(draw, (136, 820), "三阶段展示主线", size=34, color=TEAL, bold=True)
    stage_width = 620
    stage_items = [
        ("术前三维参考", "公开 CBCT/STL、下颌曲线、复核平面、对象树与方向检查。", CYAN),
        (
            "术中荧光融合判读",
            "关键帧证据、融合叠加、风险层、不确定性层与连续帧输出。",
            GREEN,
        ),
        (
            "回顾验证与回灌",
            "医生复核、模型/阈值身份、SHA256、失败原因与可导出证据。",
            AMBER,
        ),
    ]
    for index, (heading, detail, accent) in enumerate(stage_items):
        x = 140 + index * 660
        draw.rectangle((x, 894, x + 16, 1010), fill=accent)
        text(draw, (x + 42, 892), heading, size=31, color=INK, bold=True)
        wrapped(
            draw,
            (x + 42, 944),
            detail,
            width=stage_width - 60,
            size=24,
            color=MUTED,
            spacing=6,
        )
    footer(
        draw,
        "工程示意。设备私有接口由企业侧负责；空间证据缺失时平台保持 L0 未配准参考。",
    )
    image.save(path, quality=95)


def build_boundary_concept(path: Path) -> None:
    image, draw = new_canvas()
    title(
        draw,
        "FIG 1",
        "颌骨骨髓炎术中边界判读的信号与复核层次",
        "概念示意：把结构、荧光、风险与医生复核分层表达，避免单一信号承担终判任务",
    )
    stages = [
        (
            "结构信息",
            "原彩图、CBCT/STL 与术野形态，提供空间与操作背景。",
            CYAN_LIGHT,
            CYAN,
        ),
        ("动态信号", "荧光强度、时序变化、配准质量与 ROI 量化。", TEAL_LIGHT, TEAL),
        (
            "复核候选",
            "低活性候选、过渡复核区、高活性参考和无法判断区。",
            AMBER_LIGHT,
            AMBER,
        ),
        (
            "临床复核",
            "医生结合病理、培养、术野和患者条件形成最终判断。",
            GREEN_LIGHT,
            GREEN,
        ),
    ]
    for index, (heading, detail, fill, accent) in enumerate(stages):
        x = 90 + index * 530
        rounded(draw, (x, 370, x + 470, 710), fill=fill, outline=accent, width=4)
        text(draw, (x + 38, 416), f"0{index + 1}", size=24, color=accent, bold=True)
        text(draw, (x + 38, 470), heading, size=36, color=INK, bold=True)
        wrapped(draw, (x + 38, 540), detail, width=370, size=26, color=MUTED, spacing=10)
        if index < len(stages) - 1:
            arrow(draw, (x + 482, 540), (x + 518, 540), color=TEAL)
    rounded(draw, (290, 870, 1910, 1060), fill="#FFFFFF", outline=LINE, width=3)
    text(draw, (350, 922), "安全判读原则", size=32, color=TEAL, bold=True)
    wrapped(
        draw,
        (350, 980),
        "平台将信号、风险和不确定性组织为复核优先级；缺少骨面门控、校准、来源或医生复核时保持工程参考状态。",
        width=1460,
        size=27,
        color=INK,
        spacing=8,
    )
    footer(draw, "概念图基于赛题痛点与平台安全架构，不代表患者病理图像或已验证切除边界。")
    image.save(path, quality=95)


def build_fusion_pipeline(path: Path) -> None:
    image, draw = new_canvas()
    title(
        draw,
        "FIG 4-1",
        "白光 / 荧光双通道融合与三通道质控",
        "面向 4K JPEG 与 MP4 的可配置融合流程；设备叠加图进入质量核对与证据留存",
    )

    input_boxes = [
        ("原彩图", "结构与术野信息", CYAN_LIGHT, CYAN),
        ("原始荧光图", "ICG 信号与时序输入", GREEN_LIGHT, GREEN),
        ("设备叠加图", "显示与质控核对", AMBER_LIGHT, AMBER),
    ]
    for index, (heading, detail, fill, accent) in enumerate(input_boxes):
        x = 110 + index * 610
        rounded(draw, (x, 370, x + 480, 550), fill=fill, outline=accent, width=4)
        text(draw, (x + 36, 410), heading, size=35, color=INK, bold=True)
        text(draw, (x + 36, 470), detail, size=26, color=MUTED)
        if index < 2:
            arrow(draw, (x + 496, 460), (x + 574, 460), color=TEAL)

    flow = [
        ("输入准入", "签名、解码、方向、时间戳和通道关系", CYAN),
        ("几何配准", "尺寸对齐、相位相关与低响应降级", TEAL),
        ("信号处理", "背景扣除、百分位归一化、伪彩与 ROI 定量", GREEN),
        ("质控 / 输出", "差异热图、融合图、量化与证据 manifest", AMBER),
    ]
    for index, (heading, detail, accent) in enumerate(flow):
        x = 100 + index * 530
        rounded(draw, (x, 720, x + 440, 992), fill="#FFFFFF", outline=accent, width=4)
        text(draw, (x + 34, 760), f"0{index + 1}", size=24, color=accent, bold=True)
        text(draw, (x + 34, 812), heading, size=34, color=INK, bold=True)
        wrapped(draw, (x + 34, 870), detail, width=370, size=25, color=MUTED, spacing=8)
        if index < len(flow) - 1:
            arrow(draw, (x + 452, 856), (x + 510, 856), color=TEAL)
    footer(draw, "模型输入遵循原彩图与原始荧光图；设备叠加图用于质量检查与显示证据。")
    image.save(path, quality=95)


def panel_image(image_path: Path, target_size: tuple[int, int]) -> Image.Image:
    with Image.open(image_path) as source:
        image = source.convert("RGB")
    image.thumbnail(target_size, Image.Resampling.LANCZOS)
    panel = Image.new("RGB", target_size, "#101E29")
    x = (target_size[0] - image.width) // 2
    y = (target_size[1] - image.height) // 2
    panel.paste(image, (x, y))
    return panel


def build_d083_panel(path: Path) -> None:
    image, draw = new_canvas()
    title(
        draw,
        "FIG 4-2 / 6-4",
        "公开人体 ICG 视频关键帧的融合与复核图层",
        "D083 人体骨移植 ICG 视频代理，用于信号处理与可视化工程验证；非颌骨骨髓炎目标域",
    )
    panels = [
        ("原始荧光帧", D083_PANEL_SOURCES[0], "保留原始信号以支持复核。"),
        ("信号候选叠加", D083_PANEL_SOURCES[1], "工程候选叠加图。"),
        ("风险提示层", D083_PANEL_SOURCES[2], "风险与边界复核优先级。"),
        ("不确定性图层", D083_PANEL_SOURCES[3], "低置信区域进入复核队列。"),
    ]
    placements = [(110, 330), (1150, 330), (110, 750), (1150, 750)]
    for (heading, image_path, detail), (x, y) in zip(panels, placements, strict=True):
        rounded(draw, (x, y, x + 940, y + 350), fill="#FFFFFF", outline=LINE, width=3)
        panel = panel_image(image_path, (520, 298))
        image.paste(panel, (x + 24, y + 26))
        text(draw, (x + 578, y + 56), heading, size=32, color=INK, bold=True)
        wrapped(draw, (x + 578, y + 118), detail, width=310, size=25, color=MUTED, spacing=8)
        text(draw, (x + 578, y + 255), "工程验证图层", size=23, color=TEAL, bold=True)
    footer(draw, "来源：PMC9478374，CC BY 4.0。模型图层用于工程候选与复核流程说明。")
    image.save(path, quality=95)


def build_d083_timeline(path: Path) -> None:
    manifest = json.loads(D083_TIMELINE_MANIFEST.read_text(encoding="utf-8"))
    frames = manifest["frames"]
    if not frames:
        raise ValueError(f"D083 timeline manifest has no frames: {D083_TIMELINE_MANIFEST}")
    times = [float(item["timestamp_sec"]) for item in frames]
    intensities = [float(item["p95_intensity"]) for item in frames]
    areas = [float(item["positive_area_fraction"]) for item in frames]
    if times[-1] <= 0:
        raise ValueError(f"D083 timeline must end after 0 seconds: {D083_TIMELINE_MANIFEST}")
    intensity_max = max(intensities) or 1.0
    area_max = max(areas) or 1.0

    image, draw = new_canvas()
    title(
        draw,
        "FIG 6-1",
        "公开人体 ICG 视频代理的关键帧时序参考",
        "D083 视频均匀抽取 12 个关键帧；强度来自解码 8-bit 亮度代理，供工程回放与复核使用",
    )
    chart = (190, 380, 1630, 970)
    x1, y1, x2, y2 = chart
    draw.rectangle(chart, fill="#FFFFFF", outline=LINE, width=3)
    for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = y2 - int((y2 - y1) * fraction)
        draw.line((x1, y, x2, y), fill="#E3ECEF", width=2)
        text(draw, (x1 - 28, y), f"{fraction:.2f}", size=22, color=MUTED, anchor="rm")
    for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
        x = x1 + int((x2 - x1) * fraction)
        draw.line((x, y1, x, y2), fill="#E3ECEF", width=2)
        text(
            draw,
            (x, y2 + 42),
            f"{times[-1] * fraction:.0f}s",
            size=22,
            color=MUTED,
            anchor="ma",
        )
    intensity_points = []
    area_points = []
    for time_value, intensity, area in zip(times, intensities, areas, strict=True):
        x = x1 + int((x2 - x1) * time_value / times[-1])
        intensity_points.append((x, y2 - int((y2 - y1) * intensity / intensity_max)))
        area_points.append((x, y2 - int((y2 - y1) * (area / area_max))))
    draw.line(intensity_points, fill=GREEN, width=7, joint="curve")
    draw.line(area_points, fill=CYAN, width=6, joint="curve")
    for point in intensity_points:
        draw.ellipse((point[0] - 8, point[1] - 8, point[0] + 8, point[1] + 8), fill=GREEN)
    for point in area_points:
        draw.ellipse((point[0] - 7, point[1] - 7, point[0] + 7, point[1] + 7), fill=CYAN)
    text(draw, (210, 328), "归一化关键帧 P95 亮度", size=27, color=GREEN, bold=True)
    text(
        draw,
        (580, 328),
        "信号候选面积比例（按本序列最大值归一化）",
        size=27,
        color=CYAN,
        bold=True,
    )
    rounded(draw, (1710, 402, 2080, 880), fill=TEAL_LIGHT, outline=TEAL, width=3)
    text(draw, (1750, 454), "解读边界", size=31, color=TEAL, bold=True)
    wrapped(
        draw,
        (1750, 520),
        "视频已压缩、采样稀疏，曲线用于关键帧工程回放。跨病例量化需原始传感器、统一采集协议与医生复核。",
        width=286,
        size=25,
        color=INK,
        spacing=9,
    )
    footer(
        draw,
        "来源：D083 公开人体骨移植 ICG 视频代理。曲线不表示注射药代、病灶边界或临床疗效。",
    )
    image.save(path, quality=95)


def build_4k_engineering_input(path: Path) -> None:
    image, draw = new_canvas()
    title(
        draw,
        "FIG 6-2",
        "4K 合成工程输入的双通道融合验证",
        "以 3840x2160 合成白光/荧光成对输入验证文件准入、配准、融合、ROI 与患者条件安全回退流程",
    )
    panels = [
        ("合成白光输入", COMPETITION_4K_INPUTS[0], CYAN),
        ("合成荧光输入", COMPETITION_4K_INPUTS[1], GREEN),
    ]
    for index, (heading, source_path, accent) in enumerate(panels):
        x = 110 + index * 750
        rounded(draw, (x, 350, x + 700, 840), fill="#FFFFFF", outline=accent, width=4)
        panel = panel_image(source_path, (640, 340))
        image.paste(panel, (x + 30, 390))
        text(draw, (x + 30, 864), heading, size=32, color=INK, bold=True)
        text(draw, (x + 30, 916), "3840 x 2160 | 合成工程输入", size=24, color=MUTED)
    rounded(draw, (1630, 350, 2110, 840), fill=AMBER_LIGHT, outline=AMBER, width=4)
    text(draw, (1670, 404), "验证范围", size=32, color=AMBER, bold=True)
    for offset, item in enumerate(
        (
            "文件准入与双通道配准",
            "伪彩、融合与 ROI",
            "4K tiled 路径",
            "患者条件安全回退",
        )
    ):
        text(draw, (1670, 486 + offset * 66), item, size=25, color=INK)
    footer(draw, "该图使用合成 4K 工程输入，不含患者信息、组织学标签或临床性能结论。")
    image.save(path, quality=95)


def build_d074_proxy_summary(path: Path) -> None:
    report = json.loads(D074_PROXY_REPORT.read_text(encoding="utf-8"))
    metrics = report["validation"]["metrics"]
    values = [
        ("低活性候选", float(metrics["low_activity_dice"]), RED),
        ("过渡复核区", float(metrics["transition_dice"]), AMBER),
        ("高活性参考", float(metrics["high_activity_dice"]), GREEN),
    ]
    image, draw = new_canvas()
    title(
        draw,
        "FIG 6-3",
        "骨活性多任务候选的 D074 代理域结果摘要",
        "D074 为公开人脑 PpIX 显微荧光代理，测试集 2 个样本；指标仅说明训练与推理链可运行",
    )
    base_x, base_y, height = 260, 980, 490
    draw.line((base_x, base_y, 1560, base_y), fill=LINE, width=4)
    for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = base_y - int(height * fraction)
        draw.line((base_x, y, 1560, y), fill="#E3ECEF", width=2)
        text(draw, (base_x - 30, y), f"{fraction:.2f}", size=22, color=MUTED, anchor="rm")
    for index, (label, value, accent) in enumerate(values):
        x = 420 + index * 390
        bar_height = int(height * value)
        draw.rounded_rectangle((x, base_y - bar_height, x + 190, base_y), radius=16, fill=accent)
        text(
            draw,
            (x + 95, base_y - bar_height - 34),
            f"{value:.3f}",
            size=31,
            color=INK,
            bold=True,
            anchor="ms",
        )
        text(
            draw,
            (x + 95, base_y + 48),
            label,
            size=26,
            color=INK,
            bold=True,
            anchor="ma",
        )
        text(draw, (x + 95, base_y + 90), "Dice", size=23, color=MUTED, anchor="ma")
    rounded(draw, (1660, 390, 2080, 920), fill=RED_LIGHT, outline=RED, width=4)
    text(draw, (1704, 448), "安全门结论", size=31, color=RED, bold=True)
    for offset, item in enumerate(
        (
            "接受覆盖率 0.056 < 0.10",
            "选择性错误率 0.302 > 0.15",
            "工程实用门未通过",
            "候选模型保留为研发验证。",
        )
    ):
        text(draw, (1704, 526 + offset * 58), item, size=24, color=INK)
    footer(
        draw,
        "D074 为非骨、非 ICG、非颌骨、非目标域代理。图中无临床混淆矩阵与临床性能结论。",
    )
    image.save(path, quality=95)


def build_ai_pipeline(path: Path) -> None:
    image, draw = new_canvas()
    title(
        draw,
        "FIG 5-1",
        "AI 辅助判读与患者条件安全门",
        "影像基础结果始终保留；患者条件模块仅产生受限差异证据并接受独立安全门控",
    )

    stages = [
        ("多模态影像", "4K JPEG / MP4\n白光、荧光、时间信息", CYAN_LIGHT, CYAN),
        (
            "影像基础推理",
            "关键帧 tiled / 连续帧 fast-output\n概率图与时序稳定性",
            TEAL_LIGHT,
            TEAL,
        ),
        ("四类输出契约", "bone gate、荧光信号\n风险、不确定性", GREEN_LIGHT, GREEN),
        (
            "医生复核与回灌",
            "ROI、人工修改、版本、训练准入\n证据包与失效原因",
            AMBER_LIGHT,
            AMBER,
        ),
    ]
    for index, (heading, detail, fill, accent) in enumerate(stages):
        x = 90 + index * 530
        rounded(draw, (x, 360, x + 470, 650), fill=fill, outline=accent, width=4)
        text(draw, (x + 34, 402), f"0{index + 1}", size=24, color=accent, bold=True)
        text(draw, (x + 34, 456), heading, size=34, color=INK, bold=True)
        y = 522
        for line in detail.split("\n"):
            text(draw, (x + 34, y), line, size=24, color=MUTED)
            y += 42
        if index < len(stages) - 1:
            arrow(draw, (x + 482, 505), (x + 518, 505), color=TEAL)

    rounded(draw, (410, 800, 1790, 1060), fill=RED_LIGHT, outline=RED, width=4)
    text(draw, (470, 844), "患者条件安全门", size=36, color=RED, bold=True)
    safety = [
        ("输入", "年龄、性别、基础病、用药、血液指标"),
        ("门控", "完整性、来源、范围、校准与亚组审计状态"),
        ("输出", "患者条件差异图；门控失败时回到影像基础概率"),
    ]
    for index, (heading, detail) in enumerate(safety):
        x = 470 + index * 420
        text(draw, (x, 928), heading, size=28, color=RED, bold=True)
        wrapped(draw, (x, 974), detail, width=340, size=23, color=INK, spacing=6)
        if index < len(safety) - 1:
            arrow(draw, (x + 350, 968), (x + 394, 968), color=RED, width=6)
    footer(
        draw,
        "当前患者条件与骨活性空间结果属于研发验证能力，尚未形成目标域临床性能结论。",
    )
    image.save(path, quality=95)


def runtime_metrics() -> dict[str, float]:
    four_k_text = RUNTIME_4K_REPORT.read_text(encoding="utf-8")
    four_k_match = re.search(
        r"模型 P50/P95：`[0-9.]+` / `(?P<model_p95>[0-9.]+)` ms。\s*"
        r"- 端到端 P50/P95：`[0-9.]+` / `(?P<e2e_p95>[0-9.]+)` ms。",
        four_k_text,
    )
    if four_k_match is None:
        raise ValueError(f"Unable to read 4K P95 metrics from {RUNTIME_4K_REPORT}")

    live_text = RUNTIME_LIVE_REPORT.read_text(encoding="utf-8")
    live_match = re.search(
        r"\| `current_production_model_via_isolated_candidate_config`[^|]*"
        r"\| [0-9.]+ / (?P<e2e_p95>[0-9.]+)"
        r" \| [0-9.]+ / (?P<model_p95>[0-9.]+) \|",
        live_text,
    )
    if live_match is None:
        raise ValueError(f"Unable to read live fast P95 metrics from {RUNTIME_LIVE_REPORT}")

    metrics = {
        "four_k_model_p95_ms": float(four_k_match.group("model_p95")),
        "four_k_e2e_p95_ms": float(four_k_match.group("e2e_p95")),
        "live_e2e_p95_ms": float(live_match.group("e2e_p95")),
        "live_model_p95_ms": float(live_match.group("model_p95")),
    }
    if any(value <= 0 for value in metrics.values()):
        raise ValueError("Runtime P95 metrics must be positive.")
    return metrics


def build_runtime_chart(path: Path) -> None:
    image, draw = new_canvas()
    title(
        draw,
        "FIG 6-5",
        "4K 全证据与连续帧输出的工程性能",
        "硬件基线：NVIDIA GeForce RTX 5060 Laptop GPU；指标来自公开代理工程验证",
    )

    measured = runtime_metrics()
    metrics = [
        (
            "4K tiled\nE2E P95",
            measured["four_k_e2e_p95_ms"],
            f"{measured['four_k_e2e_p95_ms'] / 1000:.2f} s",
            CYAN,
        ),
        (
            "4K tiled\n模型 P95",
            measured["four_k_model_p95_ms"],
            f"{measured['four_k_model_p95_ms']:.0f} ms",
            TEAL,
        ),
        (
            "fast-output\n服务 E2E P95",
            measured["live_e2e_p95_ms"],
            f"{measured['live_e2e_p95_ms']:.0f} ms",
            GREEN,
        ),
        (
            "fast-output\n模型 P95",
            measured["live_model_p95_ms"],
            f"{measured['live_model_p95_ms']:.0f} ms",
            AMBER,
        ),
    ]
    base_x = 190
    base_y = 1010
    max_height = 500
    max_value = max(metric[1] for metric in metrics)
    draw.line((base_x, base_y, 1960, base_y), fill=LINE, width=4)
    for index, (label, value, display, color) in enumerate(metrics):
        x = base_x + 170 + index * 440
        height = int((value / max_value) * max_height)
        draw.rounded_rectangle((x, base_y - height, x + 180, base_y), radius=14, fill=color)
        text(
            draw,
            (x + 90, base_y - height - 36),
            display,
            size=31,
            color=INK,
            bold=True,
            anchor="ms",
        )
        first, second = label.split("\n")
        text(
            draw,
            (x + 90, base_y + 52),
            first,
            size=27,
            color=INK,
            bold=True,
            anchor="ma",
        )
        text(draw, (x + 90, base_y + 94), second, size=25, color=MUTED, anchor="ma")

    rounded(draw, (1600, 360, 2080, 690), fill=TEAL_LIGHT, outline=TEAL, width=3)
    text(draw, (1640, 408), "运行策略", size=31, color=TEAL, bold=True)
    wrapped(
        draw,
        (1640, 468),
        "4K tiled 路径保留完整尺寸与证据；fast-output 路径以串行连续帧刷新支持术中工程演示。",
        width=360,
        size=25,
        color=INK,
        spacing=8,
    )
    footer(
        draw,
        "性能阈值与测试环境详见工程验证记录；数据域为公开离体荧光代理，非目标域临床性能。",
    )
    image.save(path, quality=95)


def build_roadmap(path: Path) -> None:
    image, draw = new_canvas()
    title(
        draw,
        "FIG 8-1",
        "从软件可行性到目标域验证的分级路线",
        "以可运行平台、可追溯数据与医生复核为基础，逐步补齐目标域证据",
    )
    roadmap = [
        (
            "当前可运行",
            "4K 输入、融合处理、AI 候选、医生复核、证据包、三维参考。",
            TEAL_LIGHT,
            TEAL,
        ),
        (
            "数据回灌",
            "真实目标域脱敏数据、关键帧与 ROI 标注、患者级分组。",
            CYAN_LIGHT,
            CYAN,
        ),
        (
            "工程验证",
            "物理仿体、L1 静态配准、L2 离线位姿回放、误差与失效记录。",
            GREEN_LIGHT,
            GREEN,
        ),
        (
            "转化验证",
            "造影剂 A0-A4、目标域模型、概率校准、亚组审计与独立复核。",
            AMBER_LIGHT,
            AMBER,
        ),
    ]
    for index, (heading, detail, fill, accent) in enumerate(roadmap):
        x = 100 + index * 520
        rounded(draw, (x, 420, x + 440, 770), fill=fill, outline=accent, width=4)
        draw.ellipse((x + 34, 456, x + 116, 538), fill=accent)
        text(
            draw,
            (x + 75, 498),
            str(index + 1),
            size=30,
            color="white",
            bold=True,
            anchor="mm",
        )
        text(draw, (x + 36, 576), heading, size=34, color=INK, bold=True)
        wrapped(draw, (x + 36, 640), detail, width=360, size=25, color=MUTED, spacing=8)
        if index < len(roadmap) - 1:
            arrow(draw, (x + 452, 595), (x + 506, 595), color=TEAL)

    rounded(draw, (260, 920, 1940, 1070), fill="#FFFFFF", outline=LINE, width=3)
    text(draw, (330, 970), "统一安全原则", size=31, color=TEAL, bold=True)
    text(
        draw,
        (690, 970),
        "任何一步缺少来源、质量、误差、医生复核或训练准入证据时，结果保持为工程参考并记录回退原因。",
        size=27,
        color=INK,
    )
    footer(
        draw,
        "路线图用于可行性报告与研发计划；各阶段进入下一步前需通过对应数据、工程和伦理门控。",
    )
    image.save(path, quality=95)


def source_record(path: Path) -> dict[str, int | str]:
    return {
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
    }


def generated_asset_record(staged_path: Path, output_path: Path) -> dict[str, int | str]:
    return {
        "path": str(output_path.relative_to(ROOT)).replace("\\", "/"),
        "sha256": sha256(staged_path),
        "bytes": staged_path.stat().st_size,
    }


def ensure_source_files(paths: tuple[Path, ...]) -> None:
    missing = [path for path in paths if not path.is_file()]
    if missing:
        missing_text = "\n".join(f"- {path}" for path in missing)
        raise FileNotFoundError(f"Missing Challenge Cup figure source files:\n{missing_text}")


def main() -> None:
    if not FONT_REGULAR.exists() or not FONT_BOLD.exists():
        raise RuntimeError("Microsoft YaHei font is required to render Chinese report figures.")

    figures = {
        "fig_01_boundary_review_concept.png": build_boundary_concept,
        "fig_02_system_architecture.png": build_architecture,
        "fig_04_01_fusion_pipeline.png": build_fusion_pipeline,
        "fig_04_02_d083_review_layers.png": build_d083_panel,
        "fig_05_01_ai_review_pipeline.png": build_ai_pipeline,
        "fig_06_01_d083_timeline.png": build_d083_timeline,
        "fig_06_02_4k_engineering_input.png": build_4k_engineering_input,
        "fig_06_03_d074_proxy_summary.png": build_d074_proxy_summary,
        "fig_06_05_runtime_paths.png": build_runtime_chart,
        "fig_08_01_validation_roadmap.png": build_roadmap,
    }
    source_inputs = (
        D083_TIMELINE_MANIFEST,
        *D083_PANEL_SOURCES,
        *COMPETITION_4K_INPUTS,
        D074_PROXY_REPORT,
        SHOWCASE_SCREENSHOT,
        RUNTIME_4K_REPORT,
        RUNTIME_LIVE_REPORT,
    )
    ensure_source_files(source_inputs)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generated_filenames = tuple(figures) + ("fig_07_02_challenge_cup_showcase.png",)
    with tempfile.TemporaryDirectory(prefix=".challenge_cup_figures_", dir=OUTPUT_DIR) as temporary_directory:
        staging_dir = Path(temporary_directory)
        for filename, builder in figures.items():
            builder(staging_dir / filename)
        shutil.copy2(SHOWCASE_SCREENSHOT, staging_dir / "fig_07_02_challenge_cup_showcase.png")

        manifest = {
            "schema_version": "challenge_cup_report_assets_v1",
            "generated_by": "tools/build_challenge_cup_figures.py",
            "data_boundary": "public_or_engineering_validation_only",
            "source_items": [source_record(source) for source in source_inputs],
            "items": [
                generated_asset_record(staging_dir / filename, OUTPUT_DIR / filename)
                for filename in sorted(generated_filenames)
            ],
        }
        staged_manifest = staging_dir / "manifest.json"
        staged_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        for filename in generated_filenames:
            (staging_dir / filename).replace(OUTPUT_DIR / filename)
        staged_manifest.replace(OUTPUT_DIR / "manifest.json")

    manifest_items = manifest["items"]
    print(f"Generated {len(manifest_items)} report figures in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
