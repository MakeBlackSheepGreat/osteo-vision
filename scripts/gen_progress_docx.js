const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat,
  HeadingLevel, BorderStyle, WidthType, ShadingType,
  PageNumber, PageBreak
} = require("docx");

// ─── helpers ──────────────────────────────────────────────
const FONT = "Calibri";
const FONT_CJK = "Microsoft YaHei";
const border = { style: BorderStyle.SINGLE, size: 1, color: "B0C0D0" };
const borders = { top: border, bottom: border, left: border, right: border };
const cellMargins = { top: 40, bottom: 40, left: 120, right: 120 };
const hdrBorder = { style: BorderStyle.SINGLE, size: 2, color: "1A5276" };
const hdrBorders = { top: border, bottom: hdrBorder, left: border, right: border };
const hdrShading = { fill: "E8F0FE", type: ShadingType.CLEAR };

function runProps(size = 22, opts = {}) {
  return {
    font: { ascii: FONT, hAnsi: FONT, cs: FONT, eastAsia: FONT_CJK },
    size,
    bold: opts.bold ?? false,
    color: opts.color ?? "162020",
    italics: opts.italics ?? false,
  };
}

function p(text, opts = {}) {
  return new Paragraph({
    spacing: { after: opts.spacing ?? 160 },
    children: [new TextRun({ text, ...runProps(opts.size ?? 22, opts) })],
  });
}

function boldP(text, size = 22) {
  return p(text, { bold: true, size });
}

function headerCell(text, width) {
  return new TableCell({
    borders: hdrBorders, shading: hdrShading, width: { size: width, type: WidthType.DXA },
    margins: cellMargins,
    children: [new Paragraph({
      indent: { left: 0, firstLine: 0 },
      children: [new TextRun({ text, ...runProps(20, { bold: true, color: "1A5276" }) })]
    })],
  });
}

function cell(text, width) {
  return new TableCell({
    borders, width: { size: width, type: WidthType.DXA }, margins: cellMargins,
    children: [new Paragraph({
      spacing: { after: 0 },
      indent: { left: 0, firstLine: 0 },
      children: [new TextRun({ text, ...runProps(20, { color: "162020" }) })]
    })],
  });
}

function makeTable(headers, rows, colWidths) {
  const totalWidth = colWidths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: totalWidth, type: WidthType.DXA },
    columnWidths: colWidths,
    rows: [
      new TableRow({ tableHeader: true, children: headers.map((h, i) => headerCell(h, colWidths[i])) }),
      ...rows.map(row =>
        new TableRow({ children: row.map((c, i) => cell(String(c), colWidths[i])) })
      ),
    ],
  });
}

// ─── page setup ───────────────────────────────────────────
const A4_W = 11906, A4_H = 16838, MARGIN = 1440, CONTENT = A4_W - 2 * MARGIN;

function heading1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1, spacing: { before: 360, after: 200 },
    children: [new TextRun({ text, ...runProps(32, { bold: true, color: "1A5276" }) })],
  });
}

function heading2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2, spacing: { before: 280, after: 160 },
    children: [new TextRun({ text, ...runProps(28, { bold: true, color: "1E6FA6" }) })],
  });
}

function bullet(text) {
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    children: [new TextRun({ text, ...runProps(22) })],
  });
}

// ─── build children ───────────────────────────────────────
const children = [];

// Title block
children.push(new Paragraph({
  spacing: { after: 60 },
  children: [new TextRun({ text: "颌骨骨髓炎智能化荧光诊疗平台", ...runProps(44, { bold: true, color: "1A5276" }) })]
}));
children.push(new Paragraph({
  spacing: { after: 40 },
  children: [new TextRun({ text: "项目进度汇报", ...runProps(36, { bold: true, color: "1A5276" }) })]
}));
children.push(new Paragraph({
  spacing: { after: 40 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "1A5276", space: 8 } },
  children: [new TextRun({ text: "汇报日期：2026年6月18日　　项目阶段：V1 → V2　　版本号：0.2.0", ...runProps(20, { color: "5A6A7A" }) })]
}));
children.push(p(""));

// ── Section 1 ──
children.push(heading1("一、项目定位"));
children.push(p("基于白光 / ICG 双通道影像的颌骨骨髓炎术中边界风险提示与病例报告软件平台。", { bold: true, size: 24 }));
children.push(p("面向三大赛点：荧光伪彩色增强（赛点一）、AI 辅助诊断（赛点二）、标准化输出与远程协作（赛点三）。"));

