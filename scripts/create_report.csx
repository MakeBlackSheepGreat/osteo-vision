#r "nuget: DocumentFormat.OpenXml, 3.2.0"

using DocumentFormat.OpenXml;
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Wordprocessing;

var outputPath = "C:/Users/876762330/Desktop/projects/osteo-vision/output/项目资料汇总.docx";

using var doc = WordprocessingDocument.Create(outputPath, WordprocessingDocumentType.Document);
var mainPart = doc.AddMainDocumentPart();

// Add styles part
var stylesPart = mainPart.AddNewPart<StyleDefinitionsPart>();
var styles = new Styles(
    new DocDefaults(
        new RunPropertiesDefault(
            new RunPropertiesBaseStyle(
                new RunFonts { Ascii = "Calibri", HighAnsi = "Calibri", EastAsia = "宋体", ComplexScript = "Arial" },
                new FontSize { Val = "24" },
                new FontSizeComplexScript { Val = "24" }
            )
        ),
        new ParagraphPropertiesDefault(
            new ParagraphPropertiesBaseStyle(
                new SpacingBetweenLines { After = "120", Line = "276", LineRule = LineSpacingRuleValues.Auto }
            )
        )
    ),
    // Normal style
    new Style(
        new StyleName { Val = "Normal" },
        new StyleParagraphProperties(
            new SpacingBetweenLines { After = "120", Line = "276", LineRule = LineSpacingRuleValues.Auto }
        ),
        new StyleRunProperties(
            new RunFonts { Ascii = "Calibri", HighAnsi = "Calibri", EastAsia = "宋体" },
            new FontSize { Val = "24" }
        )
    ) { Type = StyleValues.Paragraph, StyleId = "Normal", Default = true },
    // Heading1
    new Style(
        new StyleName { Val = "heading 1" },
        new BasedOn { Val = "Normal" },
        new NextParagraphStyle { Val = "Normal" },
        new StyleParagraphProperties(
            new SpacingBetweenLines { Before = "360", After = "200" },
            new OutlineLevel { Val = 0 },
            new KeepNext(),
            new KeepLines()
        ),
        new StyleRunProperties(
            new RunFonts { Ascii = "Calibri", HighAnsi = "Calibri", EastAsia = "黑体" },
            new Bold(),
            new FontSize { Val = "36" },
            new FontSizeComplexScript { Val = "36" },
            new Color { Val = "1F3864" }
        )
    ) { Type = StyleValues.Paragraph, StyleId = "Heading1" },
    // Heading2
    new Style(
        new StyleName { Val = "heading 2" },
        new BasedOn { Val = "Normal" },
        new NextParagraphStyle { Val = "Normal" },
        new StyleParagraphProperties(
            new SpacingBetweenLines { Before = "240", After = "120" },
            new OutlineLevel { Val = 1 },
            new KeepNext(),
            new KeepLines()
        ),
        new StyleRunProperties(
            new RunFonts { Ascii = "Calibri", HighAnsi = "Calibri", EastAsia = "黑体" },
            new Bold(),
            new FontSize { Val = "28" },
            new FontSizeComplexScript { Val = "28" },
            new Color { Val = "2E75B6" }
        )
    ) { Type = StyleValues.Paragraph, StyleId = "Heading2" },
    // Heading3
    new Style(
        new StyleName { Val = "heading 3" },
        new BasedOn { Val = "Normal" },
        new NextParagraphStyle { Val = "Normal" },
        new StyleParagraphProperties(
            new SpacingBetweenLines { Before = "200", After = "80" },
            new OutlineLevel { Val = 2 },
            new KeepNext()
        ),
        new StyleRunProperties(
            new RunFonts { Ascii = "Calibri", HighAnsi = "Calibri", EastAsia = "黑体" },
            new Bold(),
            new FontSize { Val = "24" },
            new FontSizeComplexScript { Val = "24" },
            new Color { Val = "2E75B6" }
        )
    ) { Type = StyleValues.Paragraph, StyleId = "Heading3" },
    // TOC heading style
    new Style(
        new StyleName { Val = "TOC Heading" },
        new BasedOn { Val = "Heading1" },
        new StyleParagraphProperties(
            new OutlineLevel { Val = 9 }
        )
    ) { Type = StyleValues.Paragraph, StyleId = "TOCHeading" }
);
stylesPart.Styles = styles;

