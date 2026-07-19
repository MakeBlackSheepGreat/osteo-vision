const fs = require("fs");
const path = require("path");
const {
  AlignmentType,
  BorderStyle,
  Document,
  ExternalHyperlink,
  Footer,
  HeadingLevel,
  LevelFormat,
  Packer,
  PageNumber,
  Paragraph,
  ShadingType,
  Table,
  TableCell,
  TableOfContents,
  TableRow,
  TextRun,
  WidthType,
} = require("docx");

const outputPath = path.resolve(
  __dirname,
  "osteo_vision_competition_gap_solutions_archive_20260710_zh.docx",
);

const PAGE_WIDTH = 11906;
const PAGE_HEIGHT = 16838;
const CONTENT_WIDTH = 9026;
const colors = {
  navy: "17324D",
  blue: "2563A6",
  cyan: "DCECF4",
  pale: "F3F6F8",
  green: "E3F1E8",
  amber: "FFF1D6",
  red: "FCE5E5",
  border: "B8C4CC",
  text: "1F2933",
  muted: "5B6770",
  white: "FFFFFF",
};

const statusFill = {
  "当前可直接落地": colors.green,
  "需企业/医院/实验团队配合": colors.amber,
  "只能降低风险或补论证": colors.cyan,
  "当前无可靠替代": colors.red,
};

function run(text, options = {}) {
  return new TextRun({
    text,
    font: options.font || "Microsoft YaHei",
    size: options.size || 21,
    bold: options.bold || false,
    color: options.color || colors.text,
    italics: options.italics || false,
  });
}

function p(text, options = {}) {
  return new Paragraph({
    alignment: options.alignment || AlignmentType.LEFT,
    spacing: { before: options.before || 0, after: options.after ?? 110, line: 330 },
    indent: options.indent ? { firstLine: options.indent } : undefined,
    keepNext: options.keepNext || false,
    children: [run(text, options)],
  });
}

function heading(text, level = 1) {
  const levelMap = {
    1: HeadingLevel.HEADING_1,
    2: HeadingLevel.HEADING_2,
    3: HeadingLevel.HEADING_3,
  };
  return new Paragraph({
    heading: levelMap[level],
    keepNext: true,
    children: [run(text, { bold: true })],
  });
}

function bullet(text, reference = "bullet-main") {
  return new Paragraph({
    numbering: { reference, level: 0 },
    spacing: { after: 80, line: 315 },
    children: [run(text)],
  });
}

function linkParagraph(label, url, suffix = "") {
  return new Paragraph({
    spacing: { after: 70, line: 300 },
    children: [
      new ExternalHyperlink({
        link: url,
        children: [new TextRun({ text: label, style: "Hyperlink", font: "Microsoft YaHei", size: 20 })],
      }),
      run(suffix, { size: 20, color: colors.muted }),
    ],
  });
}

const border = { style: BorderStyle.SINGLE, size: 4, color: colors.border };
const borders = { top: border, bottom: border, left: border, right: border };

function cell(text, width, options = {}) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    borders,
    shading: { fill: options.fill || colors.white, type: ShadingType.CLEAR },
    margins: { top: 95, bottom: 95, left: 105, right: 105 },
    verticalAlign: "center",
    children: [
      new Paragraph({
        spacing: { after: 0, line: 280 },
        alignment: options.alignment || AlignmentType.LEFT,
        children: [run(text, { size: options.size || 18, bold: options.bold, color: options.color })],
      }),
    ],
  });
}

function table(headers, rows, widths) {
  return new Table({
    width: { size: CONTENT_WIDTH, type: WidthType.DXA },
    columnWidths: widths,
    rows: [
      new TableRow({
        tableHeader: true,
        children: headers.map((header, index) =>
          cell(header, widths[index], { fill: colors.navy, bold: true, color: colors.white, alignment: AlignmentType.CENTER }),
        ),
      }),
      ...rows.map(
        (row, rowIndex) =>
          new TableRow({
            cantSplit: true,
            children: row.map((value, index) => {
              const fill = index === 2 && statusFill[value] ? statusFill[value] : rowIndex % 2 ? colors.pale : colors.white;
              return cell(value, widths[index], { fill, bold: index === 0 });
            }),
          }),
      ),
    ],
  });
}