// ── Section 2 ──
children.push(heading1("二、总体完成概览"));
children.push(makeTable(
  ["维度", "状态", "关键产出"],
  [
    ["V1 荧光融合闭环", "✅ 完成", "白光+ICG → 伪彩融合图 + 热图 + 归一化图 + JSON/Markdown 报告"],
    ["V2 前后端分离平台", "✅ 已成型", "Vue 3 前端 + FastAPI 后端 + 完整 REST API"],
    ["V2 前端界面", "✅ 有型", "三页面（病例工作台、医生复核、报告导出），医学蓝配色"],
    ["AI 模型框架", "✅ 就绪", "配置驱动，4 模型注册（nnU-Net、MedSAM2、BiomedCLIP、Fixture）"],
    ["AI 模型训练", "🔄 进行中", "10 模型基准测试完成，nnU-Net 基线 smoke 跑通"],
    ["真实样本接入", "⏳ 待开始", "公开 CBCT 三数据集预处理已完成"],
    ["DICOM 输出", "⏳ 待开始", "架构预留，需赛点三细化"],
  ],
  [1800, 1200, 6026]
));
children.push(p(""));

// ── Section 3 ──
children.push(heading1("三、各模块详细进度"));

// 3.1
children.push(heading2("3.1 荧光分析与图像融合（赛点一） ✅ 完成"));
children.push(boldP("核心文件：src/preprocess/fluorescence.py（240 行）", 20));
children.push(boldP("已实现能力："));
children.push(bullet("白光图像 + ICG 荧光图像双通道输入"));
children.push(bullet("自动尺寸对齐（resize to white-light）"));
children.push(bullet("荧光强度归一化（[1%, 99%] 百分位归一化）"));
children.push(bullet("伪彩映射（绿 / 琥珀 / 品红三种方案）"));
children.push(bullet("Alpha 融合叠加（overlay = (1-α)×white + α×pseudo_color）"));
children.push(bullet("荧光定量统计：均值、最大值、P95、阳性面积、阳性面积占比"));
children.push(bullet("输出品：融合图 PNG、热图 PNG、归一化荧光 PNG、JSON 报告、Markdown 报告"));
children.push(boldP("前端融合参数面板："));
children.push(bullet("透明度滑块（0.00 – 1.00）"));
children.push(bullet("荧光阈值滑块（0.00 – 1.00）"));
children.push(bullet("伪彩方案下拉（绿色 / 琥珀色 / 品红色）"));
children.push(p("状态：严格对标赛点一。当前采用 resize 对齐（标注为 initial demo），后续可升级为刚性/非刚性配准。", { size: 20 }));

// 3.2
children.push(heading2("3.2 AI 辅助诊断框架（赛点二） 🔄 框架就绪 / 训练进行中"));
children.push(boldP("模型注册表："));
children.push(makeTable(
  ["模型 ID", "家族", "任务类型", "说明"],
  [
    ["nnunet_v2_osteo_baseline", "nnU-Net v2", "分割", "颌骨骨髓炎分割基线"],
    ["medsam2_osteo_promptable", "MedSAM-like", "分割", "可提示病灶/坏死骨 ROI 分割"],
    ["biomedclip_osteo_screening", "VLM 编码器", "分类", "图像级辅助筛查流程"],
    ["fixture_default", "Fixture", "全部", "确定性 fallback，测试和 Demo 用"],
  ],
  [2200, 1500, 1000, 4326]
));
children.push(p(""));
children.push(boldP("AI 模型训练成果："));
children.push(makeTable(
  ["完成项", "说明"],
  [
    ["D024 10 模型基准", "MONAI 框架 10 种 3D 模型在 DentVoxel jaw-roi 上完成比较"],
    ["D024 nnU-Net smoke", "nnU-Net v2 在 D024 上跑通完整训练/预测/评估链路"],
    ["D024 分割模型选型报告", "中英文双语，推荐 nnU-Net v2 / MedNeXt / U-Mamba"],
    ["3 个公开 CBCT 预处理", "D024 DentVoxel、D025 DolChID、D036 ToothFairy2"],
    ["颌骨基础分割模型设计", "架构设计报告，5-fold 验证与 HD95/NSD 指标定义"],
  ],
  [2000, 7026]
));
children.push(p(""));
children.push(boldP("AI 安全边界："));
children.push(bullet("所有模型 clinical_claim_allowed: false"));
children.push(bullet("输出定位为辅助提示 + 医生复核，不自动确诊"));
children.push(bullet("候选区域状态四态：review_required / accepted / modified / rejected"));

