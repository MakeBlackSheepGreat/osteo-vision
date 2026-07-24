"""Aggregate the Challenge Cup chapter drafts into one buildable UTF-8 report."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRAFT_DIR = ROOT / "research" / "reports" / "submission" / "challenge_cup_report_draft_20260721"
OUTPUT_PATH = DRAFT_DIR / "challenge_cup_feasibility_report_20260722_zh.md"
CHAPTERS = (
    "Cap1_项目背景与临床需求.md",
    "Cap2_总体技术方案设计.md",
    "Cap3_荧光造影剂设计.md",
    "Cap4_多模态荧光显微图像融合方法.md",
    "Cap5_病灶智能识别与辅助决策模型.md",
    "Cap6_实验设计及结果验证.md",
    "Cap7_工程实现与临床应用方案.md",
    "Cap8_创新性与可行性.md",
    "Cap9_未来展望.md",
)


def main() -> None:
    chapter_texts: list[str] = []
    for chapter_name in CHAPTERS:
        chapter_path = DRAFT_DIR / chapter_name
        if not chapter_path.is_file():
            raise FileNotFoundError(f"Missing Challenge Cup chapter: {chapter_path}")
        chapter_texts.append(chapter_path.read_text(encoding="utf-8").strip())

    preamble = """# 颌骨骨髓炎智能化荧光诊疗可行性报告

版本：挑战杯报告整合稿  
日期：2026-07-22  
范围：面向荧光手术显微镜的平台软件可行性、工程验证与后续验证方案；造影剂综述与实验路线见第 3 章。

> 患者安全边界：全文所述平台输出均为研发验证证据和医生复核辅助。公开、代理、合成与仿真数据均按各章节的数据域声明解释，不用于自动确诊、自动切除或真实术中导航承诺。
""".strip()
    report = "\n\n---\n\n".join((preamble, *chapter_texts)) + "\n"
    OUTPUT_PATH.write_text(report, encoding="utf-8")
    print(f"Generated Challenge Cup report: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