function callout(title, body, fill = colors.cyan) {
  return new Table({
    width: { size: CONTENT_WIDTH, type: WidthType.DXA },
    columnWidths: [CONTENT_WIDTH],
    rows: [
      new TableRow({
        children: [
          new TableCell({
            width: { size: CONTENT_WIDTH, type: WidthType.DXA },
            borders,
            shading: { fill, type: ShadingType.CLEAR },
            margins: { top: 130, bottom: 130, left: 160, right: 160 },
            children: [
              new Paragraph({ spacing: { after: 70 }, children: [run(title, { bold: true, size: 21, color: colors.navy })] }),
              p(body, { after: 0, size: 19 }),
            ],
          }),
        ],
      }),
    ],
  });
}

const gapRows = [
  ["新型荧光造影剂", "已具备 ICG、四环素/骨自发荧光、骨靶向和细菌靶向文献链", "需企业/医院/实验团队配合", "形成明确候选结构与验证矩阵；原创性能需合成、光谱和生物学验证"],
  ["真实目标域数据", "未发现公开的颌骨骨髓炎白光/ICG像素标注视频集", "当前无可靠替代", "采用公开荧光代理、骨髓炎公开视频、CBCT代理和后续小金标准集分层推进"],
  ["医生金标准", "现阶段暂缺医生关键帧/ROI标注", "需企业/医院/实验团队配合", "SAM 2/CVAT预标注，医生仅复核高价值关键帧"],
  ["历史指标泄漏", "同源视频帧可能跨训练集和验证集", "当前可直接落地", "按 source_video_id/case_id 重划分并重训，历史指标降级"],
  ["多 mask 模型全零", "当前训练记录显示 Dice、IoU和预测阳性比例为0", "当前可直接落地", "先做标签审计与小样本过拟合，再调整采样、损失和阈值"],
  ["双通道 AI", "现有AI链路以单幅RGB关键帧为主", "当前可直接落地", "双编码器中间融合，完成单模态与融合消融"],
  ["配准与标定", "当前主要为轻量平移配准", "需企业/医院/实验团队配合", "离线双通道标定、在线残差校正、荧光仿体质控"],
  ["ICG 定量", "绝对强度受曝光、距离、剂量和运动影响", "当前可直接落地", "背景扣除、运动补偿、归一化时间强度曲线"],
  ["4K实时分析", "当前属于关键帧播放同步分析", "当前可直接落地", "4K播放与低分辨率异步AI双速管线，保留关键帧表述"],
  ["不确定性", "已有风险/不确定性输出，缺系统校准", "当前可直接落地", "温度缩放、TTA/集成方差、ECE/Brier与复核优先级"],
  ["三维空间映射", "具备CBCT三维工作台，术中坐标尚未注册", "需企业/医院/实验团队配合", "保持术前参考定位；完整导航需跟踪、配准与误差验证"],
  ["最终参赛交付", "仓库未发现按官方三项重排的最终Word/PDF", "当前可直接落地", "按造影剂、融合、AI、设备适配、证据边界重写并冻结"],
];