// 3.3
children.push(heading2("3.3 前端界面（Vue 3 + TypeScript） ✅ 已成型"));
children.push(boldP("技术栈：Vue 3.5 + Vite 6 + Pinia 3 + Vue Router 4 + TypeScript 5"));
children.push(p(""));
children.push(makeTable(
  ["页面", "路由", "状态", "核心内容"],
  [
    ["病例工作台", "/case", "✅ 完成", "三栏布局：控制面板 + 三联图像/候选区/量化 + 证据面板"],
    ["医生复核", "/review", "✅ 完成", "两栏布局：ROI 画布 + 候选区列表/复核按钮/量化指标"],
    ["报告导出", "/report", "✅ 完成", "两栏布局：导出详情 + 输出边界说明"],
  ],
  [1400, 1000, 1000, 5626]
));
children.push(p(""));
children.push(p("已实现 UI 组件（9 个）：CaseInputPanel、FusionViewer、RoiCanvas、CandidateRegionList、ReviewStateControls、QuantificationPanel、QualityFlagPanel、ExportPanel、MedicalDisclaimer"));
children.push(p("设计语言：医学蓝主色调（#1A5276 / #2980B9 / #1E6FA6），浅蓝灰底色（#F3F6FA），白色卡片，清晰信息层级，临床级软件质感。"));

// 3.4
children.push(heading2("3.4 后端服务（FastAPI） ✅ 已成型"));
children.push(p("API 路由（8 个端点）：GET /health、GET /ready、病例 CRUD、输入管理、分析执行、复核记录、证据包导出"));
children.push(p("后端服务层（5 个 service）：AnalysisService、InputService、ReviewService、ExportService、RoiService"));
children.push(p("数据流：前端 ↔ REST API ↔ Service 层 ↔ 荧光融合引擎 ↔ JSON 文件持久化"));

// 3.5
children.push(heading2("3.5 标准化输出（赛点三） 🟡 基础完成 / 待扩展"));
children.push(boldP("已实现输出格式："));
children.push(bullet("overlay.png — 白光/荧光融合图"));
children.push(bullet("heatmap.png — 荧光热图"));
children.push(bullet("normalized_fluorescence.png — 归一化荧光灰度图"));
children.push(bullet("report.json — 结构化 JSON（含融合参数、量化指标、免责声明）"));
children.push(bullet("report.md — Markdown 单病例报告"));
children.push(bullet("ZIP 证据包导出（含所有图和报告）"));
children.push(boldP("待实现："));
children.push(bullet("DICOM Secondary Capture（从 PNG 封装）"));
children.push(bullet("DICOM Structured Report（结构化病灶描述）"));
children.push(bullet("PDF 正式报告"));

// 3.6
children.push(heading2("3.6 研究文档 📚 已完成 32 份报告"));
children.push(makeTable(
  ["类别", "数量", "举例"],
  [
    ["预处理报告", "6 份中英双语", "D024 DentVoxel、D025 DolChID、D036 ToothFairy2"],
    ["建模报告", "8 份中英双语", "10 模型基准、前沿基准、nnU-Net smoke、选型报告"],
    ["规划文档", "8 份中英双语", "平台目标母稿、V1 闭环计划、技术栈、任务定义"],
  ],
  [1800, 1600, 5626]
));
children.push(p(""));

// 3.7
children.push(heading2("3.7 工程体系"));
children.push(makeTable(
  ["维度", "详情"],
  [
    ["Python 源码", "72 个 .py 文件（core/datasets/engine/models/pipelines/preprocess/reports）"],
    ["后端源码", "32 个 .py 文件（api/core/domains/services/reports）"],
    ["测试体系", "29 个测试文件（unit + smoke + integration）"],
    ["代码质量", "black + isort + flake8 + mypy 就绪，pre-commit 已配"],
    ["配置驱动", "configs/tasks/osteo_vision.yml + configs/inference/osteo_vision.yml"],
    ["前端测试", "Vitest，4 个组件测试全部通过"],
    ["一键启动", "make platform（同时启动前后端），make demo（Gradio 备用）"],
  ],
  [1800, 7226]
));
children.push(p(""));

// ── Section 4 ──
children.push(heading1("四、版本路线图"));
children.push(makeTable(
  ["版本", "目标", "状态"],
  [
    ["V1", "Gradio / 最小平台闭环跑通双通道融合 + 报告闭环", "✅ 已完成"],
    ["V2", "前后端分离 (Vue + FastAPI) + 完整病例工作台", "✅ 已成型（代码就绪）"],
    ["V3", "AI 基线接入 + 真实模型推理", "🔄 框架就绪，训练进行中"],
    ["V4", "真实术中样本闭环 + DICOM 标准化", "⏳ 待开始"],
  ],
  [800, 6026, 2200]
));
children.push(p(""));

// ── Section 5 ──
children.push(heading1("五、当前阻塞与风险"));
children.push(makeTable(
  ["风险项", "等级", "说明"],
  [
    ["缺少真实术中白光/ICG 样本", "🔴 高", "AI 模块只能用公开 CBCT 数据做间接验证，赛点二只能作为平台演示"],
    ["缺少医生标注", "🔴 高", "下颌骨/坏死骨/灌注异常缺乏金标准标注，模型评估受限"],
    ["DICOM 输出未启动", "🟡 中", "赛点三的 DICOM SC/SR 扩展需要进一步调研和开发"],
    ["虚函数对接", "🟡 中", "后端 AI 推理目前通过 Fixture 返回模拟结果，真实模型尚未上线"],
  ],
  [2600, 1000, 5426]
));
children.push(p(""));

