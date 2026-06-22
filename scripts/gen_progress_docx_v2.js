const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat,
  HeadingLevel, BorderStyle, WidthType, ShadingType,
  PageNumber
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

function boldP(text, size = 22) { return p(text, { bold: true, size }); }

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
      ...rows.map(row => new TableRow({ children: row.map((c, i) => cell(String(c), colWidths[i])) })),
    ],
  });
}

// ─── page setup ───────────────────────────────────────────
const A4_W = 11906, A4_H = 16838, MARGIN = 1440;

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

// ── 大白话导读 ──（仿 Nature 摘要段落：先讲背景，再点问题，再说方案）
function plainIntro(text) {
  return new Paragraph({
    spacing: { before: 120, after: 120 },
    indent: { left: 80 },
    border: { left: { style: BorderStyle.SINGLE, size: 6, color: "2980B9", space: 8 } },
    children: [new TextRun({ text, ...runProps(20, { color: "2980B9", italics: true }) })],
  });
}

// ════════════════════════════════════════════════════════════
//  Below: ONLY the content — the report body — changes for v2.
//  Preamble (helpers) and postamble (doc build) stay the same.
// ════════════════════════════════════════════════════════════

const children = [];

// ── Title ──
children.push(new Paragraph({
  spacing: { after: 60 },
  children: [new TextRun({ text: "颌骨骨髓炎智能化荧光诊疗平台", ...runProps(44, { bold: true, color: "1A5276" }) })]
}));
children.push(new Paragraph({
  spacing: { after: 40 },
  children: [new TextRun({ text: "团队进展报告（2026年6月）", ...runProps(36, { bold: true, color: "1A5276" }) })]
}));
children.push(new Paragraph({
  spacing: { after: 40 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "1A5276", space: 8 } },
  children: [new TextRun({ text: "版本 0.2.0   |   阶段 V1 已完成 → V2 已成型   |   目标：竞赛可演示闭环", ...runProps(20, { color: "5A6A7A" }) })]
}));
children.push(p(""));

// ════════════════════════════════════════════════════════════
// 第一章：我们是干什么的
// ════════════════════════════════════════════════════════════
children.push(heading1("一、我们是干什么的"));

children.push(plainIntro("一句话：做一款软件，帮口腔科医生在手术中看清楚哪里骨头坏了、坏到什么程度——用荧光相机拍照 + AI 自动标出来 + 生成报告。"));
children.push(p(""));

children.push(p("颌骨骨髓炎是下巴骨头里的一种严重感染，手术时医生需要把坏死的骨头切掉。但肉眼很难判断切到哪里算干净——ICG 荧光造影剂可以帮上忙：它在血流正常的地方亮、坏死的地方暗。问题是荧光信号很弱，肉眼直接看容易漏掉，也不方便记录。"));

children.push(p("我们做的事情，就是把荧光信号增强、用颜色标出来、让 AI 辅助判读哪里风险高、最后生成可存档的结构化报告。全部跑在普通电脑上，不需要额外硬件。"));

children.push(p("这个项目同时参加三个赛道的竞赛评比：", { bold: true }));
children.push(bullet("赛点一：荧光图像伪彩色增强——把两张图（白光 + 荧光）叠在一起，用颜色突出异常区域"));
children.push(bullet("赛点二：AI 辅助诊断——自动标注疑似病灶位置，提示医生需要重点复核的区域"));
children.push(bullet("赛点三：标准化输出——把结果导出成结构化报告，预留 DICOM 医院标准格式"));

// ════════════════════════════════════════════════════════════
// 第二章：总体完成情况（一张表看清楚）
// ════════════════════════════════════════════════════════════
children.push(heading1("二、整体做到哪了（一表概览）"));

children.push(plainIntro("一句话：软件前后端已经连起来了，荧光融合跑通了，AI 框架搭好了，现在缺真实手术样本做最后的临床验证。"));
children.push(p(""));

