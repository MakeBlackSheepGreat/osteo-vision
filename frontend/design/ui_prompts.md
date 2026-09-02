# Osteo Vision 前端 UI 生成提示词

> 用途：发给 GPT-image-1 / DALL·E / Midjourney 等图片生成模型，产出 UI 参考图。
> 每个 prompt 对应一个独立页面，可单独使用。

---

## 通用设计语言（所有页面共享）

在描述各页面前，先把这套设计基线告诉模型，避免每次重复：

```
Design language for all screens below:
- Language: Simplified Chinese UI text.
- Color palette: Medical blue theme. Primary deep blue #1a5276, medium blue #2980b9,
  accent blue #1e6fa6. Background light blue-gray #f3f6fa. Card background pure white #ffffff
  with subtle blue-gray border #c8d4e0. Secondary text #5a6a7a. Body text #162020.
  Warning amber #c1812a on #fffaf0. Error red #a23b25. Success blue #1e6fa6 on #e8f0fe.
- Typography: Chinese sans-serif (Noto Sans SC / PingFang SC feel). Clear hierarchy:
  large bold titles, medium section headings, small gray labels.
- Components: Rounded corners (8px), white cards with thin blue-gray borders, thin
  horizontal dividers, compact spacing. No heavy shadows. Clean, clinical, trustworthy.
- Overall feel: Hospital-grade medical imaging software. Professional, high information
  density, restrained color use, not playful. Think PACS viewer meets modern SaaS dashboard.
```

---

## Prompt 1 — 病例工作台（主页，最核心）

```
Generate a high-fidelity UI screenshot of a Chinese-language medical imaging analysis
platform for osteomyelitis intraoperative decision support. The page is called
"病例工作台" (Case Workspace).

[Design language: insert the shared block above]

=== PAGE LAYOUT (desktop, 1440×900 viewport, top to bottom) ===

TOP BAR:
- Left: small gray label "研发验证版平台" above a large bold title "颌骨骨髓炎术中辅助决策平台"
- Right: the clinical workflow navigation in this order — "数据准入", "病例档案", "病例工作台"
  (active), "三维导航", "医生复核", "报告导出"; secondary research support follows afterward.

WARNING BANNER:
- A horizontal amber-bordered notice bar with a left thick amber accent stripe.
- Bold label "医生复核边界" followed by descriptive gray text about ICG fluorescence
  being a reference only.

STATUS STRIP:
- 4 white metric tiles in a row, each with a small gray top label and a large bold value:
  "病例状态: 已分析"  |  "输入通道: 2 个"  |  "候选区域: 3"  |  "证据文件: 5 个"

MAIN 3-COLUMN LAYOUT:

LEFT SIDEBAR (~300px, white card, vertical stack of collapsible sections):
1. Section "病例 / 建立与加载": text input "病例标题" with placeholder,
   primary blue button "新建病例", text input "病例 ID", secondary button "加载病例".
2. Section "官方输入 / JPEG 与 MP4": file pickers for JPEG images and MP4 videos,
   plus a paired white-light/fluorescence upload control for static fusion.
3. Section "融合参数 / 伪彩与阈值": two horizontal sliders (融合透明度 0.45,
   荧光阈值 0.60), a dropdown "伪彩方案", primary blue button "运行双通道分析".
4. Small section: secondary button "导出证据包".

CENTER PANEL (main content area):
- Header row: left side has gray label "分析视图" + heading "双通道融合与风险提示";
  right side has a rounded status pill "已完成" (blue text on light blue bg).
- Image grid: 3 side-by-side image slots, each a rounded card with dashed blue-gray border
  and subtle blue gradient background. Each slot has a header "融合图 / 热图 / 归一化图".
  Inside each slot, show a realistic medical image: the left one shows a jaw intraoral photo
  with green-tinted fluorescence overlay, the middle shows a heatmap from blue→red, the right
  shows a normalized grayscale fluorescence image. Add small annotation text in each slot.
- Below images, a 2-column result section:
  LEFT column "候选区域 / 医生复核队列": 2–3 list items, each a white card with
  "荧光高信号候选区" label + yellow "待复核" pill + score/confidence values.
  RIGHT column "量化 / 荧光统计": a definition list grid with metrics like
  平均荧光强度 0.3421, 最大荧光强度 0.8912, P95 荧光强度 0.6734, 阳性面积占比 0.1823.

RIGHT SIDEBAR (~300px, white card, vertical stack):
1. "当前病例" — heading "颌骨骨髓炎术中演示病例", dl with 病例 ID, 复核版本, 最近运行.
2. "输入清单 / 通道记录" — list items showing "白光" and "ICG 荧光" with file paths.
3. "质控 / 运行提示" — "暂无阻断性提示" in gray.
4. "证据 / 输出文件" — list of artifact types (融合图, 热图, JSON 报告, etc.).

BOTTOM: collapsed debug panel "调试数据".

Render as a real screenshot, photorealistic UI, sharp text, no placeholder gray boxes —
fill image slots with plausible medical fluorescence imagery. Chinese text throughout.
```

---

## Prompt 2 — 医生复核页

