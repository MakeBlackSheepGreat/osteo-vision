using DocumentFormat.OpenXml;
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Wordprocessing;
using WpPageSize = DocumentFormat.OpenXml.Wordprocessing.PageSize;

var outputPath = "C:/Users/876762330/Desktop/projects/osteo-vision/output/项目资料汇总.docx";

using var doc = WordprocessingDocument.Create(outputPath, WordprocessingDocumentType.Document);
var mainPart = doc.AddMainDocumentPart();

var stylesPart = mainPart.AddNewPart<StyleDefinitionsPart>();
stylesPart.Styles = new Styles(
    new DocDefaults(
        new RunPropertiesDefault(new RunPropertiesBaseStyle(
            new RunFonts { Ascii = "Calibri", HighAnsi = "Calibri", EastAsia = "宋体", ComplexScript = "Arial" },
            new FontSize { Val = "24" }, new FontSizeComplexScript { Val = "24" }
        )),
        new ParagraphPropertiesDefault(new ParagraphPropertiesBaseStyle(
            new SpacingBetweenLines { After = "120", Line = "276", LineRule = LineSpacingRuleValues.Auto }
        ))
    ),
    MkStyle("Normal", null, "Normal", true, null, null, null, null),
    MkStyle("Heading1", "Normal", "heading 1", false, "36", "1F3864", "黑体", 0),
    MkStyle("Heading2", "Normal", "heading 2", false, "28", "2E75B6", "黑体", 1),
    MkStyle("Heading3", "Normal", "heading 3", false, "24", "2E75B6", "黑体", 2)
);

var body = new Body();

body.Append(Sp(3000));
body.Append(P("面向颌骨骨髓炎的智能化荧光诊疗方案", true, "1F3864", "52"));
body.Append(new Paragraph());
body.Append(P("项目资料汇总报告", false, "2E75B6", "36"));
body.Append(new Paragraph());
body.Append(P("华西口腔 × 成都科奥达光电技术有限公司", false, "666666", "28"));
body.Append(new Paragraph());
body.Append(P("编制日期：2026年5月30日", false, "999999", "24"));
body.Append(P("论文数量：60 篇（全部附有 PDF）", false, "999999", "24"));
body.Append(P("数据集数量：35 个", false, "999999", "24"));
body.Append(P("可用开源模型：9 个", false, "999999", "24"));
body.Append(PB());

body.Append(H1("目  录"));
var toc = new Paragraph();
toc.Append(new Run(new FieldChar { FieldCharType = FieldCharValues.Begin }));
toc.Append(new Run(new FieldCode(" TOC \\o \"1-3\" \\h \\z \\u ") { Space = SpaceProcessingModeValues.Preserve }));
toc.Append(new Run(new FieldChar { FieldCharType = FieldCharValues.Separate }));
toc.Append(new Run(new Text("（请在 Word 中右键点击此处 → 更新域 → 更新整个目录）") { Space = SpaceProcessingModeValues.Preserve }));
toc.Append(new Run(new FieldChar { FieldCharType = FieldCharValues.End }));
body.Append(toc);
body.Append(PB());

body.Append(H1("一、项目背景"));
body.Append(P("本项目参加华西口腔与成都科奥达光电技术有限公司联合举办的竞赛，为企业自研口腔数字观察仪（可见光+荧光双通道）开发面向颌骨骨髓炎手术的数字化辅助系统。"));
body.Append(P("颌骨骨髓炎是口腔颌面外科的常见疾病，其病灶边界隐匿，坏死骨、炎症组织和潜在活性骨之间缺乏稳定的术中判别标准，仅凭肉眼和临床经验易造成误判。本方案利用企业已有的吲哚菁绿（ICG）造影剂，结合白光/荧光双通道，通过多模态图像融合和AI辅助判读，为术中提供病灶边界风险提示。"));

body.Append(H2("1.1 赛题设置"));
body.Append(Tbl(new[] { "赛点", "内容", "难度" }, new[] {
    new[] { "赛点一", "荧光图像伪彩色增强，辅助医生判读", "★★" },
    new[] { "赛点二", "基于目标检测/分割模型的智能辅助诊断，自动标注病灶区域", "★★★" },
    new[] { "赛点三", "DICOM标准输出 + 远程协作/会诊功能（扩展项）", "★" }
}));