const children = [
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 760, after: 220 },
    children: [run("颌骨骨髓炎智能化荧光诊疗", { bold: true, size: 42, color: colors.navy })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 170 },
    children: [run("赛题差距、困难与国内外解决路径归档报告", { bold: true, size: 32, color: colors.blue })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 80 },
    children: [run("只读审计与互联网资料复核归档", { size: 22, color: colors.muted })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 540 },
    children: [run("归档日期：2026年7月10日", { size: 21, color: colors.muted })],
  }),
  callout(
    "用途与医学边界",
    "本报告用于比赛方案决策、研发验证和团队协作。所有模型输出均定位为术中参考信号、风险提示和医生复核辅助。代理数据、伪标注和公开异域数据所得指标不能用于声称真实术中ICG颌骨骨髓炎临床性能。",
    colors.amber,
  ),
  new Paragraph({ children: [new TextRun("")] }),
  new TableOfContents("目录", { hyperlink: true, headingStyleRange: "1-3" }),

  heading("零、R01-R08修复归档更新", 1),
  p("2026年7月10日已完成前八项问题的比赛版工程修复。本节记录当前可核验状态，后文章节保留问题发现时的背景、互联网解决路径和外部依赖，便于追溯决策过程。", { indent: 420 }),
  table(
    ["编号", "修复状态", "当前证据"],
    [
      ["R01 视频源级泄漏", "已完成", "192帧/48视频源按源分组；train/val/test为28/14/6源；leakage_detected=false"],
      ["R02 多mask全零", "工程修复完成", "独立双头监督、有效性mask和逐头阈值；测试两个头空mask率均为0"],
      ["R03 0.9093可信度", "已完成", "旧值撤回泛化证据地位；独立测试Dice 0.9214，视频级95% CI 0.9127-0.9302"],
      ["R04 最终证据链", "已完成比赛版索引", "证据已按造影剂、多模态融合、AI判读、设备适配和医学边界重排"],
      ["R05 双通道AI", "已完成代理基线", "四组消融均可运行；验证集选择early fusion；独立测试Dice 0.8654"],
      ["R06 ICG动态定量", "已完成软件实现", "背景扣除、归一化时间强度曲线、达峰时间、上升斜率、AUC和质控"],
      ["R07 4K稳定性", "已完成关键帧验证", "3840x2160、45 tiles、5次运行；端到端P50/P95为3481.8/7577.3 ms"],
      ["R08 不确定性", "已完成技术校准", "温度缩放、预测熵、TTA方差、ECE/Brier、uncertain_mask和复核优先级"],
    ],
    [1650, 1900, 5476],
  ),
  callout(
    "更新后的证据边界",
    "上述结果均用于比赛版工程验证。D046指标来自公开非目标域视频伪标注，bone_gate来自待复核prompt-assisted种子；造影剂实物、真实目标域病例与医生金标准、企业显微镜实机验证仍属于外部依赖。",
    colors.amber,
  ),
  heading("0.1 无泄漏单mask评估", 2),
  p("新主线候选使用视频源级分组清单训练，验证集确定阈值0.45，测试集只执行一次独立评估。测试Dice为0.9214、IoU为0.8546、Boundary F1为0.9844，空mask率和过分割率均为0；ECE为0.00524，Brier score为0.01973。所有结果只代表D046伪标注代理任务。", { indent: 420 }),
  heading("0.2 多mask与双通道模型", 2),
  p("多mask训练已按图像聚合标签，并为荧光信号头和骨面门控头提供独立有效性mask、损失和阈值扫描。测试Dice分别为0.4984和0.8722，两个头均保持非空。双通道模型完成白光单模态、荧光单模态、早期融合和中间融合四组消融，验证集选择early fusion，测试Dice为0.8654。白光由源图亮度合成，结果只证明工程可运行性。", { indent: 420 }),
  heading("0.3 动态定量、4K与不确定性", 2),
  p("视频汇总已加入稀疏关键帧时间强度曲线，输出背景扣除值、基线到峰值归一化、达峰时间、最大上升斜率、AUC和曲线质控。官方4K尺寸的五次强制tiling验证全部通过，模型推理P50为1587.4 ms，端到端P50/P95为3481.8/7577.3 ms。推理配置已启用温度1.4138和TTA不确定性，输出risk_mask、uncertain_mask与医生复核优先级。", { indent: 420 }),

  heading("一、执行摘要", 1),
  p("项目已经形成较完整的平台软件演示闭环，具备4K JPEG/MP4输入、白光/荧光融合、关键帧分割提示、医生复核和证据导出能力。按官方三项答题要求衡量，主要缺口集中在新型造影剂方案证据、真实目标域数据、无泄漏AI评价、企业显微镜实机适配以及最终参赛文档。", { indent: 420 }),
  p("互联网与学术资料复核显示，多数困难存在可执行的比赛版解决路径。三项能力仍依赖外部协作：原创造影剂实物验证、真实目标域病例及医生金标准、企业显微镜实机验证。公开数据和工程方法可以降低风险、完善论证并维持软件闭环，无法生成缺失的临床证据。", { indent: 420 }),
  table(
    ["维度", "当前判断"],
    [
      ["软件工程演示成熟度", "约75%：主流程可演示，仍需长视频、设备样片和交付冻结验证"],
      ["官方三项答题整体就绪度", "约45%-55%：第二项较强，第三项为代理工程验证，第一项仍需形成独立方案"],
      ["真实目标域与医学证据成熟度", "低于20%：缺真实术中白光/ICG病例、医生像素级标注和目标域独立测试"],
      ["提交风险", "截止2026年7月30日；最终Word/PDF、无泄漏重评估和造影剂章节需优先收束"],
    ],
    [2950, 6076],
  ),

  heading("二、官方赛题目标与当前距离", 1),
  p("依据本地完整赛题方案和赛题方设备技术文档，完整作品需覆盖三项核心内容：新型荧光造影剂设计、多模态白光/荧光图像融合与处理、AI辅助显微成像判读。设备输入边界包括3840×2160摄录、USB3.0存储、JPEG图片和MP4视频。", { indent: 420 }),
  table(
    ["官方要求", "当前状态", "成熟度判断", "决定性缺口"],
    [
      ["新型荧光造影剂设计", "已有ICG基线、四环素/自发荧光、骨靶向及细菌靶向文献", "15%-25%", "缺独立候选结构、光谱适配、稳定性、毒性及选择性验证"],
      ["多模态融合与处理", "具备4K输入、背景扣除、配准、伪彩、融合、ROI定量和播放同步", "60%-70%", "缺真实双通道同步样片、设备标定和连续实机验证"],
      ["AI辅助显微判读", "具备checkpoint、tiling、候选区、风险/不确定性和医生复核", "40%-50%", "缺目标域标注、无泄漏独立评价和显式双通道模型"],
      ["企业显微镜集成", "文件格式已对齐官方边界", "35%-45%", "缺通道编码、时间同步、曝光、倍率、滤光片和长视频实测"],
      ["最终作品交付", "已有多份阶段报告和软件证据", "20%-30%", "缺按三项核心要求重排的最终Word/PDF和冻结版本"],
    ],
    [2050, 2750, 1300, 2926],
  ),

  heading("三、困难与解决路径总表", 1),
  p("以下结论采用四级分类，便于团队区分可立即推进事项与外部依赖。"),
  table(["困难", "当前证据", "解决类别", "建议路径"], gapRows, [1670, 2520, 2030, 2806]),

  heading("四、逐项解决方案", 1),
  heading("4.1 新型荧光造影剂", 2),
  p("建议形成“骨定位 + 感染识别 + 近红外发光”的候选设计框架。骨定位端可采用磷酸基或双膦酸基，提高对羟基磷灰石的亲和力；感染识别端可评估万古霉素、IsaA抗体或金黄色葡萄球菌核酸酶激活底物；发光端优先考虑接近企业ICG检测窗口的七甲川菁类染料。", { indent: 420 }),
  bullet("骨靶向证据：磷酸化近红外染料已显示骨矿物亲和与长期滞留能力。"),
  bullet("细菌靶向证据：Vanco-800CW可识别革兰阳性菌及相关生物膜，已有动物、取出内固定物和人体尸体模型证据。"),
  bullet("候选限制：颌骨骨髓炎可能为多菌种感染；单一万古霉素靶点覆盖有限。"),
  bullet("光学限制：Vanco-800CW峰值与ICG通道接近但不完全一致，需获取企业滤光片透过曲线。"),
  callout("结论分类", "候选设计和文献论证可直接完成；合成、纯化、光谱、细胞、组织选择性及安全性验证需要化学、药理、口腔病理和实验团队协作。"),

  heading("4.2 四环素与骨自发荧光保底路径", 2),
  p("四环素标记与骨自发荧光在颌骨坏死、颌骨放射性坏死及慢性硬化性下颌骨髓炎中已有边界提示研究。该路线可支撑坏死骨与活性骨差异的科学机制，并可设计为造影剂对照组或扩展通道。其激发通常位于蓝光范围，和企业ICG近红外通道存在明显光谱差异。", { indent: 420 }),
  callout("结论分类", "该路线适合降低造影剂章节的论证风险，无法单独满足原创近红外造影剂的全部验证要求。", colors.amber),

  heading("4.3 真实目标域数据缺失", 2),
  p("本轮未核验到公开的“颌骨骨髓炎 + 白光/ICG + 可下载MP4 + 像素级标注”数据集。检索中出现的所谓MICCAI ICG-SEG仓库链接返回404；SurgeryVideoQA提供视频问答数据，未提供荧光分割mask。", { indent: 420 }),
  bullet("公开荧光工程代理：OnLume/Dryad与OFDVDnet，可验证双通道、去噪、融合、低剂量和时序处理。"),
  bullet("骨髓炎真实公开视频：本地清单已记录25个非荧光骨髓炎视频文件，可用于手术场景、视频输入和自监督预训练。"),
  bullet("口腔多光谱代理：MODID可提供口腔组织多光谱先验，但其波段和ICG目标域不同。"),
  bullet("CBCT层：ToothFairy2、D024/D025及少量医院CBCT用于颌骨解剖、三维表面和术前证据。"),
  bullet("目标域层：后续企业/医院样片只用于微调、标定和独立测试，必须按病例和视频源隔离。"),
  callout("结论分类", "公开资料足以维持工程验证闭环；真实目标域临床性能没有可靠公开替代。"),

  heading("4.4 医生标注与小金标准集", 2),
  p("采用SAM 2视频传播和CVAT复核工作流，可以把医生工作量集中到高价值关键帧。建议先由工程人员完成帧筛选、提示框和初始mask，再由医生执行接受、修改或驳回。", { indent: 420 }),
  bullet("首批目标：按不同视频源选择50-100个关键帧，覆盖暴露骨、软组织、器械遮挡、强弱荧光和边界模糊场景。"),
  bullet("双人独立复核10%-20%样本，记录一致性和分歧仲裁。"),
  bullet("accepted/modified进入高权重训练；rejected进入负例或错误分析；review_required不得进入金标准测试。"),
  bullet("测试集先锁定，后续模型和伪标签不得反向污染测试集。"),
  callout("结论分类", "工具链可直接部署；标签的医学有效性仍依赖医生复核。"),

  heading("4.5 历史指标泄漏与可信评估", 2),
  p("现有关键帧伪标签以帧级sample_id进行划分，同一源视频的相邻帧可能同时进入训练集和验证集。由此得到的Dice 0.9093存在明显乐观偏差。", { indent: 420 }),
  bullet("先按source_video_id或case_id分组切分，再从每组抽取关键帧。"),
  bullet("重新训练全部候选模型，旧指标只保留为历史代理实验。"),
  bullet("报告Dice、IoU、Boundary F1、空mask率、过分割率、灵敏度、特异度和视频级bootstrap置信区间。"),
  bullet("真实医生标注测试集与伪标签测试集分开报告，禁止混合为单一临床指标。"),
  callout("结论分类", "该问题完全由项目内部解决，且属于提交前最高优先级。", colors.green),

  heading("4.6 多 mask 模型全零", 2),
  p("当前多mask训练结果为零时，首要任务是验证标签、损失和坐标链路。继续替换网络架构无法自动修复空标签或极端类别不平衡。", { indent: 420 }),
  bullet("统计每个mask的非空率、阳性面积比例、复核状态、空间尺寸和图像对应关系。"),
  bullet("先让模型过拟合4-8个有效样本，确认前向、损失、反向和阈值链路。"),
  bullet("采用正样本patch采样、BCE + Dice/Tversky、多头独立损失和逐头阈值扫描。"),
  bullet("bone_gate_mask缺医生或prompt复核时继续保持不可用/待复核状态。"),
  callout("结论分类", "训练链路可直接修复；有效骨面标签仍依赖人工复核。"),

  heading("4.7 白光/荧光联合AI", 2),
  p("推荐以双编码器中间融合为首个可运行基线。白光分支学习骨面纹理、器械和解剖边界；荧光分支学习信号强度、灌注变化和时序特征；融合模块输出骨面门控、荧光信号、风险和不确定性四类mask。", { indent: 420 }),
  bullet("完成四组消融：白光单模态、荧光单模态、输入级早期融合、特征级中间融合。"),
  bullet("加入通道缺失训练和质量门控，避免单通道异常导致无提示输出。"),
  bullet("使用公开配对荧光视频证明工程能力，目标域临床指标继续留空。"),
  callout("结论分类", "模型结构、训练脚本和推理adapter可直接实现；目标域有效性需要真实双通道数据。"),

  heading("4.8 配准、标定与设备适配", 2),
  p("离线标定应覆盖两通道内参、畸变、相对位姿、尺度和工作距离；在线阶段再以互信息、ECC或光流进行残差校正。使用含ICG或近红外荧光材料的组织仿体测量检测下限、均匀性、信噪比、畸变和通道偏移。", { indent: 420 }),
  bullet("企业需确认白光/NIR原始通道是否分别导出，以及MP4中的通道布局。"),
  bullet("企业需提供同步方式、时间戳、帧率、曝光、增益、倍率、工作距离和滤光片曲线。"),
  bullet("若设备只输出合成overlay，平台可做显示与量化验证，无法恢复真实原始双通道。"),
  callout("结论分类", "算法和标定方案成熟；真实集成结论需要企业设备资料与实机样片。", colors.amber),

  heading("4.9 ICG动态定量", 2),
  p("单帧绝对强度受设备、曝光、距离、组织表面、注射剂量和运动影响。建议将量化主线调整为背景扣除、运动补偿和归一化时间强度曲线，并输出到峰时间、归一化上升斜率、AUC和曲线质量。", { indent: 420 }),
  bullet("锁定曝光、增益、照明、工作距离和采集时长。"),
  bullet("记录剂量、注射时间、注射速率和可能的动脉输入函数。"),
  bullet("对运动、出血、器械遮挡和饱和帧设置质量标记。"),
  callout("结论分类", "软件算法可直接落地；跨病例阈值需要标准化协议和真实样本验证。"),

  heading("4.10 4K关键帧近实时分析", 2),
  p("比赛版采用双速管线更稳妥：4K原视频保持正常播放，AI在缩放帧或ROI上异步运行；关键帧执行4K tiling，关键帧之间使用光流或视频分割传播。", { indent: 420 }),
  bullet("硬件解码优先使用NVDEC/FFmpeg或等价路径。"),
  bullet("推理层可评估TensorRT FP16、异步队列和丢帧策略。"),
  bullet("记录解码、预处理、推理、后处理和显示的分阶段延迟及P95。"),
  bullet("界面与报告继续标记keyframe-based playback analysis。"),
  callout("结论分类", "关键帧近实时可直接推进；4K逐帧30 FPS需要目标硬件实测后再作判断。"),

  heading("4.11 不确定性与医生复核优先级", 2),
  p("技术性不确定性可以通过温度缩放、测试时增强方差或深度集成获得，并与时序跳变、通道缺失和质量异常合并为复核优先级。", { indent: 420 }),
  bullet("报告ECE、Brier score、可靠性图和选择性覆盖率。"),
  bullet("高不确定性帧优先进入医生复核队列。"),
  bullet("代理标签只能用于评估模型稳定性，无法校准疾病判断正确性。"),
  callout("结论分类", "技术性不确定性可直接实现；临床风险校准需要医生金标准和目标域队列。"),

  heading("4.12 三维工作台与术中空间映射", 2),
  p("ToothFairy2、nnU-Net和现有CBCT工作台可以支持术前上下颌分割、方向检查、三维表面和候选区证据展示。术中视频与CBCT之间缺少共同坐标系、光学跟踪和目标配准误差验证。", { indent: 420 }),
  callout("结论分类", "术前三维参考可直接保留；实时术中导航需要跟踪硬件、标志物/表面配准、坐标变换和误差验证，当前没有可靠软件替代。", colors.amber),

  heading("五、国内外资料对项目的具体价值", 1),
  table(
    ["资料方向", "代表来源", "可用于", "禁止声称"],
    [
      ["颌骨自发/四环素荧光", "MRONJ、ORNJ、DCSO研究", "边界机制、对照方案、未来验证设计", "等同于企业ICG通道或原创造影剂"],
      ["骨靶向近红外探针", "磷酸化/双膦酸近红外染料", "候选分子骨亲和端设计", "已经实现骨髓炎选择性"],
      ["细菌靶向探针", "Vanco-800CW、1D9-680、激活型核酸酶探针", "感染靶向端与验证指标", "覆盖所有颌骨骨髓炎病原"],
      ["公开荧光视频", "OnLume Dryad、OFDVDnet", "双通道融合、去噪、时序与4K/MP4工程", "真实颌骨骨髓炎术中数据"],
      ["骨感染/骨髓炎视频", "PMC论文补充视频", "真实手术场景、自监督预训练和演示", "荧光数据或像素级金标准"],
      ["手术视频工具", "SAM 2、CVAT、MONAI Label", "标注加速、传播、复核和回灌", "自动生成医学真值"],
      ["实时AI框架", "TensorRT、Holoscan", "低延迟管线与目标硬件基准", "本项目已达到某一实时帧率"],
    ],
    [1800, 2300, 2600, 2326],
  ),

  heading("六、提交前优先级与时间安排", 1),
  table(
    ["时间窗", "必须完成", "验收证据"],
    [
      ["第1-3天", "冻结造影剂候选结构、机理、光谱适配与验证矩阵；向企业发送设备问题清单", "候选方案图、验证表、企业问题清单"],
      ["第1-5天", "完成视频源级重划分、泄漏检查、重训练和阈值扫描", "split manifest、leakage=0、重评估报告"],
      ["第4-9天", "实现最小双通道模型及四组消融；修复多mask全零问题", "模型代码、checkpoint、adapter、消融表、失败分析"],
      ["第6-11天", "完成真实长MP4、异常编码、4K延迟和资源测试", "P50/P95延迟、显存/RSS、失败恢复记录"],
      ["第8-15天", "按官方三项核心要求形成最终Word/PDF初稿", "章节完整性检查、引用和医学边界检查"],
      ["第16-18天", "冻结比赛版本、全量测试、录屏和证据包", "Git标签、模型清单、校验和、三分钟演示视频"],
      ["第19-20天", "交叉复核与提交包校验", "Word/PDF一致性、报名表、压缩包可解压和哈希"],
    ],
    [1450, 4850, 2726],
  ),
  callout(
    "资源取舍",
    "主投入集中于造影剂答题、无泄漏AI证据、双通道融合、设备适配和最终交付。DICOM、远程协作和新的三维视觉效果保持现状，避免消耗核心交付时间。",
    colors.amber,
  ),

  heading("七、企业、医院与实验团队协作清单", 1),
  heading("7.1 企业显微镜团队", 2),
  bullet("提供一段原始白光/NIR双通道JPEG或MP4样片及文件说明。"),
  bullet("确认通道编码、同步、时间戳、帧率、曝光、增益、倍率、工作距离和滤光片曲线。"),
  bullet("确认第三方候选染料可兼容的激发/发射范围及设备安全边界。"),
  bullet("安排一次实机导入、播放、分析和导出验证。"),
  heading("7.2 医院与医生", 2),
  bullet("复核50-100个关键帧和少量CBCT病例，给出接受、修改或驳回状态。"),
  bullet("确认术中真正关心的输出：暴露骨、灌注信号、边界风险、器械遮挡和不确定性。"),
  bullet("对最终报告措辞、病例展示和医生复核流程进行医学审阅。"),
  heading("7.3 化学与实验团队", 2),
  bullet("评估候选结构的合成可行性、纯化和稳定性。"),
  bullet("测量吸收/发射光谱、量子产率、光稳定性和组织背景。"),
  bullet("设计羟基磷灰石结合、细菌选择性、细胞毒性和离体组织成像实验。"),
  bullet("记录阴性、竞争抑制、无菌炎症和多菌种对照。"),

  heading("八、证据边界与声明模板", 1),
  table(
    ["场景", "建议表述"],
    [
      ["ICG输出", "反映灌注、血管通透性和组织活性差异，用于术中参考和医生复核"],
      ["AI分割", "输出视频信号候选区、边界风险和不确定性提示，不作疾病终判"],
      ["代理数据指标", "用于验证工程可运行性、模型训练链路和相对比较，不代表目标域临床性能"],
      ["公开异域视频", "明确公开来源、荧光属性、医学场景和非目标域边界"],
      ["三维模型", "公开异域解剖分割或高阈值硬组织代理；方向和边界需医生/Slicer复核"],
      ["候选造影剂", "文献支持的设计方案及未来验证路径；未完成实物合成时不报告原创实验性能"],
    ],
    [2200, 6826],
  ),

  heading("九、主要参考资料与链接", 1),
  p("官方本地赛题方案：HT-202604成都科奥达光电技术有限公司-面向颌骨骨髓炎的智能化荧光诊疗比赛方案.pdf（本地忽略文件，不外传）", { size: 20 }),
  linkParagraph("磷酸化近红外骨靶向探针", "https://doi.org/10.1002/anie.201404930"),
  linkParagraph("Vanco-800CW活体细菌成像", "https://doi.org/10.1038/ncomms3584"),
  linkParagraph("Vanco-800CW取出内固定物验证", "https://doi.org/10.1007/s00259-022-05695-y"),
  linkParagraph("葡萄球菌植入感染荧光引导清创", "https://doi.org/10.1038/s41598-020-78362-7"),
  linkParagraph("MRONJ自发荧光与四环素荧光对照", "https://pubmed.ncbi.nlm.nih.gov/27856150/"),
  linkParagraph("下颌慢性硬化性骨髓炎荧光引导切除", "https://pmc.ncbi.nlm.nih.gov/articles/PMC4628814/"),
  linkParagraph("2025年骨自发荧光与病理相关研究", "https://doi.org/10.3390/life15050686"),
  linkParagraph("颌骨放射性坏死荧光引导手术", "https://doi.org/10.1177/03000605221104186"),
  linkParagraph("OnLume荧光视频去噪数据", "https://doi.org/10.5061/dryad.8gtht76x9"),
  linkParagraph("OFDVDnet荧光手术视频数据", "https://doi.org/10.5061/dryad.v6wwpzh3w"),
  linkParagraph("口腔多光谱MODID数据", "https://doi.org/10.5061/dryad.nvx0k6dxw"),
  linkParagraph("SAM 2", "https://github.com/facebookresearch/sam2"),
  linkParagraph("CVAT", "https://github.com/cvat-ai/cvat"),
  linkParagraph("MONAI Label", "https://github.com/Project-MONAI/MONAILabel"),
  linkParagraph("ICG时间强度曲线归一化", "https://pmc.ncbi.nlm.nih.gov/articles/PMC10209496/"),
  linkParagraph("荧光手术定量与报告标准", "https://doi.org/10.1007/s11307-018-1220-0"),
  linkParagraph("医学分割置信度校准", "https://doi.org/10.1109/TMI.2020.3006437"),
  linkParagraph("NVIDIA Holoscan", "https://developer.nvidia.com/holoscan-sdk"),
  linkParagraph("ICG骨灌注系统综述", "https://doi.org/10.3390/life12020154"),
  linkParagraph("ICG感染组织临床先导研究", "https://doi.org/10.1117/1.JBO.29.6.066003"),

  heading("十、归档结论", 1),
  p("项目具备可信的软件工程展示基础。剩余困难中，视频源级重评估、多mask训练修复、双通道模型、ICG动态定量、4K异步AI、最终Word/PDF和版本冻结均可由当前团队推进。造影剂原创验证、真实目标域样本与医生金标准、企业显微镜实机验证需要外部团队参与。", { indent: 420 }),
  p("最终提交应完整回答造影剂、多模态处理和AI判读三项核心要求，并逐级标明文献证据、代理工程证据、医生复核证据和真实目标域证据。当前无法取得的证据应明确列为外部依赖与后续验证计划。", { indent: 420 }),
];

