const fs = require("fs");
const path = require("path");
const {
  AlignmentType,
  BorderStyle,
  Document,
  Footer,
  Header,
  HeadingLevel,
  ImageRun,
  Packer,
  PageNumber,
  Paragraph,
  ShadingType,
  Table,
  TableCell,
  TableRow,
  TextRun,
  VerticalAlign,
  WidthType,
} = require("docx");

const repoRoot = path.resolve(__dirname, "..");
const desktopScreenshots = path.join(
  repoRoot,
  "output",
  "playwright",
  "desktop-real-test",
  "20260831175827-49764",
  "screenshots",
);
const intakeScreenshots = path.join(
  repoRoot,
  "output",
  "playwright",
  "intake-case-real-test",
  "20260831175719",
  "screenshots",
);
const outputDirectory = path.join(repoRoot, "docs", "release");
const outputPath = path.join(outputDirectory, "Osteo_Vision_r28_使用说明.docx");

const FONT = "Microsoft YaHei";
const COLORS = {
  ink: "19323F",
  muted: "5D7480",
  blue: "167BA5",
  bluePale: "E8F4F8",
  teal: "157C75",
  tealPale: "E8F7F3",
  amber: "B7791F",
  amberPale: "FFF4DF",
  red: "B54242",
  redPale: "FCEAEA",
  line: "C9D9E0",
  light: "F6FAFB",
};
const PAGE = {
  width: 11906,
  height: 16838,
  margin: { top: 720, right: 800, bottom: 720, left: 800 },
};
const CONTENT_WIDTH = PAGE.width - PAGE.margin.left - PAGE.margin.right;
const CELL_BORDER = { style: BorderStyle.SINGLE, size: 1, color: COLORS.line };
const TABLE_BORDERS = {
  top: CELL_BORDER,
  bottom: CELL_BORDER,
  left: CELL_BORDER,
  right: CELL_BORDER,
  insideHorizontal: CELL_BORDER,
  insideVertical: CELL_BORDER,
};

function prefixed(value) {
  return value;
}

function run(value, options = {}) {
  return new TextRun({
    text: value,
    font: FONT,
    size: options.size ?? 21,
    color: options.color ?? COLORS.ink,
    bold: options.bold ?? false,
    italics: options.italics ?? false,
  });
}

function paragraph(value, options = {}) {
  return new Paragraph({
    alignment: options.alignment ?? AlignmentType.LEFT,
    spacing: { before: options.before ?? 0, after: options.after ?? 120, line: options.line ?? 310 },
    keepLines: true,
    children: [
      run(prefixed(value), {
        size: options.size ?? 21,
        color: options.color ?? COLORS.ink,
        bold: options.bold ?? false,
        italics: options.italics ?? false,
      }),
    ],
  });
}

function step(value) {
  return paragraph(value, { before: 0, after: 80, size: 20, color: COLORS.ink });
}

function h1(value, pageBreakBefore = false) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    pageBreakBefore,
    keepNext: true,
    children: [run(prefixed(value), { size: 31, color: COLORS.ink, bold: true })],
  });
}

function h2(value) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    keepNext: true,
    children: [run(prefixed(value), { size: 25, color: COLORS.blue, bold: true })],
  });
}

function note(value, tone = "blue") {
  const toneMap = {
    blue: { fill: COLORS.bluePale, color: COLORS.blue },
    teal: { fill: COLORS.tealPale, color: COLORS.teal },
    amber: { fill: COLORS.amberPale, color: COLORS.amber },
    red: { fill: COLORS.redPale, color: COLORS.red },
  };
  const selected = toneMap[tone];
  return new Table({
    width: { size: CONTENT_WIDTH, type: WidthType.DXA },
    columnWidths: [CONTENT_WIDTH],
    rows: [
      new TableRow({
        cantSplit: true,
        children: [
          new TableCell({
            width: { size: CONTENT_WIDTH, type: WidthType.DXA },
            margins: { top: 100, bottom: 100, left: 150, right: 150 },
            borders: TABLE_BORDERS,
            shading: { fill: selected.fill, type: ShadingType.CLEAR },
            children: [paragraph(value, { size: 19, color: selected.color, after: 0 })],
          }),
        ],
      }),
    ],
  });
}