body.Append(H2("1.2 评审权重"));
body.Append(Tbl(new[] { "维度", "权重", "本方案优势" }, new[] {
    new[] { "先进性", "40%", "EGNet边界感知分割 + FRS损失 + 不确定性热图" },
    new[] { "可行性", "30%", "ICG已有CE认证；9个开源模型可直接使用" },
    new[] { "完整度", "20%", "术前ROI→术中融合→边界分割→风险提示→DICOM" },
    new[] { "经济性", "10%", "ICG成本低（企业已有）；开源框架" }
}));

body.Append(H1("二、文献调研成果"));
body.Append(P("共收录60篇论文，全部附有本地PDF文件，覆盖六大类别。"));

body.Append(H2("2.1 论文分类统计"));
body.Append(Tbl(new[] { "类别", "数量", "代表性论文/方法" }, new[] {
    new[] { "ICG荧光", "17", "ICG骨灌注综述、EAES共识、ICG牙科成像、显微镜ICG AI" },
    new[] { "模型方法", "17", "U-Net、nnU-Net、TransUNet、Swin UNETR、MedSAM、EGNet" },
    new[] { "口腔AI", "9", "全景片骨溶解检测、半监督骨髓炎分类、CBCT分割" },
    new[] { "病种影像", "8", "MRI纹理分析、多中心影像组学、多模态比较" },
    new[] { "AI方法", "7", "DL骨髓炎诊断、颌骨形状分析、MRI骨髓分割" },
    new[] { "相关方法", "2", "骨髓感染免疫、荧光引导评估" }
}));

body.Append(H2("2.2 带代码/模型的论文（9篇）"));
body.Append(Tbl(new[] { "编号", "模型", "代码链接", "引用数" }, new[] {
    new[] { "P019", "nnU-Net", "github.com/MIC-DKFZ/nnUNet", "8323" },
    new[] { "P020", "TransUNet", "github.com/Beckschen/TransUNet", "3825" },
    new[] { "P021", "Swin UNETR", "github.com/Project-MONAI/research-contributions", "—" },
    new[] { "P022", "UNETR", "github.com/Project-MONAI/MONAI", "2799" },
    new[] { "P024", "MedSAM", "github.com/bowang-lab/MedSAM", "2315" },
    new[] { "P026", "SAM Adapter", "github.com/KidsWithTokens/Medical-SAM-Adapter", "223" },
    new[] { "P032", "EGNet", "github.com/ITXIAOWU123/EGNet", "—" },
    new[] { "P033", "FRS Loss", "github.com/MohsinFurkh/Fuzzy-Rough-Set-Loss", "—" },
    new[] { "P034", "Retuve", "github.com/radoss-org/retuve", "—" }
}));

body.Append(H2("2.3 ICG荧光核心文献"));
body.Append(Tbl(new[] { "编号", "论文", "关键发现" }, new[] {
    new[] { "P038", "EAES ICG共识(2023)", "51位专家17国：ICG安全有效，剂量0.25-0.5mg/kg" },
    new[] { "P041", "ICG骨灌注综述(2022)", "23项研究452例：ICG对骨髓炎诊断有积极意义" },
    new[] { "P042", "ICG识别坏死感染(2024)", "115例：存活组织均显示荧光，坏死组织均无荧光" },
    new[] { "P044", "ICG牙科成像(2019)", "首次体内验证ICG牙科成像可行性" },
    new[] { "P046", "显微镜ICG AI分割(2022)", "U-Net在ICG显微镜视频上做血管语义分割" },
    new[] { "P062", "ICG骨肿瘤综述(2026)", "中文综述：ICG骨肿瘤术中应用和骨髓炎诊断" }
}));

body.Append(H2("2.4 口腔/颌骨AI核心文献"));
body.Append(Tbl(new[] { "编号", "论文", "关键发现" }, new[] {
    new[] { "P014", "WaveletFusion-ViT(2024)", "AUC 0.96，区分全景片中骨髓炎与良性肿瘤" },
    new[] { "P003", "多中心影像组学(2026)", "120例五中心：影像组学指导手术切除范围" },
    new[] { "P002", "影像组学手术决策(2024)", "扩展ROI比原始ROI效果更好" },
    new[] { "P007", "全景片骨溶解检测(2025)", "CNN+ViT检测边界清晰/不清病灶" }
}));

body.Append(H1("三、数据集调研成果"));
body.Append(P("共收录35个数据集/数据入口，5个直接颌骨/口腔相关，30个可用于迁移学习。"));