// Build body
var body = new Body();

// Helper functions
Paragraph MakePara(string text, string styleId = null, bool bold = false, string color = null, string fontSize = null)
{
    var rp = new RunProperties();
    if (bold) rp.Append(new Bold());
    if (color != null) rp.Append(new Color { Val = color });
    if (fontSize != null) { rp.Append(new FontSize { Val = fontSize }); rp.Append(new FontSizeComplexScript { Val = fontSize }); }
    var run = new Run(rp, new Text(text) { Space = SpaceProcessingModeValues.Preserve });
    var para = new Paragraph();
    if (styleId != null) para.Append(new ParagraphProperties(new ParagraphStyleId { Val = styleId }));
    para.Append(run);
    return para;
}

Paragraph MakeH1(string text) => MakePara(text, "Heading1");
Paragraph MakeH2(string text) => MakePara(text, "Heading2");
Paragraph MakeH3(string text) => MakePara(text, "Heading3");

Table MakeTable(string[] headers, string[][] rows)
{
    var tbl = new Table();
    var tblPr = new TableProperties(
        new TableBorders(
            new TopBorder { Val = BorderValues.Single, Size = 4, Color = "2E75B6" },
            new BottomBorder { Val = BorderValues.Single, Size = 4, Color = "2E75B6" },
            new LeftBorder { Val = BorderValues.Single, Size = 4, Color = "CCCCCC" },
            new RightBorder { Val = BorderValues.Single, Size = 4, Color = "CCCCCC" },
            new InsideHorizontalBorder { Val = BorderValues.Single, Size = 2, Color = "CCCCCC" },
            new InsideVerticalBorder { Val = BorderValues.Single, Size = 2, Color = "CCCCCC" }
        ),
        new TableWidth { Width = "5000", Type = TableWidthUnitValues.Pct },
        new TableCellMarginDefault(
            new TopMargin { Width = "40", Type = TableWidthUnitValues.Dxa },
            new TableCellLeftMargin { Width = 80, Type = TableWidthValues.Dxa },
            new BottomMargin { Width = "40", Type = TableWidthUnitValues.Dxa },
            new TableCellRightMargin { Width = 80, Type = TableWidthValues.Dxa }
        )
    );
    tbl.Append(tblPr);

    // Grid
    var grid = new TableGrid();
    foreach (var _ in headers) grid.Append(new GridColumn());
    tbl.Append(grid);

    // Header row
    var hRow = new TableRow();
    foreach (var h in headers)
    {
        var tc = new TableCell(
            new TableCellProperties(new Shading { Val = ShadingPatternValues.Clear, Color = "auto", Fill = "2E75B6" }),
            new Paragraph(
                new ParagraphProperties(new Justification { Val = JustificationValues.Center }),
                new Run(
                    new RunProperties(new Bold(), new Color { Val = "FFFFFF" }, new FontSize { Val = "20" }),
                    new Text(h) { Space = SpaceProcessingModeValues.Preserve }
                )
            )
        );
        hRow.Append(tc);
    }
    tbl.Append(hRow);

    // Data rows
    for (int i = 0; i < rows.Length; i++)
    {
        var row = new TableRow();
        string fill = i % 2 == 0 ? "F2F7FC" : "FFFFFF";
        foreach (var cell in rows[i])
        {
            var tc = new TableCell(
                new TableCellProperties(new Shading { Val = ShadingPatternValues.Clear, Color = "auto", Fill = fill }),
                new Paragraph(
                    new Run(
                        new RunProperties(new FontSize { Val = "20" }),
                        new Text(cell ?? "") { Space = SpaceProcessingModeValues.Preserve }
                    )
                )
            );
            row.Append(tc);
        }
        tbl.Append(row);
    }
    return tbl;
}