children.push(makeTable(
  ["模块", "完成度", "做到了什么", "下周能演示吗"],
  [
    ["荧光融合（赛点一）", "✅ 完成", "白光+ICG 双图输入，一键输出融合图、热图、归一化图、JSON 和 Markdown 报告", "✅ 能演示"],
    ["前端软件界面", "✅ 完成", "3 个页面（病例工作台 + 医生复核 + 报告导出），医学蓝主题", "✅ 能演示"],
    ["后端 API 服务", "✅ 完成", "8 个接口，病例管理、分析、导出全链路通畅", "✅ 能演示"],
    ["AI 模型框架", "✅ 就绪", "4 个模型已注册（nnU-Net / MedSAM2 / BiomedCLIP / Fixture），可切换", "✅ 能演示（Fixture 模拟）"],
    ["AI 模型训练", "🔄 进行中", "10 种 3D 模型在公开数据上完成对比测试，nnU-Net 训练链路跑通", "⚠️ 可演示训练报告"],
    ["公开数据预处理", "✅ 完成", "3 个公开 CBCT 数据集已预处理，33 份中英双语研究报告已归档", "✅ 能展示"],
    ["真实手术样本", "❌ 缺", "目前只有公开 CBCT 数据，没有术中白光/ICG 样本", "❌ 不能"],
    ["DICOM 标准输出", "⏳ 待做", "架构已预留接口，具体的 DICOM SC/SR 封装待开发", "❌ 不能"],
  ],
  [1800, 1000, 4000, 2200]
));

// ════════════════════════════════════════════════════════════
// 第三章：三个赛点分别做了什么
// ════════════════════════════════════════════════════════════
children.push(heading1("三、三个赛点分别做了什么"));

// 3.1 赛点一
children.push(heading2("赛点一：荧光图像伪彩色增强 —— 把不可见的荧光信号变成可见的彩色图"));

children.push(plainIntro("通俗理解：拍一张白光照片（看得见牙齿和骨头），再拍一张荧光照片（只有荧光信号），软件自动把两张图对齐、叠在一起，用绿色/琥珀色/品红色标出荧光的强弱。强的地方可能血流好，弱的地方可能坏死了。"));
children.push(p(""));

children.push(boldP("已经做出来的功能："));
children.push(bullet("拖入两张图（白光 + 荧光），软件自动对齐尺寸"));
children.push(bullet("荧光信号归一化处理——消除不同曝光条件下的强度差异"));
children.push(bullet("三种伪彩方案可选：绿色（默认）、琥珀色（暖色调）、品红色"));
children.push(bullet("一个滑块调透明度，一个滑块调阈值，实时调节看得见的融合效果"));
children.push(bullet("自动算出一个区域的平均荧光强度、最大值、P95、阳性面积占比"));
children.push(bullet("一键导出 6 个文件：融合图、热图、归一化灰度图、JSON 结构化报告、Markdown 报告、ZIP 证据包"));

children.push(p(""));
children.push(boldP("技术实现："));
children.push(p("核心代码在一个 240 行的 Python 文件里（src/preprocess/fluorescence.py）。用的是 Alpha 融合算法——简单说就是把白光图的每个像素和荧光伪彩图的对应像素按比例混合。目前用简单的 resize 做对齐（标注为演示版本），后续可以换成精确的医学图像配准算法。"));

// 3.2 赛点二
children.push(heading2("赛点二：AI 辅助诊断 —— 让 AI 帮医生标出可疑区域"));

children.push(plainIntro("通俗理解：AI 看完荧光融合图后，会圈出几个它觉得异常的区域，告诉医生\u201C这里是高荧光区，可能血流异常\u201D或者\u201C这里是低荧光区，可能坏死了\u201D。但最终决定权在医生手里——医生可以接受、修改或驳回 AI 的建议。"));
children.push(p(""));

children.push(boldP("AI 模型储备："));
children.push(p("我们在系统里注册了 4 个可切换的模型（像换显卡一样可以换不同模型）："));
children.push(makeTable(
  ["模型", "做什么", "来源", "状态"],
  [
    ["nnU-Net v2", "颌骨/病灶区域分割（圈出哪里是骨头、哪里是病变）", "德国海德堡大学开源", "基线模型，训练链路已跑通"],
    ["MedSAM2", "可交互式分割——医生点一下，AI 圈出周围异常组织", "学术前沿，2025 年论文", "已注册，待完整训练"],
    ["BiomedCLIP", "图像分类——判断整张图是正常还是异常", "微软研究院开源", "已注册，辅助筛查用"],
    ["Fixture（兜底）", "确定性模拟模型——没有真实模型时也能跑完整流程", "团队自建", "Demo/测试用"],
  ],
  [1600, 3200, 2000, 2200]
));