body.Append(H2("3.1 直接相关数据集"));
body.Append(Tbl(new[] { "编号", "数据集", "模态", "用途" }, new[] {
    new[] { "D025", "牙源性病灶CBCT+病理", "CBCT", "颌骨病灶分类/分割（最接近骨髓炎）" },
    new[] { "D024", "DentVoxel牙科CBCT", "CBCT", "颌骨3D分割预训练（38结构标注）" },
    new[] { "D026", "下颌管分割数据集", "CBCT", "下颌管结构分割" },
    new[] { "D005", "全景片+下颌分割", "全景片", "下颌骨ROI提取" },
    new[] { "D014", "HuggingFace全景片", "全景片", "大规模预训练（约27900张）" }
}));

body.Append(H2("3.2 迁移学习数据集"));
body.Append(Tbl(new[] { "类别", "数量", "代表数据集" }, new[] {
    new[] { "口腔AI", "8", "DENTEX、Tufts、OdontoAI(4K)、Kaggle龋齿/分割" },
    new[] { "骨/感染", "12", "BTXRD骨肿瘤、MURA肌骨(40K)、DeepLesion" },
    new[] { "通用分割", "5", "MSD、BraTS、ISIC、REFUGE、PROMISE12" },
    new[] { "ICG/荧光", "2", "OFDVDnet荧光视频去噪、CTI荧光数据" },
    new[] { "口腔其他", "3", "NIDCR头颈入口、TCIA头颈、CODE口腔黏膜" }
}));

body.Append(H1("四、推荐技术路线"));
body.Append(P("方案名：基于ICG荧光成像与多模态AI融合的颌骨骨髓炎术中辅助判读系统"));

body.Append(H2("4.1 系统架构"));
body.Append(Tbl(new[] { "层级", "功能", "推荐模型" }, new[] {
    new[] { "术前ROI", "从全景片/CBCT提取颌骨和病灶", "nnU-Net / MedSAM" },
    new[] { "白光/荧光融合", "双通道配准，伪彩叠加图", "多模态融合" },
    new[] { "病灶边界分割", "分割+边界增强+不确定性热图", "EGNet + FRS Loss" },
    new[] { "显微镜端呈现", "叠加热图、边界线、风险标签", "4K叠加 + DICOM输出" }
}));

body.Append(H2("4.2 核心模型性能"));
body.Append(Tbl(new[] { "模型", "任务", "关键指标", "数据集" }, new[] {
    new[] { "EGNet", "边界感知分割", "Dice 0.9164, IoU 0.8543", "ISIC2018" },
    new[] { "FRS Loss", "模糊边界分割", "Recall +2.33%", "多基准消融" },
    new[] { "WaveletFusion-ViT", "骨髓炎分类", "AUC 0.9568", "全景片" },
    new[] { "nnU-Net", "通用医学分割", "自配置top性能", "MSD" },
    new[] { "MedSAM", "交互式分割", "2315引用", "多模态" }
}));

body.Append(H1("五、关键结论与建议"));

body.Append(H2("5.1 可行性判断"));
body.Append(P("1. ICG造影剂成熟安全：EAES 2023共识确认ICG安全有效，骨灌注系统综述（23项研究452例）支持其在骨髓炎诊断中的应用前景。"));
body.Append(P("2. AI技术路线成熟：9个核心模型有开源代码可直接使用，nnU-Net可快速搭建baseline，EGNet+FRS Loss专门针对模糊边界。"));
body.Append(P("3. 公开数据可支撑预训练：D025（牙源性病灶CBCT+病理）和D024（38结构标注CBCT）是最接近的公开数据。"));
body.Append(P("4. 直接任务证据充分：P014证明全景片上区分骨髓炎可行（AUC 0.96），P046实现显微镜ICG视频AI语义分割。"));

body.Append(H2("5.2 核心限制"));
body.Append(P("1. 无专用数据集：没有公开的颌骨骨髓炎术中ICG荧光数据集，需通过迁移学习和半监督学习弥补。"));
body.Append(P("2. ICG特异性不足：ICG反映血流灌注而非骨髓炎病理标志，定位为灌注/活性提示信号。"));