function cell(value, width, options = {}) {
  const values = Array.isArray(value) ? value : [value];
  const textChildren = values.map((item) => {
    if (item instanceof Paragraph) {
      return item;
    }
    return paragraph(item, {
      size: options.size ?? 18,
      bold: options.bold ?? false,
      color: options.color ?? COLORS.ink,
      after: 0,
      line: 285,
    });
  });
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    margins: { top: 80, bottom: 80, left: 100, right: 100 },
    borders: TABLE_BORDERS,
    verticalAlign: VerticalAlign.CENTER,
    shading: options.fill ? { fill: options.fill, type: ShadingType.CLEAR } : undefined,
    children: textChildren,
  });
}

function table(headers, rows, widths) {
  const allRows = [
    new TableRow({
      tableHeader: true,
      cantSplit: true,
      children: headers.map((value, index) =>
        cell(value, widths[index], { fill: COLORS.bluePale, color: COLORS.blue, bold: true, size: 18 }),
      ),
    }),
    ...rows.map(
      (row, rowIndex) =>
        new TableRow({
          cantSplit: true,
          children: row.map((value, index) =>
            cell(value, widths[index], { fill: rowIndex % 2 === 0 ? "FFFFFF" : COLORS.light }),
          ),
        }),
    ),
  ];
  return new Table({
    width: { size: CONTENT_WIDTH, type: WidthType.DXA },
    columnWidths: widths,
    rows: allRows,
  });
}

function pngSize(filePath) {
  const data = fs.readFileSync(filePath);
  if (data.subarray(1, 4).toString("ascii") !== "PNG") {
    throw new Error(`Expected a PNG screenshot: ${filePath}`);
  }
  return { width: data.readUInt32BE(16), height: data.readUInt32BE(20) };
}

function figure(filePath, caption, width = 640) {
  const dimensions = pngSize(filePath);
  let imageWidth = width;
  let imageHeight = Math.round((dimensions.height / dimensions.width) * imageWidth);
  const maxHeight = 730;
  if (imageHeight > maxHeight) {
    imageHeight = maxHeight;
    imageWidth = Math.round((dimensions.width / dimensions.height) * imageHeight);
  }
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 120, after: 60 },
      keepLines: true,
      children: [
        new ImageRun({
          type: "png",
          data: fs.readFileSync(filePath),
          transformation: { width: imageWidth, height: imageHeight },
          altText: {
            title: "Osteo Vision r28 真实桌面测试截图",
            description: caption,
            name: path.basename(filePath),
          },
        }),
      ],
    }),
    paragraph(caption, { alignment: AlignmentType.CENTER, size: 17, color: COLORS.muted, after: 130, line: 260 }),
  ];
}

function screenshot(folder, fileName) {
  const filePath = path.join(folder, fileName);
  if (!fs.existsSync(filePath)) {
    throw new Error(`Required real-test screenshot is missing: ${filePath}`);
  }
  return filePath;
}

function screenshotPrefix(folder, prefix) {
  const candidate = fs
    .readdirSync(folder)
    .filter((name) => name.startsWith(prefix) && name.toLowerCase().endsWith(".png"))
    .sort()[0];
  if (!candidate) {
    throw new Error(`Required real-test screenshot prefix is missing: ${prefix}`);
  }
  return path.join(folder, candidate);
}

function buttonScreenshot(prefix, label) {
  const buttonRoot = path.join(desktopScreenshots, "buttons");
  const candidate = fs
    .readdirSync(buttonRoot)
    .filter((name) => name.startsWith(prefix) && name.includes(label) && name.toLowerCase().endsWith(".png"))
    .sort()
    .slice(-1)[0];
  if (!candidate) {
    throw new Error(`Required button screenshot is missing: ${prefix}${label}`);
  }
  return path.join(buttonRoot, candidate);
}