// ── Section 6 ──
children.push(heading1("六、下周可演示内容"));
children.push(p("如明后天需要给领导看，建议聚焦以下可演示路径："));
children.push(p(""));
children.push(p("1. 启动平台（2 分钟）：make platform 一键启动，浏览器打开 http://127.0.0.1:5174", { bold: true }));
children.push(p("2. 演示双通道融合工作流（5 分钟）：新建病例 → 输入测试图片 → 运行分析 → 三联图像视图 → 候选区域 → 导出 ZIP"));
children.push(p("3. 展示 AI 辅助复核流程（3 分钟）：切换到医生复核页 → ROI 画布 + 候选区 + 接受/修改/驳回操作"));
children.push(p("4. 展示研究文档体系（5 分钟）：32 份中英双语报告的完整性 → 30+ 篇论文、11 个数据集、5 个外部模型快照"));

// ── Section 7 ──
children.push(heading1("七、核心文件索引"));
children.push(makeTable(
  ["用途", "路径"],
  [
    ["项目目标母稿", "research/reports/planning/osteo_vision_platform_target_zh.md"],
    ["V1 闭环计划", "research/reports/planning/v1_demo_closure_zh.md"],
    ["荧光融合引擎", "src/preprocess/fluorescence.py"],
    ["后端分析服务", "backend/src/services/analysis_service.py"],
    ["前端主页", "frontend/src/pages/CaseWorkspacePage.vue"],
    ["任务配置", "configs/tasks/osteo_vision.yml"],
    ["推理配置", "configs/inference/osteo_vision.yml"],
    ["10 模型基准报告", "research/reports/modeling/d024_10_model_baseline_benchmark_zh.md"],
    ["颌骨分割模型设计", "research/reports/modeling/osteo_vision_foundation_segmentation_model_design_zh.md"],
  ],
  [3200, 5826]
));

// ── Disclaimer ──
children.push(p(""));
children.push(new Paragraph({
  spacing: { before: 200, after: 120 },
  border: {
    top: { style: BorderStyle.SINGLE, size: 2, color: "C1812A", space: 8 },
    left: { style: BorderStyle.SINGLE, size: 8, color: "C1812A", space: 8 },
  },
  indent: { left: 120 },
  children: [
    new TextRun({ text: "平台安全边界免责声明：", ...runProps(18, { bold: true, color: "8A5C11" }) }),
    new TextRun({ text: "本报告所有内容均定位为研发验证版平台和竞赛演示，不构成临床诊断结论。AI 模型评估受限于公开数据集和模拟样本，真实临床性能需经脱敏术中数据闭环验证。", ...runProps(18, { color: "6B5018" }) }),
  ],
}));

// ── Build document ──
const doc = new Document({
  numbering: {
    config: [{
      reference: "bullets",
      levels: [{
        level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } },
      }],
    }],
  },
  styles: {
    default: {
      document: {
        run: { font: { ascii: FONT, hAnsi: FONT, cs: FONT, eastAsia: FONT_CJK }, size: 22 },
        paragraph: { spacing: { after: 160, line: 276 }, indent: { left: 0, firstLine: 0 } },
      },
    },
    paragraphStyles: [
      {
        id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: { ascii: FONT, hAnsi: FONT, cs: FONT, eastAsia: FONT_CJK }, size: 32, bold: true, color: "1A5276" },
        paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 },
      },
      {
        id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: { ascii: FONT, hAnsi: FONT, cs: FONT, eastAsia: FONT_CJK }, size: 28, bold: true, color: "1E6FA6" },
        paragraph: { spacing: { before: 280, after: 160 }, outlineLevel: 1 },
      },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: A4_W, height: A4_H },
        margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN },
      },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          children: [new TextRun({
            text: "颌骨骨髓炎智能化荧光诊疗平台 — 项目进度汇报",
            ...runProps(16, { color: "8A9AAA", italics: true }),
          })],
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [
            new TextRun({ text: "— ", ...runProps(16, { color: "8A9AAA" }) }),
            new TextRun({ children: [PageNumber.CURRENT], ...runProps(16, { color: "1A5276" }) }),
            new TextRun({ text: " —", ...runProps(16, { color: "8A9AAA" }) }),
          ],
        })],
      }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then(buffer => {
  const outPath = "research/reports/planning/progress_report_20250618_zh.docx";
  fs.writeFileSync(outPath, buffer);
  console.log("Written: " + outPath + " (" + buffer.length + " bytes)");
});