// ─── COVER PAGE ───
body.Append(new Paragraph(new ParagraphProperties(new SpacingBetweenLines { Before = "3000" })));
body.Append(MakePara("面向颌骨骨髓炎的智能化荧光诊疗方案", null, true, "1F3864", "52"));
body.Append(new Paragraph());
body.Append(MakePara("项目资料汇总报告", null, false, "2E75B6", "36"));
body.Append(new Paragraph());
body.Append(MakePara("华西口腔 × 成都科奥达光电技术有限公司", null, false, "666666", "28"));
body.Append(new Paragraph());
body.Append(new Paragraph());
body.Append(MakePara("编制日期：2026年5月30日", null, false, "999999", "24"));
body.Append(MakePara("论文数量：60 篇（全部附有 PDF）", null, false, "999999", "24"));
body.Append(MakePara("数据集数量：35 个", null, false, "999999", "24"));
body.Append(MakePara("可用开源模型：9 个", null, false, "999999", "24"));

// Page break after cover
body.Append(new Paragraph(new Run(new Break { Type = BreakValues.Page })));

// ─── TOC ───
body.Append(MakePara("目  录", "TOCHeading"));
var tocPara = new Paragraph();
tocPara.Append(new Run(new FieldChar { FieldCharType = FieldCharValues.Begin }));
tocPara.Append(new Run(new FieldCode(" TOC \\o \"1-3\" \\h \\z \\u ") { Space = SpaceProcessingModeValues.Preserve }));
tocPara.Append(new Run(new FieldChar { FieldCharType = FieldCharValues.Separate }));
tocPara.Append(new Run(new Text("（请在 Word 中右键更新目录）") { Space = SpaceProcessingModeValues.Preserve }));
tocPara.Append(new Run(new FieldChar { FieldCharType = FieldCharValues.End }));
body.Append(tocPara);
body.Append(new Paragraph(new Run(new Break { Type = BreakValues.Page })));

// ─── SECTION 1: PROJECT BACKGROUND ───
body.Append(MakeH1("一、项目背景"));
body.Append(MakePara("本项目参加华西口腔与成都科奥达光电技术有限公司联合举办的竞赛，为企业自研口腔数字观察仪（可见光+荧光双通道）开发面向颌骨骨髓炎手术的数字化辅助系统。"));
body.Append(MakePara("颌骨骨髓炎是口腔颌面外科的常见疾病，其病灶边界隐匿，坏死骨、炎症组织和潜在活性骨之间缺乏稳定的术中判别标准，仅凭肉眼和临床经验易造成误判，导致疾病复发或过度切除正常组织。"));
body.Append(MakePara("本方案的核心思路是：利用企业已有的吲哚菁绿（ICG）造影剂，结合口腔数字观察仪的白光/荧光双通道，通过多模态图像融合和AI辅助判读，为术中提供病灶边界风险提示。"));

body.Append(MakeH2("1.1 赛题设置"));
body.Append(MakeTable(
    new[] { "赛点", "内容", "难度" },
    new[] {
        new[] { "赛点一", "荧光图像伪彩色增强，辅助医生判读", "★★" },
        new[] { "赛点二", "基于目标检测/分割模型的智能辅助诊断，自动标注病灶区域", "★★★" },
        new[] { "赛点三", "DICOM标准输出 + 远程协作/会诊功能（扩展项）", "★" }
    }
));
body.Append(new Paragraph());