const SHOT = {
  startup: screenshot(desktopScreenshots, "01-startup.png"),
  ofdvdnet: screenshot(desktopScreenshots, "02-ofdvdnet-three-view.png"),
  dualChannel: screenshot(desktopScreenshots, "03-dual-channel-analysis.png"),
  annotation: screenshot(desktopScreenshots, "04-manual-annotation.png"),
  navigation: screenshot(desktopScreenshots, "05-d024-navigation.png"),
  mp4: screenshot(desktopScreenshots, "06-mp4-import-playback.png"),
  camera: screenshot(desktopScreenshots, "07-camera-live-segmentation.png"),
  intakeAdmitted: screenshot(intakeScreenshots, "01-intake-admitted.png"),
  intakeQuarantined: screenshot(intakeScreenshots, "02-intake-quarantined.png"),
  caseArchive: screenshot(intakeScreenshots, "04-case-archive-after-restart.png"),
  report: buttonScreenshot("0242-", "报告导出"),
  videoLibrary: buttonScreenshot("0234-", "公开视频库"),
  staticReview: buttonScreenshot("0239-", "静态数据复核"),
  sampleModel: buttonScreenshot("0214-", "载入示例建模"),
};

const children = [];

children.push(
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 160, after: 90 },
    children: [run("OSTEO VISION", { size: 30, color: COLORS.blue, bold: true })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 70 },
    children: [run("木中荧光辅助平台", { size: 25, color: COLORS.muted, bold: true })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 150, after: 70 },
    children: [run("r28 竞赛光盘运行包使用说明", { size: 39, color: COLORS.ink, bold: true })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 140 },
    children: [run("面向颌骨骨髓炎术中辅助决策的研发验证版平台", { size: 22, color: COLORS.muted })],
  }),
  note("本说明对应 2026-08-31 构建的 r28 Windows 离线运行包。文中全部界面图片来自该发行包的真实桌面自动化测试。", "teal"),
  ...figure(SHOT.startup, "图 1. r28 桌面应用启动后的病例工作台。窗口由唯一的 Osteo Vision Platform.exe 启动。", 540),
  table(
    ["文档项目", "发行信息"],
    [
      ["平台版本", "r28，Windows x64 离线发行包"],
      ["运行包目录", "Osteo-Vision-Competition-Disc-win32-x64-20260831-r28"],
      ["唯一启动入口", "Osteo Vision Platform.exe"],
      ["ZIP SHA256", "以随包 release-manifest.json 与交付校验记录为准"],
      ["医学用途边界", "研发验证与医生复核参考，不作为临床诊断结论。"],
    ],
    [3000, CONTENT_WIDTH - 3000],
  ),
  paragraph("本手册按正式比赛光盘运行包编写。压缩包用于传输；在另一台电脑上使用前，需先完整解压到本地文件夹，再从该文件夹双击启动入口。", { before: 140, after: 0, size: 19, color: COLORS.muted }),
);

children.push(
  h1("01 交付包、运行条件与一键启动", true),
  paragraph("r28 采用 Windows 桌面应用窗口。用户仅需使用根目录的 Osteo Vision Platform.exe；应用会管理本地服务、前端资源和三维运行时。"),
  h2("交付包完整性"),
  table(
    ["同级内容", "用途与操作要求"],
    [
      ["Osteo Vision Platform.exe", "唯一用户启动入口。双击后打开桌面应用窗口。"],
      ["resources、locales 及 DLL 文件", "受管运行时、模型、FFmpeg、界面和语言资源。必须与 exe 保持同级。"],
      ["release-manifest.json", "记录发行包文件清单、长度和 SHA256。"],
      ["verify_release.ps1", "需要核验完整性时使用；日常启动无需运行该脚本。"],
    ],
    [3000, CONTENT_WIDTH - 3000],
  ),
  note("刻录、复制或解压时请保留完整目录层级。只复制 exe 会导致运行时资源缺失。光盘可保持只读，病例、证据和日志会写入当前 Windows 用户的应用数据目录。", "amber"),
  h2("目标电脑与加速策略"),
  table(
    ["项目", "r28 行为"],
    [
      ["操作系统", "Windows 10 或 Windows 11，64 位。"],
      ["本地空间", "需要为导入 JPEG/MP4、分析产物、证据包和日志预留可写入空间。"],
      ["NVIDIA GPU", "检测到兼容 GPU 与 CUDA 驱动时，自动选择 CUDA 加速。"],
      ["CPU 降级", "CUDA 不可用、驱动不兼容或加速运行异常时，自动切换 CPU 并保留状态记录。"],
      ["光盘介质", "发行包约 5.99 GB；单层 DVD 容量不足。请使用满足容量的介质或完整复制到本机磁盘。"],
    ],
    [3000, CONTENT_WIDTH - 3000],
  ),
  h2("启动步骤"),
  step("第一步：完整解压或复制 r28 文件夹，确认 exe、resources 和 locales 仍在同一级目录。"),
  step("第二步：双击 Osteo Vision Platform.exe，并等待桌面窗口显示。无需启动浏览器、终端、Python、Conda 或网络服务。"),
  step("第三步：在顶部运行状态查看当前加速状态；可用 GPU 会显示 CUDA 路径，降级时会显示 CPU 与原因。"),
  step("第四步：从顶部导航进入数据准入、病例档案或病例工作台开始演示。"),
);