const doc = new Document({
  creator: "Codex",
  title: "颌骨骨髓炎智能化荧光诊疗赛题差距与解决路径归档报告",
  description: "项目困难、赛题差距及国内外可用解决路径归档",
  styles: {
    default: {
      document: { run: { font: "Microsoft YaHei", size: 21, color: colors.text } },
      paragraph: { spacing: { after: 100, line: 315 } },
    },
    paragraphStyles: [
      {
        id: "Title",
        name: "Title",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { font: "Microsoft YaHei", size: 42, bold: true, color: colors.navy },
        paragraph: { alignment: AlignmentType.CENTER, spacing: { after: 240 } },
      },
      {
        id: "Heading1",
        name: "Heading 1",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { font: "Microsoft YaHei", size: 30, bold: true, color: colors.navy },
        paragraph: { spacing: { before: 300, after: 150 }, outlineLevel: 0, keepNext: true },
      },
      {
        id: "Heading2",
        name: "Heading 2",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { font: "Microsoft YaHei", size: 25, bold: true, color: colors.blue },
        paragraph: { spacing: { before: 230, after: 110 }, outlineLevel: 1, keepNext: true },
      },
      {
        id: "Heading3",
        name: "Heading 3",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { font: "Microsoft YaHei", size: 22, bold: true, color: colors.text },
        paragraph: { spacing: { before: 180, after: 90 }, outlineLevel: 2, keepNext: true },
      },
    ],
  },
  numbering: {
    config: [
      {
        reference: "bullet-main",
        levels: [
          {
            level: 0,
            format: LevelFormat.BULLET,
            text: "•",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 620, hanging: 300 } } },
          },
        ],
      },
    ],
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: PAGE_WIDTH, height: PAGE_HEIGHT },
          margin: { top: 1134, right: 1440, bottom: 1134, left: 1440, header: 600, footer: 600 },
        },
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              children: [
                run("颌骨骨髓炎智能化荧光诊疗 | 赛题差距与解决路径归档   ", { size: 17, color: colors.muted }),
                new TextRun({ children: [PageNumber.CURRENT], font: "Microsoft YaHei", size: 17, color: colors.muted }),
              ],
            }),
          ],
        }),
      },
      children,
    },
  ],
});

Packer.toBuffer(doc)
  .then((buffer) => {
    fs.writeFileSync(outputPath, buffer);
    process.stdout.write(`${outputPath}\n`);
  })
  .catch((error) => {
    process.stderr.write(`${error.stack || error}\n`);
    process.exitCode = 1;
  });