body.Append(MakeH2("1.2 评审权重"));
body.Append(MakeTable(
    new[] { "评审维度", "权重", "本方案优势" },
    new[] {
        new[] { "先进性", "40%", "EGNet边界感知分割 + FRS模糊粗糙集损失 + 不确定性热图 + 半监督学习" },
        new[] { "可行性", "30%", "ICG已有CE认证和大量临床证据；9个开源模型可直接使用" },
        new[] { "完整度", "20%", "覆盖术前ROI→术中融合→边界分割→风险提示→DICOM输出全链条" },
        new[] { "经济性", "10%", "ICG造影剂成本低（企业已有产品）；模型使用开源框架" }
    }
));
body.Append(new Paragraph());

// ─── SECTION 2: LITERATURE SURVEY ───
body.Append(MakeH1("二、文献调研成果"));
body.Append(MakePara("共收录60篇论文，全部附有本地PDF文件，覆盖病种影像、口腔AI、模型方法、ICG荧光、AI方法、相关方法六大类别。"));

body.Append(MakeH2("2.1 论文分类统计"));
body.Append(MakeTable(
    new[] { "类别", "数量", "代表性论文/方法" },
    new[] {
        new[] { "ICG荧光", "17", "ICG骨灌注评估系统综述、EAES ICG共识、ICG牙科成像、显微镜ICG AI分割" },
        new[] { "模型方法", "17", "U-Net、nnU-Net、TransUNet、Swin UNETR、MedSAM、EGNet、FRS Loss" },
        new[] { "口腔AI", "9", "全景片骨溶解检测、颌骨囊肿/肿瘤检测、半监督骨髓炎分类、CBCT分割" },
        new[] { "病种影像", "8", "MRI纹理分析骨髓炎、多中心影像组学手术决策、多模态影像比较" },
        new[] { "AI方法", "7", "DL骨髓炎诊断、颌骨形状分析、MRI骨髓信号分割" },
        new[] { "相关方法", "2", "骨髓感染免疫反应、荧光引导骨/软组织评估" }
    }
));
body.Append(new Paragraph());

body.Append(MakeH2("2.2 带代码/模型的论文（9篇）"));
body.Append(MakeTable(
    new[] { "编号", "模型", "代码链接", "引用数" },
    new[] {
        new[] { "P019", "nnU-Net", "github.com/MIC-DKFZ/nnUNet", "8323" },
        new[] { "P020", "TransUNet", "github.com/Beckschen/TransUNet", "3825" },
        new[] { "P021", "Swin UNETR", "github.com/Project-MONAI/research-contributions", "—" },
        new[] { "P022", "UNETR", "github.com/Project-MONAI/MONAI", "2799" },
        new[] { "P024", "MedSAM", "github.com/bowang-lab/MedSAM", "2315" },
        new[] { "P026", "Medical SAM Adapter", "github.com/KidsWithTokens/Medical-SAM-Adapter", "223" },
        new[] { "P032", "EGNet", "github.com/ITXIAOWU123/EGNet", "—" },
        new[] { "P033", "FRS Loss", "github.com/MohsinFurkh/Fuzzy-Rough-Set-Loss", "—" },
        new[] { "P034", "Retuve", "github.com/radoss-org/retuve", "—" }
    }
));
body.Append(new Paragraph());

body.Append(MakeH2("2.3 ICG荧光核心文献"));
body.Append(MakeTable(
    new[] { "编号", "论文", "关键发现" },
    new[] {
        new[] { "P038", "EAES ICG荧光手术共识（2023）", "51位专家17国共识：ICG安全有效，剂量0.25-0.5mg/kg，给药后10分钟开始成像" },
        new[] { "P041", "ICG骨灌注评估系统综述（2022）", "23项研究452例患者：ICG灌注评估对骨髓炎诊断和骨活力评估有积极意义" },
        new[] { "P042", "ICG识别坏死性软组织感染（2024）", "115例患者：所有存活组织显示荧光，所有坏死组织无荧光" },
        new[] { "P044", "ICG辅助近红外牙科成像（2019）", "首次体内验证ICG牙科成像可行性，优化了成像条件" },
        new[] { "P046", "显微镜ICG视频AI语义分割（2022）", "最接近本赛题的工程形态：U-Net在ICG显微镜视频上做脑动脉语义分割" },
        new[] { "P062", "ICG在骨与软组织肿瘤中的应用综述（2026）", "中文综述，涵盖ICG骨肿瘤术中应用、骨髓炎辅助诊断、NIR-II未来方向" }
    }
));
body.Append(new Paragraph());