children.push(
  h1("02 数据准入与病例档案"),
  paragraph("真实 JPEG/MP4 在写入病例或进入分析前，需要完成授权、脱敏、来源和文件完整性检查。只有已准入文件可进入病例工作流。"),
  ...figure(SHOT.intakeAdmitted, "图 2. 数据准入已完成状态。界面展示交接与授权字段、JPEG/MP4 文件条目、SHA256、病例映射及准入结果。", 610),
  h2("准入操作"),
  step("第一步：进入顶部“数据准入”，记录来源机构、接收人、交接编号、授权状态和允许用途。"),
  step("第二步：选择 JPEG 或 MP4 文件，填写病例映射、输入通道和采集关系。"),
  step("第三步：执行准入检查。系统校验文件可读性、SHA256、重复项、格式、通道关系与同步配对信息。"),
  step("第四步：检查右侧准入与隔离结果。已准入文件可打开平台病例；隔离文件保留原因码，等待整改或复核。"),
  ...figure(SHOT.intakeQuarantined, "图 3. 数据准入隔离结果。隔离状态用于保留问题原因与审计轨迹，禁止直接进入病例分析。", 590),
  h2("病例档案"),
  paragraph("病例档案将病例、输入、分析、建模与复核对象关联起来。自动化测试已验证重启应用后档案仍可恢复。"),
  ...figure(SHOT.caseArchive, "图 4. 重启后恢复的病例档案。病例对象、输入状态和关联关系保留在应用数据目录。", 580),
);

children.push(
  h1("03 病例工作台：MP4、JPEG 与公开三视图演示"),
  paragraph("官方主输入为 MP4 视频文件和 JPEG 图像文件。病例工作台提供单路视频、双通道视频、合成三视图和 JPEG 融合等受控流程。"),
  h2("MP4 视频分析"),
  step("第一步：在左侧选择“文件输入”和“MP4 视频”，再选择单路视频、双通道视频或合成三视图。"),
  step("第二步：选择已准入 MP4。单路视频可设置重点复核时间点，再启动离线关键帧分析。"),
  step("第三步：在结果区查看视频、融合图、热图、归一化图和候选区，并在完成后导出证据包。"),
  ...figure(SHOT.mp4, "图 5. 已导入 MP4 的播放与关键帧分析界面。运行结果会在同一病例工作台内呈现。", 620),
  h2("公开 OFDVDnet 三视图演示"),
  paragraph("内置 OFDVDnet 公开三视图荧光代理数据，可离线展示白光、荧光和设备叠加三路拆分、同步与分析。该数据用于工程演示，不代表真实术中 ICG 颌骨骨髓炎病例。"),
  ...figure(SHOT.ofdvdnet, "图 6. OFDVDnet 合成三视图在病例工作台内拆分为白光、荧光与设备叠加通道。", 640),
  h2("JPEG 图像融合"),
  step("第一步：在“文件输入”下选择“JPEG 图像”。"),
  step("第二步：依次选择白光 JPEG、ICG JPEG，以及可选的设备叠加 JPEG。"),
  step("第三步：点击“开始图像融合分析”，在融合图、热图、归一化图和候选区内进行医生复核。"),
  note("JPEG 与 MP4 的导入路径优先使用已准入病例文件。演示数据路径均解析到发行包内受控资源，运行包不依赖开发机绝对路径。", "teal"),
);