```
Generate a high-fidelity UI screenshot of a Chinese-language medical image review page
for an osteomyelitis diagnosis support platform. The page is called "医生复核".

[Design language: insert the shared block above]

=== PAGE LAYOUT (desktop, 1440×900 viewport) ===

TOP LEFT:
- Gray small label "医生复核" above large title "候选区域与 ROI 判读"
TOP RIGHT:
- White button with blue text "返回病例工作台"

MAIN 2-COLUMN LAYOUT (max-width 1300px, centered):

LEFT COLUMN (wider, ~60%):
- White card "ROI 复核 / 术中手动 ROI"
- Inside: a large canvas area with subtle grid lines (34px spacing, light blue-gray),
  and a rectangular amber-bordered ROI selection box drawn on it.
- The canvas background has a faint diagonal gradient from blue tint to white.
- Label centered: "影像与标注画布"

RIGHT COLUMN (stacked cards):
CARD 1 — "AI 辅助提示 / 候选区域":
- A list of 2–3 candidate region cards, each containing:
  - Title row: bold "荧光高信号候选区" left, yellow rounded pill "待复核" right.
  - Two-column metrics: 分数 0.7823 | 置信参考 0.6512
  - Gray description paragraph about the finding.

CARD 2 — "医生操作 / 复核状态":
- Three vertically stacked buttons:
  - Primary blue filled button: "接受候选区"
  - White outlined button: "标记已修改"
  - White outlined button with red text: "驳回提示"

CARD 3 — "荧光分析 / 量化指标":
- 2-column grid of metric name/value pairs:
  平均荧光强度 0.3421, 最大荧光强度 0.8912, P95 荧光强度 0.6734,
  阳性面积像素 4821, 阳性面积占比 0.1823, 阈值 0.6000

The overall composition emphasizes the large ROI canvas on the left and dense review
controls on the right. Clean, clinical, no decorative elements. Chinese text throughout.
```

---

## Prompt 3 — 报告导出页

```
Generate a high-fidelity UI screenshot of a Chinese-language report preview page for a
medical imaging platform. The page is called "报告导出".

[Design language: insert the shared block above]

=== PAGE LAYOUT (desktop, 1440×900 viewport) ===

TOP LEFT:
- Gray small label "结果输出" above large title "病例证据包预览"
TOP RIGHT:
- White button with blue text "返回病例工作台"

MAIN 2-COLUMN LAYOUT (max-width 1180px, centered):

LEFT COLUMN (wider):
- White card "当前导出"
- Definition list with 3 rows:
  - 病例 ID → a UUID string like "case-20250618-a3f2"
  - 证据包路径 → a Windows file path "D:\artifacts\export\case-20250618-a3f2"
  - 证据文件数量 → "5"

RIGHT COLUMN (narrower):
- White card "输出边界"
- Paragraph of descriptive text: "导出内容面向科研演示、研发汇报和医生复核记录。
  报告中的候选区域、荧光统计和图像证据均需结合术中视野与医生判断。"

Below the two cards, optionally show a preview area with thumbnails of exported artifacts:
small image cards labeled "融合图", "热图", "归一化荧光", "JSON 报告", "Markdown 报告",
each with a small icon or preview thumbnail.

Minimalist page, lots of white space, emphasis on clarity and trustworthiness.
Chinese text throughout.
```

---

## Prompt 4 — 登录/启动页（可选扩展）

> 当前代码中没有登录页，但作为完整产品可以考虑加上。以下为参考。

```
Generate a clean, centered login/splash screen for a Chinese-language medical imaging
platform called "颌骨骨髓炎术中辅助决策平台".

[Design language: insert the shared block above]

Centered on a light blue-gray #f3f6fa background:
- A large white card (max-width 420px) with subtle blue-gray border and generous padding.
- Top: platform logo placeholder (a simple blue medical cross or microscope icon).
- Title: "颌骨骨髓炎术中辅助决策平台" in large bold dark text.
- Subtitle: "科研与研发平台验证" in small gray uppercase-style label.
- Two text inputs: "工号 / 用户名", "密码" (with placeholder dots).
- A primary blue button spanning full width: "进入工作台".
- Below button: small gray text "仅供科研演示，不用于临床诊断".
- Bottom of card: amber notice stripe "医生复核边界" with explanation text.

Background: subtle diagonal gradient from light blue to white. No decorative illustrations.
Clean, medical, trustworthy. Chinese text throughout.
```

---

## 使用建议

1. **优先级**：Prompt 1（病例工作台）是信息密度最高、最能体现产品定位的页面，建议先生成。
2. **迭代策略**：先用宽泛描述生成整体布局，再用局部放大 prompt 细化单个组件。
3. **文字渲染**：如果模型中文渲染不佳，可以让模型生成布局后再用 Figma 手动替换文字。
4. **风格锚点**：可以附上参考图（如 OHIF Viewer、3D Slicer、Nvidia Clara 的截图）并说
   "match this level of professional medical imaging software polish"。
5. **工作站分辨率**：以桌面端 1440×900 及更宽的临床工作站视口为验收基线。