body.Append(MakeH2("2.4 口腔/颌骨AI核心文献"));
body.Append(MakeTable(
    new[] { "编号", "论文", "关键发现" },
    new[] {
        new[] { "P014", "WaveletFusion-ViT半监督骨髓炎分类（2024）", "AUC 0.9568，直接区分全景片中的慢性化脓性骨髓炎与良性肿瘤" },
        new[] { "P003", "多中心habitat imaging骨髓炎手术决策（2026）", "120例五中心：影像组学指导手术切除范围，从诊断推进到手术规划" },
        new[] { "P002", "慢性骨髓炎影像组学手术决策（2024）", "扩展ROI比原始ROI效果更好，病灶周边区域有决策价值" },
        new[] { "P007", "全景片骨溶解病灶检测（2025）", "CNN+ViT检测边界清晰/不清病灶，直接对应本赛题" }
    }
));
body.Append(new Paragraph());

// ─── SECTION 3: DATASETS ───
body.Append(MakeH1("三、数据集调研成果"));
body.Append(MakePara("共收录35个数据集/数据入口，其中5个直接颌骨/口腔相关，30个可用于迁移学习。"));

body.Append(MakeH2("3.1 直接相关数据集（颌骨/口腔专用）"));
body.Append(MakeTable(
    new[] { "编号", "数据集", "模态", "规模", "用途" },
    new[] {
        new[] { "D025", "牙源性病灶CBCT + 病理标签", "CBCT", "含组织病理标注", "颌骨病灶分类/分割（最接近骨髓炎任务）" },
        new[] { "D024", "DentVoxel牙科CBCT", "CBCT", "38种解剖结构标注", "颌骨3D分割预训练" },
        new[] { "D026", "下颌管分割数据集", "CBCT", "下颌管分割标注", "下颌管结构分割" },
        new[] { "D005", "全景片+下颌分割标注", "全景片", "含下颌分割标注", "下颌骨ROI提取" },
        new[] { "D014", "HuggingFace全景片", "全景片", "约27900张", "大规模全景片预训练" }
    }
));
body.Append(new Paragraph());

body.Append(MakeH2("3.2 迁移学习数据集（按类别）"));
body.Append(MakeTable(
    new[] { "类别", "数量", "代表数据集" },
    new[] {
        new[] { "口腔AI", "8", "DENTEX、Tufts、儿童全景片、OdontoAI(4K)、Kaggle龋齿/分割" },
        new[] { "骨/感染", "12", "BTXRD骨肿瘤、MURA肌骨(40K)、DeepLesion、骨折检测、骨髓炎临床" },
        new[] { "通用分割", "5", "Medical Segmentation Decathlon、BraTS、ISIC皮肤病变、REFUGE、PROMISE12" },
        new[] { "ICG/荧光", "2", "OFDVDnet荧光手术视频去噪、CTI荧光数据" },
        new[] { "口腔其他", "3", "NIDCR头颈入口、TCIA头颈集合、CODE口腔黏膜" }
    }
));
body.Append(new Paragraph());

// ─── SECTION 4: TECHNICAL ROUTE ───
body.Append(MakeH1("四、推荐技术路线"));
body.Append(MakePara("方案名：基于ICG荧光成像与多模态AI融合的颌骨骨髓炎术中辅助判读系统"));