children.push(
  h1("04 双通道实时分析"),
  paragraph("双通道流程用于已配对的白光与荧光输入。r28 会建立同步会话并生成融合结果资源，适用于双通道 MP4 或 JPEG 成对分析。"),
  ...figure(SHOT.dualChannel, "图 7. 双通道实时分析完成后的真实桌面测试界面。白光、荧光、配准融合与 AI 风险提示同时呈现。", 640),
  h2("操作步骤"),
  step("第一步：在病例工作台选择“文件输入”，再选择“双通道视频”或“JPEG 图像”。"),
  step("第二步：选择白光和荧光文件；视频流程可添加可选设备叠加视频。"),
  step("第三步：点击“开启双通道实时分析”或“开始图像融合分析”。状态会显示会话就绪、同步偏移和分析完成情况。"),
  step("第四步：检查配准融合结果、AI 分割与风险提示；必要时使用“复位自动偏移”或准备同步预览。"),
  note("发布包中的双通道演示已经过真实按钮自动化测试。历史的开发机输入路径限制已在发行包中替换为受控的本地数据根路径。", "teal"),
);

children.push(
  h1("05 摄像头输入与实时分割"),
  paragraph("摄像头模式用于可用本机摄像头的工程演示。首次启用时，Windows 或应用会请求摄像头访问权限。"),
  ...figure(SHOT.camera, "图 8. 摄像头实时分割的真实桌面测试界面。页面显示当前视频流、实时分割状态与分析控件。", 620),
  h2("操作步骤"),
  step("第一步：在病例工作台选择“浏览器摄像头”。"),
  step("第二步：在权限提示中允许摄像头访问，选择可用设备后等待预览建立。"),
  step("第三步：点击“开始实时分割”。系统按连续分析节奏更新信号候选、边界风险与不确定区域提示。"),
  step("第四步：需要保存时点击“抓取关键帧分析”；结束时点击“关闭摄像头”。"),
  note("摄像头不可用、被系统占用或权限被拒绝时，界面会保留可追溯状态。可切换到文件输入继续完成离线演示。", "amber"),
);

children.push(
  h1("06 三维导航与示例建模"),
  paragraph("三维导航页面运行独立的本地三维渲染资源，并与病例、模型、复核和证据数据保持版本化关联。三维运行时不可用时，病例工作台仍保留二维证据和复核路径。"),
  ...figure(SHOT.navigation, "图 9. D024 公开下颌参考在病例三维导航工作台中的 L0 参考视图。左侧图标已使用固定尺寸与居中对齐。", 620),
  h2("内置示例数据"),
  table(
    ["示例", "可演示内容与边界"],
    [
      ["D024 公开下颌参考", "离线加载下颌表面参考、检查模型显示、重置视角和保留病例关联。"],
      ["D036 ToothFairy2 MHA", "发行包内的示例建模体数据，用于“载入示例建模”与建模任务流程演示。"],
      ["OFDVDnet 三视图", "可与病例工作台输入、关键帧、人工标注和三维参考共同演示。"],
    ],
    [3200, CONTENT_WIDTH - 3200],
  ),
  ...figure(SHOT.sampleModel, "图 10. 三维导航页面的“载入示例建模”控件。示例任务在发行包内读取受控 MHA 数据。", 560),
  h2("操作步骤"),
  step("第一步：进入“三维导航”，点击“同步病例数据”。"),
  step("第二步：点击“载入示例建模”，或选择已准入的 CBCT、STL / GLB 文件。"),
  step("第三步：提交建模并查看处理阶段、已用时间和失败原因；加载完成后可拖动旋转视图并使用“重置视角”。"),
  step("第四步：将模型、坐标与配准状态提交医生复核。当前示例默认处于 L0 未配准参考状态。"),
  note("三维显示用于研发验证和医生复核。L1 静态配准与 L2 离线动态 AR 需在受控坐标、标定与复核证据完整后提升验证等级。", "amber"),
);