body.Append(H2("5.3 建议"));
body.Append(P("1. 建议参赛，选择基础可行demo路线，不承诺新型特异性造影剂合成。"));
body.Append(P("2. 尽早联系企业或合作医院，争取10-30例脱敏术中白光/ICG图像或视频。"));
body.Append(P("3. 以nnU-Net为baseline，逐步叠加EGNet边界分支和不确定性热图。"));
body.Append(P("4. 组建影像算法、口腔/颌面医学、平台软件三类成员的团队。"));

body.Append(new SectionProperties(
    new WpPageSize { Width = 11906U, Height = 16838U },
    new PageMargin { Top = 1440, Right = 1440U, Bottom = 1440, Left = 1440U, Header = 720U, Footer = 720U, Gutter = 0U }
));

mainPart.Document = new Document(body);
mainPart.Document.Save();
Console.WriteLine("OK: " + outputPath);

static Style MkStyle(string id, string? basedOn, string name, bool def, string? sz, string? color, string? ea, int? ol)
{
    var s = new Style { Type = StyleValues.Paragraph, StyleId = id };
    if (def) s.Default = true;
    s.Append(new StyleName { Val = name });
    if (basedOn != null) s.Append(new BasedOn { Val = basedOn });
    var pp = new StyleParagraphProperties();
    if (ol.HasValue) { pp.Append(new OutlineLevel { Val = ol.Value }); pp.Append(new KeepNext()); pp.Append(new KeepLines()); }
    if (ol == 0) pp.Append(new SpacingBetweenLines { Before = "360", After = "200" });
    else if (ol == 1) pp.Append(new SpacingBetweenLines { Before = "240", After = "120" });
    else if (ol == 2) pp.Append(new SpacingBetweenLines { Before = "200", After = "80" });
    s.Append(pp);
    var rp = new StyleRunProperties();
    if (ea != null) rp.Append(new RunFonts { Ascii = "Calibri", HighAnsi = "Calibri", EastAsia = ea });
    if (ol.HasValue) rp.Append(new Bold());
    if (sz != null) { rp.Append(new FontSize { Val = sz }); rp.Append(new FontSizeComplexScript { Val = sz }); }
    if (color != null) rp.Append(new Color { Val = color });
    s.Append(rp);
    return s;
}

static Paragraph P(string t, bool b = false, string? c = null, string? sz = null, string? sid = null)
{
    var p = new Paragraph();
    if (sid != null) p.Append(new ParagraphProperties(new ParagraphStyleId { Val = sid }));
    var rp = new RunProperties();
    if (b) rp.Append(new Bold());
    if (c != null) rp.Append(new Color { Val = c });
    if (sz != null) { rp.Append(new FontSize { Val = sz }); rp.Append(new FontSizeComplexScript { Val = sz }); }
    p.Append(new Run(rp, new Text(t) { Space = SpaceProcessingModeValues.Preserve }));
    return p;
}

static Paragraph H1(string t) => P(t, sid: "Heading1");
static Paragraph H2(string t) => P(t, sid: "Heading2");
static Paragraph Sp(int d) => new Paragraph(new ParagraphProperties(new SpacingBetweenLines { Before = d.ToString() }));
static Paragraph PB() => new Paragraph(new Run(new Break { Type = BreakValues.Page }));

static Table Tbl(string[] h, string[][] rows)
{
    var t = new Table();
    t.Append(new TableProperties(
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
    ));
    var g = new TableGrid();
    foreach (var _ in h) g.Append(new GridColumn());
    t.Append(g);
    var hr = new TableRow();
    foreach (var x in h)
        hr.Append(new TableCell(
            new TableCellProperties(new Shading { Val = ShadingPatternValues.Clear, Color = "auto", Fill = "2E75B6" }),
            new Paragraph(new ParagraphProperties(new Justification { Val = JustificationValues.Center }),
                new Run(new RunProperties(new Bold(), new Color { Val = "FFFFFF" }, new FontSize { Val = "20" }), new Text(x) { Space = SpaceProcessingModeValues.Preserve }))));
    t.Append(hr);
    for (int i = 0; i < rows.Length; i++)
    {
        var r = new TableRow();
        string f = i % 2 == 0 ? "F2F7FC" : "FFFFFF";
        foreach (var c in rows[i])
            r.Append(new TableCell(
                new TableCellProperties(new Shading { Val = ShadingPatternValues.Clear, Color = "auto", Fill = f }),
                new Paragraph(new Run(new RunProperties(new FontSize { Val = "20" }), new Text(c ?? "") { Space = SpaceProcessingModeValues.Preserve }))));
        t.Append(r);
    }
    return t;
}