body.Append(MakeH2("4.1 系统架构"));
body.Append(MakeTable(
    new[] { "层级", "功能", "推荐模型/方法" },
    new[] {
        new[] { "第一层：术前ROI", "从全景片/CBCT提取颌骨区域和病灶候选区", "nnU-Net / MedSAM" },
        new[] { "第二层：白光/荧光融合", "显微镜双通道配准，生成伪彩叠加图", "多模态融合（像素级/特征级）" },
        new[] { "第三层：病灶边界分割", "病灶区域分割 + 边界增强 + 不确定性热图", "EGNet + FRS Loss + Stochastic SegNet" },
        new[] { "第四层：显微镜端呈现", "叠加透明热图、边界线、风险标签", "4K图像叠加 + DICOM输出" }
    }
));
body.Append(new Paragraph());

body.Append(MakeH2("4.2 核心模型性能参考"));
body.Append(MakeTable(
    new[] { "模型", "任务", "关键指标", "数据集" },
    new[] {
        new[] { "EGNet", "边界感知分割", "Dice 0.9164, IoU 0.8543", "ISIC2018（皮肤病变）" },
        new[] { "FRS Loss", "模糊边界分割", "Recall +2.33%", "多基准消融实验" },
        new[] { "WaveletFusion-ViT", "骨髓炎分类", "AUC 0.9568", "全景片（约140张）" },
        new[] { "nnU-Net", "通用医学分割", "自配置top性能", "Medical Segmentation Decathlon" },
        new[] { "MedSAM", "交互式分割", "2315引用", "多模态医学图像" }
    }
));
body.Append(new Paragraph());

// ─── SECTION 5: CONCLUSIONS ───
body.Append(MakeH1("五、关键结论与建议"));

body.Append(MakeH2("5.1 可行性判断"));
body.Append(MakePara("1. ICG造影剂成熟安全：EAES 2023共识确认ICG安全有效，骨灌注评估系统综述（23项研究452例）支持其在骨髓炎诊断中的应用前景。"));
body.Append(MakePara("2. AI技术路线成熟：9个核心模型有开源代码可直接使用，nnU-Net可快速搭建可靠baseline，EGNet+FRS Loss专门针对模糊边界优化。"));
body.Append(MakePara("3. 公开数据可支撑预训练：D025（牙源性病灶CBCT+病理）和D024（牙科CBCT 38结构标注）是最接近的公开数据。"));
body.Append(MakePara("4. 直接任务证据充分：P014已证明全景片上区分骨髓炎与其他颌骨病灶可行（AUC 0.96），P046已实现显微镜ICG视频AI语义分割。"));

body.Append(MakeH2("5.2 核心限制"));
body.Append(MakePara("1. 无专用数据集：目前没有公开的颌骨骨髓炎术中ICG荧光数据集，需通过迁移学习和半监督学习弥补。"));
body.Append(MakePara("2. ICG特异性不足：ICG反映血流灌注差异而非骨髓炎病理标志，本方案将其定位为灌注/活性提示信号，而非确诊工具。"));

body.Append(MakeH2("5.3 建议"));
body.Append(MakePara("1. 建议参赛，选择基础可行demo路线，不承诺新型特异性造影剂合成。"));
body.Append(MakePara("2. 尽早联系企业或合作医院，争取10-30例脱敏术中白光/ICG图像或视频。"));
body.Append(MakePara("3. 以nnU-Net为baseline，逐步叠加EGNet边界分支和不确定性热图。"));
body.Append(MakePara("4. 组建影像算法、口腔/颌面医学、软件原型三类成员的团队。"));

// ─── SECTION PROPERTIES (must be last child of body) ───
body.Append(new SectionProperties(
    new PageSize { Width = 11906U, Height = 16838U },
    new PageMargin { Top = 1440, Right = 1440U, Bottom = 1440, Left = 1440U, Header = 720U, Footer = 720U, Gutter = 0U }
));

mainPart.Document = new Document(body);
mainPart.Document.Save();

Console.WriteLine("DOCX created: " + outputPath);