children.push(
  h1("07 人工标注与医生复核"),
  paragraph("人工标注页面用于从病例 JPEG、MP4 关键帧和模型候选区进入复核。标注数据保留来源、版本、状态和训练准入边界。"),
  ...figure(SHOT.annotation, "图 11. 人工标注与复核工作台。界面提供画笔、橡皮擦、多边形、撤销、重做、缩放、标签和版本操作。", 640),
  h2("操作步骤"),
  step("第一步：进入“人工标注与复核”，选择病例、关键帧或候选区来源。"),
  step("第二步：使用画笔、橡皮擦或多边形标注暴露骨面、荧光信号、边界风险、不确定区域及骨活性相关复核标签。"),
  step("第三步：保存草稿或提交复核。界面保存原始图像坐标、像素掩膜、版本和复核状态。"),
  step("第四步：只有可信医生身份提交并完成复核的标注可进入高权重训练清单。工程标注和草稿保持独立来源边界。"),
);

children.push(
  h1("08 报告导出、公开视频库与静态数据复核"),
  h2("报告导出"),
  paragraph("报告导出页面汇集病例、输入、分析、量化、复核和证据记录，用于生成可追溯研发验证材料。"),
  ...figure(SHOT.report, "图 12. 报告导出页面的真实桌面测试截图。导出前请确认病例与复核状态。", 570),
  step("第一步：进入“报告导出”，选择当前病例与需要纳入的分析结果。"),
  step("第二步：检查输入来源、运行状态、量化数据、医生复核与医学边界提示。"),
  step("第三步：执行导出，并将证据包与病例档案一并保留。"),
  h2("公开视频库"),
  paragraph("公开视频库用于浏览本地已登记的公开视频资源、预览并导入病例。来源与数据域应随病例保存。"),
  ...figure(SHOT.videoLibrary, "图 13. 公开视频库页面的真实桌面测试截图。可刷新视频库、预览条目并导入病例。", 570),
  h2("静态数据复核"),
  paragraph("静态数据复核用于查看待审核的输入、标注或数据对象，维持训练准入与医生复核边界。"),
  ...figure(SHOT.staticReview, "图 14. 静态数据复核页面的真实桌面测试截图。通过刷新队列查看待复核对象。", 570),
);

children.push(
  h1("09 推荐比赛演示路径"),
  paragraph("以下路径覆盖 r28 的离线输入、融合处理、AI 辅助、人工复核、三维参考和证据导出主流程。"),
  table(
    ["顺序", "建议操作", "可见证据"],
    [
      ["01", "启动桌面应用并等待运行状态稳定。", "窗口、加速状态与顶部导航。"],
      ["02", "在数据准入中导入内置 JPEG/MP4 示例并完成检查。", "准入记录、SHA256 与病例映射。"],
      ["03", "进入病例工作台，载入 OFDVDnet 合成三视图。", "白光、荧光与设备叠加通道。"],
      ["04", "开启双通道实时分析，检查同步、融合与风险提示。", "融合结果、AI 分割和状态记录。"],
      ["05", "进入人工标注与复核，保存草稿或提交复核。", "标注工具、标签和版本状态。"],
      ["06", "进入三维导航，载入 D024 或 D036 示例建模。", "模型、L0 状态与病例关联。"],
      ["07", "在报告导出中生成证据包。", "可追溯病例分析材料。"],
    ],
    [900, 5200, CONTENT_WIDTH - 6100],
  ),
  note("内置 OFDVDnet、D024 和 D036 示例均用于公开数据或工程演示边界内的可运行展示。它们不构成真实术中 ICG 颌骨骨髓炎病例证据。", "amber"),
);