children.push(p(""));
children.push(boldP("训练进展："));
children.push(bullet("在公开的牙科 CBCT 数据集（D024 DentVoxel，100 例）上，完成了 10 种 3D 医学分割模型的对比测试"));
children.push(bullet("nnU-Net v2 完成完整训练/预测/评估闭环验证（1-epoch smoke test 通过）"));
children.push(bullet("另外 2 个公开牙科数据集（D025 DolChID、D036 ToothFairy2）已完成预处理"));
children.push(bullet("颌骨分割模型设计报告已完成（定义了 5-fold 交叉验证、Dice/HD95/NSD 评估指标）"));

children.push(p(""));
children.push(boldP("安全边界（重要）："));
children.push(p("所有 AI 模型在系统配置里都标记了 clinical_claim_allowed = false ——即 AI 输出只是“参照信号”，不是诊断结论。系统设计为辅助医生判读，不是替代医生。AI 圈出来的每个候选区域都固定有四个状态：待复核 / 已接受 / 已修改 / 已驳回。"));

children.push(p(""));
children.push(boldP("⚠️ 当前瓶颈："));
children.push(p("AI 模型目前在公开牙科 CT 数据上训练（可以看到骨头结构），但颌骨骨髓炎的真实术中荧光图像——也就是赛题核心的应用场景——我们还没有拿到。所以 AI 现在只能作为“框架能力演示”，不能承诺真实临床场景下的准确率。一旦拿到脱敏的术中样本和医生标注，可以快速启动训练。"));

// 3.3 赛点三
children.push(heading2("赛点三：标准化输出 —— 让结果可以存档、复用、对接医院系统"));

children.push(plainIntro("通俗理解：做完分析后，软件自动生成一份“病历证据包”——包含关键截图、量化数据、AI 标注结果和医生复核记录，全部打包成 ZIP。后续可以扩展成医院通用的 DICOM 格式。"));
children.push(p(""));

children.push(boldP("已经能输出的格式："));
children.push(makeTable(
  ["输出物", "格式", "包含什么"],
  [
    ["融合图", "PNG", "白光照片上叠加荧光伪彩"],
    ["热力图", "PNG", "荧光强度从蓝（低）到红（高）的彩色分布"],
    ["归一化荧光图", "PNG", "消除曝光差异后的标准灰度图"],
    ["结构化报告", "JSON", "所有参数、量化指标、输出路径、免责声明的结构化数据"],
    ["单病例报告", "Markdown", "人类可读的病例总结，可直接打开查看或转 Word"],
    ["证据包", "ZIP", "以上所有文件 + 输入的原始图的打包导出"],
  ],
  [1800, 1000, 6200]
));

children.push(p(""));
children.push(boldP("还没做的："));
children.push(bullet("DICOM Secondary Capture（把 PNG 图封装成医院影像系统能读的 DICOM 格式）"));
children.push(bullet("DICOM Structured Report（用 DICOM 标准结构化描述病灶信息）"));
children.push(bullet("PDF 正式报告（目前是 Markdown，需要加排版模板转 PDF）"));

// ════════════════════════════════════════════════════════════
// 第四章：工程成熟度
// ════════════════════════════════════════════════════════════
children.push(heading1("四、工程成熟度"));

children.push(plainIntro("一句话：代码量相当于一个中型科研项目，测试覆盖到位，文档齐备，可以一键启动演示。"));
children.push(p(""));

children.push(makeTable(
  ["指标", "数字", "说明"],
  [
    ["Python 源码", "102 个文件（72+30）", "核心框架 72 个 + 后端服务 30 个，模块化清晰"],
    ["前端组件", "14 个 Vue 组件 + 3 个页面", "Vue 3 + TypeScript + Vite 6，医学蓝主题"],
    ["API 接口", "8 个 REST 端点", "FastAPI，覆盖病例 CRUD → 分析 → 复核 → 导出全流程"],
    ["测试文件", "29 个 Python + 4 个前端", "单元测试 + 冒烟测试 + 集成测试三层体系"],
    ["研究文档", "33 份中英双语报告", "预处理 6 份 + 建模 8 份 + 规划 8 份，全部归档"],
    ["代码规范", "black + isort + flake8 + mypy", "格式化/排序/检查/类型四件套全部配置"],
    ["一键启动", "make platform", "一行命令同时拉起前后端，浏览器直接打开"],
  ],
  [1800, 2800, 4400]
));
children.push(p(""));

// ════════════════════════════════════════════════════════════
// 第五章：风险与边界
// ════════════════════════════════════════════════════════════
children.push(heading1("五、当前最大的风险和边界"));

children.push(makeTable(
  ["风险", "严重程度", "影响什么", "我们怎么应对"],
  [
    ["没有真实术中白光/ICG 样本", "🔴 高", "赛点二的 AI 只能做原型演示，不能在真实场景验证", "1) 公开 CT 数据做间接训练 2) 框架预留真实数据接口 3) 明确标注“演示用”"],
    ["没有医生标注（金标准）", "🔴 高", "AI 模型无法评估真实诊断准确率", "1) 先用图像强度统计做启发式标注 2) 报告里写清楚局限"],
    ["DICOM 封装未启动", "🟡 中", "赛点三的医院标准格式还没做", "已有 PNG/JSON 输出，DICOM 只需二次封装——开发量预估 3-5 天"],
    ["AI 真实模型未上线", "🟡 中", "后端目前用 Fixture 返回模拟结果", "nnU-Net 训练链路已通，权重到位后一小时内可切换"],
  ],
  [2200, 1000, 2400, 3400]
));
children.push(p(""));

// ════════════════════════════════════════════════════════════
// 第六章：下周可以演示什么
// ════════════════════════════════════════════════════════════
children.push(heading1("六、可以给领导看什么（15 分钟演示路线）"));

children.push(plainIntro("一句话：从打开电脑到生成证据包，全程 15 分钟。不需要 GPU，在一台普通笔记本上就能跑。"));
children.push(p(""));

children.push(boldP("第一步：启动（1 分钟）", 22));
children.push(p("打开终端，输入一行命令 make platform。浏览器自动打开软件界面。"));
children.push(p(""));

children.push(boldP("第二步：跑一个完整病例（5 分钟）", 22));
children.push(p("点击新建病例 → 拖入两张测试图片（一张白光、一张荧光）→ 调一下透明度和阈值 → 点击运行分析。软件自动生成三张对比图（融合/热图/灰度），并列出 AI 发现的异常区域和荧光强度数据。"));
children.push(p(""));

children.push(boldP("第三步：医生复核演示（3 分钟）", 22));
children.push(p("切换到医生复核页面。左边是 ROI 标注画布，右边是 AI 候选区列表。点击接受/修改/驳回，系统记录复核历史。"));
children.push(p(""));

children.push(boldP("第四步：导出证据包（1 分钟）", 22));
children.push(p("点击导出，得到一个 ZIP 文件。里面包含所有图、JSON 数据、Markdown 报告，可以直接发给同事或存档。"));
children.push(p(""));

children.push(boldP("第五步：展示研究文档体系（5 分钟）", 22));
children.push(p("打开 research/reports/ 目录，展示 33 份中英双语的预处理/建模/规划报告。外加 30+ 篇论文、11 个数据集、5 个外部模型快照的文献归档。"));

// ════════════════════════════════════════════════════════════
// 免责声明
// ════════════════════════════════════════════════════════════
children.push(p(""));
children.push(new Paragraph({
  spacing: { before: 200, after: 120 },
  border: {
    top: { style: BorderStyle.SINGLE, size: 2, color: "C1812A", space: 8 },
    left: { style: BorderStyle.SINGLE, size: 8, color: "C1812A", space: 8 },
  },
  indent: { left: 120 },
  children: [
    new TextRun({ text: "研究原型免责声明：", ...runProps(18, { bold: true, color: "8A5C11" }) }),
    new TextRun({ text: "本报告所有内容均定位为科研原型和竞赛演示，不构成临床诊断结论。AI 模型评估受限于公开数据集和模拟样本，真实临床性能需经脱敏术中数据闭环验证。", ...runProps(18, { color: "6B5018" }) }),
  ],
}));

// ════════════════════════════════════════════════════════════
// Build document
// ════════════════════════════════════════════════════════════
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
            text: "颌骨骨髓炎智能化荧光诊疗平台 — 团队进展报告",
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
  const outPath = "research/reports/planning/progress_report_v2_zh.docx";
  fs.writeFileSync(outPath, buffer);
  console.log("Written: " + outPath + " (" + buffer.length + " bytes)");
});