children.push(
  h1("10 常见问题与安全边界"),
  h2("常见问题"),
  table(
    ["现象", "处理建议"],
    [
      ["双击 exe 后无法启动", "检查 exe 是否仍与 resources、locales 和相邻运行时文件同级；在完整目录内执行 verify_release.ps1 核验发行清单。"],
      ["压缩包拷到另一台电脑后无法运行", "确认 ZIP 已完整解压，未从压缩软件预览窗口直接运行；检查目标电脑为 64 位 Windows 且有可写用户目录。"],
      ["没有 GPU 或 CUDA 状态不可用", "应用会自动使用 CPU。可继续演示 JPEG、MP4、融合、人工标注和证据导出。"],
      ["摄像头没有画面", "检查 Windows 摄像头权限、设备连接和占用状态；可切换文件输入继续离线演示。"],
      ["双通道分析无法开始", "确认选择了白光与荧光成对输入，并且文件已进入当前病例或发行包受控演示数据目录。"],
      ["三维模型未显示", "等待建模阶段完成，查看失败原因；点击重新连接或重置视角，并保留二维证据与复核流程。"],
      ["无法写入病例或导出证据", "确认当前 Windows 用户的应用数据目录可写；将完整发行包复制到本机磁盘后重试。"],
    ],
    [3000, CONTENT_WIDTH - 3000],
  ),
  h2("医学与数据安全边界"),
  paragraph("平台输出用于研发验证、工程演示和医生复核辅助。系统不会提供自动临床诊断，也不会替代医生判断。", { color: COLORS.red, bold: true }),
  paragraph("真实数据应在机构授权、脱敏、交接登记和批次准入完成后进入平台。未准入、隔离、草稿或未复核对象不得作为训练或临床结论依据。"),
  h2("r28 验证证据摘要"),
  table(
    ["验证范围", "结果"],
    [
      ["桌面功能测试", "28 项通过；按钮审计覆盖 243 个可操作控件。"],
      ["数据准入与病例档案", "专项 27 项通过；包括隔离处理与重启恢复。"],
      ["后端、前端与三维运行时", "后端 366 项、前端 255 项、三维运行时 21 项通过。"],
      ["桌面宿主与退出清理", "6 项通过；覆盖启动、就绪、端口关闭与后端进程树退出。"],
      ["迁移与压缩包校验", "完整 ZIP 解压、清单校验、绝对路径检查及专项真实测试均通过。"],
    ],
    [3600, CONTENT_WIDTH - 3600],
  ),
  paragraph("本说明结束。请将本 Word 文档与完整 r28 发行包一并保存，以便现场按图完成离线展示与核验。", { before: 120, color: COLORS.muted }),
);

const doc = new Document({
  creator: "Osteo Vision Team",
  title: "Osteo Vision r28 使用说明",
  description: "竞赛光盘 Windows 离线运行包使用说明，含真实桌面测试截图。",
  styles: {
    default: {
      document: {
        run: { font: FONT, size: 21, color: COLORS.ink },
        paragraph: { spacing: { after: 120, line: 310 } },
      },
    },
    paragraphStyles: [
      {
        id: "Heading1",
        name: "Heading 1",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { font: FONT, size: 31, bold: true, color: COLORS.ink },
        paragraph: { spacing: { before: 200, after: 160 }, outlineLevel: 0 },
      },
      {
        id: "Heading2",
        name: "Heading 2",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { font: FONT, size: 25, bold: true, color: COLORS.blue },
        paragraph: { spacing: { before: 150, after: 100 }, outlineLevel: 1 },
      },
    ],
  },
  sections: [
    {
      properties: { page: { size: { width: PAGE.width, height: PAGE.height }, margin: PAGE.margin } },
      headers: {
        default: new Header({
          children: [
            new Paragraph({
              spacing: { after: 70 },
              border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: COLORS.blue, space: 1 } },
              children: [run("Osteo Vision 木中荧光辅助平台 | r28 使用说明", { size: 16, color: COLORS.blue, bold: true })],
            }),
          ],
        }),
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              spacing: { before: 70, after: 0 },
              children: [
                run("Osteo Vision r28 使用说明 | 第 ", { size: 16, color: COLORS.muted }),
                new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: COLORS.muted }),
                run(" 页", { size: 16, color: COLORS.muted }),
              ],
            }),
          ],
        }),
      },
      children,
    },
  ],
});

fs.mkdirSync(outputDirectory, { recursive: true });
Packer.toBuffer(doc)
  .then((buffer) => {
    fs.writeFileSync(outputPath, buffer);
    process.stdout.write(`Created ${outputPath} (${buffer.length} bytes)\n`);
  })
  .catch((error) => {
    process.stderr.write(`${error.stack || error}\n`);
    process.exitCode = 1;
  });
