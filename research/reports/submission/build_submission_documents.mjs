#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  AlignmentType,
  BorderStyle,
  Document,
  ExternalHyperlink,
  Footer,
  Header,
  HeadingLevel,
  LevelFormat,
  LineRuleType,
  Packer,
  PageNumber,
  Paragraph,
  SectionType,
  ShadingType,
  Table,
  TableCell,
  TableOfContents,
  TableRow,
  TextRun,
  VerticalAlign,
  WidthType,
} from "docx";
import { Lexer, marked } from "marked";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_SOURCE = path.join(
  SCRIPT_DIR,
  "osteo_vision_technical_solution_20260719_zh.md",
);
const DEFAULT_OUTPUT = path.join(
  SCRIPT_DIR,
  "osteo_vision_technical_solution_20260719_zh.docx",
);

const sourcePath = path.resolve(process.argv[2] ?? DEFAULT_SOURCE);
const outputPath = path.resolve(process.argv[3] ?? DEFAULT_OUTPUT);

const PAGE_WIDTH = 11906;
const PAGE_HEIGHT = 16838;
const MARGIN_LEFT = 1587;
const MARGIN_RIGHT = 1440;
const CONTENT_WIDTH = PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT;
const BODY_FONT = {
  ascii: "Microsoft YaHei",
  hAnsi: "Microsoft YaHei",
  eastAsia: "Microsoft YaHei",
  cs: "Microsoft YaHei",
  hint: "eastAsia",
};
const MONO_FONT = {
  ascii: "Consolas",
  hAnsi: "Consolas",
  eastAsia: "Microsoft YaHei",
  cs: "Consolas",
};
const COLORS = {
  ink: "18323A",
  muted: "5A6870",
  teal: "0B6B68",
  tealLight: "DDEDEA",
  blue: "176B87",
  line: "B9C9CC",
  tableAlt: "F4F8F8",
  code: "EEF3F4",
  safety: "F3F7F6",
  white: "FFFFFF",
};

function fail(message) {
  process.stderr.write(`文档构建失败：${message}\n`);
  process.exit(1);
}

if (!fs.existsSync(sourcePath)) {
  fail(`找不到 Markdown 源文件：${sourcePath}`);
}

function inlineRuns(tokens = [], inherited = {}) {
  const children = [];

  for (const token of tokens) {
    switch (token.type) {
      case "text":
      case "escape":
        if (token.tokens?.length) {
          children.push(...inlineRuns(token.tokens, inherited));
        } else {
          children.push(
            new TextRun({ text: token.text ?? token.raw ?? "", ...inherited }),
          );
        }
        break;
      case "strong":
        children.push(...inlineRuns(token.tokens, { ...inherited, bold: true }));
        break;
      case "em":
        children.push(...inlineRuns(token.tokens, { ...inherited, italics: true }));
        break;
      case "del":
        children.push(...inlineRuns(token.tokens, { ...inherited, strike: true }));
        break;
      case "codespan":
        children.push(
          new TextRun({
            text: token.text ?? "",
            font: MONO_FONT,
            size: 19,
            color: "294850",
            shading: { type: ShadingType.CLEAR, fill: COLORS.code },
          }),
        );
        break;
      case "link": {
        const label = inlineRuns(token.tokens, {
          ...inherited,
          color: COLORS.blue,
          underline: {},
        });
        if (/^https?:\/\//i.test(token.href ?? "")) {
          children.push(
            new ExternalHyperlink({ children: label, link: token.href }),
          );
        } else {
          children.push(...label);
        }
        const visible = (token.text ?? "").trim();
        if (token.href && token.href !== visible) {
          children.push(
            new TextRun({
              text: `（${token.href}）`,
              color: COLORS.muted,
              size: 18,
            }),
          );
        }
        break;
      }
      case "br":
        children.push(new TextRun({ text: "", break: 1 }));
        break;
      case "html":
        children.push(
          new TextRun({ text: (token.text ?? token.raw ?? "").replace(/<[^>]+>/g, "") }),
        );
        break;
      default:
        if (token.tokens?.length) {
          children.push(...inlineRuns(token.tokens, inherited));
        } else if (token.text || token.raw) {
          children.push(new TextRun({ text: token.text ?? token.raw, ...inherited }));
        }
    }
  }

  return children;
}

function paragraphFromInline(tokens, options = {}) {
  return new Paragraph({
    spacing: { after: 160, line: 390, lineRule: LineRuleType.AUTO },
    alignment: AlignmentType.JUSTIFIED,
    widowControl: true,
    children: inlineRuns(tokens),
    ...options,
  });
}

const numberingConfigs = [];
let numberingSequence = 0;

function listParagraphs(token) {
  const reference = `${token.ordered ? "ordered" : "bullet"}-${++numberingSequence}`;
  numberingConfigs.push({
    reference,
    levels: [
      {
        level: 0,
        format: token.ordered ? LevelFormat.DECIMAL : LevelFormat.BULLET,
        text: token.ordered ? "%1." : "•",
        alignment: AlignmentType.LEFT,
        style: {
          paragraph: { indent: { left: 720, hanging: 360 } },
          run: { font: BODY_FONT, color: COLORS.teal },
        },
      },
    ],
  });

  return token.items.map((item) =>
    paragraphFromInline(Lexer.lexInline(item.text ?? ""), {
      numbering: { reference, level: 0 },
      spacing: { after: 90, line: 360, lineRule: LineRuleType.AUTO },
      keepNext: false,
    }),
  );
}

function tableFromToken(token) {
  const columnCount = Math.max(token.header?.length ?? 0, 1);
  const baseWidth = Math.floor(CONTENT_WIDTH / columnCount);
  const columnWidths = Array.from({ length: columnCount }, (_, index) =>
    index === columnCount - 1
      ? CONTENT_WIDTH - baseWidth * (columnCount - 1)
      : baseWidth,
  );
  const border = { style: BorderStyle.SINGLE, size: 3, color: COLORS.line };
  const borders = { top: border, bottom: border, left: border, right: border };

  const makeRow = (cells, isHeader, rowIndex) =>
    new TableRow({
      cantSplit: true,
      tableHeader: isHeader,
      children: cells.map((cell, cellIndex) =>
        new TableCell({
          width: { size: columnWidths[cellIndex], type: WidthType.DXA },
          borders,
          margins: { top: 100, bottom: 100, left: 130, right: 130 },
          verticalAlign: VerticalAlign.CENTER,
          shading: {
            type: ShadingType.CLEAR,
            fill: isHeader
              ? COLORS.teal
              : rowIndex % 2 === 0
                ? COLORS.white
                : COLORS.tableAlt,
          },
          children: [
            new Paragraph({
              spacing: { after: 0, line: 320, lineRule: LineRuleType.AUTO },
              alignment: isHeader ? AlignmentType.CENTER : AlignmentType.LEFT,
              children: inlineRuns(cell.tokens ?? Lexer.lexInline(cell.text ?? ""), {
                bold: isHeader,
                color: isHeader ? COLORS.white : COLORS.ink,
                size: isHeader ? 19 : 18,
              }),
            }),
          ],
        }),
      ),
    });

  const rows = [makeRow(token.header, true, 0)];
  token.rows.forEach((row, index) => rows.push(makeRow(row, false, index)));

  return new Table({
    width: { size: CONTENT_WIDTH, type: WidthType.DXA },
    columnWidths,
    rows,
    margins: { top: 0, bottom: 0, left: 0, right: 0 },
  });
}

function quoteParagraphs(token) {
  const text = token.text ?? token.raw ?? "";
  return [
    new Paragraph({
      border: {
        left: { style: BorderStyle.SINGLE, size: 18, color: COLORS.teal, space: 8 },
      },
      indent: { left: 320, right: 240 },
      shading: { type: ShadingType.CLEAR, fill: COLORS.safety },
      spacing: { before: 80, after: 160, line: 360, lineRule: LineRuleType.AUTO },
      children: inlineRuns(Lexer.lexInline(text), { color: COLORS.muted }),
    }),
  ];
}

function codeParagraph(token) {
  const lines = (token.text ?? "").split(/\r?\n/);
  const runs = [];
  lines.forEach((line, index) => {
    if (index > 0) runs.push(new TextRun({ text: "", break: 1 }));
    runs.push(new TextRun({ text: line || " ", font: MONO_FONT, size: 18 }));
  });
  return new Paragraph({
    shading: { type: ShadingType.CLEAR, fill: COLORS.code },
    border: {
      top: { style: BorderStyle.SINGLE, size: 2, color: COLORS.line },
      bottom: { style: BorderStyle.SINGLE, size: 2, color: COLORS.line },
      left: { style: BorderStyle.SINGLE, size: 2, color: COLORS.line },
      right: { style: BorderStyle.SINGLE, size: 2, color: COLORS.line },
    },
    indent: { left: 180, right: 180 },
    spacing: { before: 80, after: 160, line: 300, lineRule: LineRuleType.AUTO },
    children: runs,
  });
}

function bodyBlocks(tokens) {
  const blocks = [];
  for (const token of tokens) {
    switch (token.type) {
      case "space":
        break;
      case "heading": {
        const depth = Math.max(1, Math.min(3, token.depth - 1));
        const heading = [
          HeadingLevel.HEADING_1,
          HeadingLevel.HEADING_2,
          HeadingLevel.HEADING_3,
        ][depth - 1];
        blocks.push(
          new Paragraph({
            heading,
            keepNext: true,
            keepLines: true,
            children: inlineRuns(token.tokens),
          }),
        );
        break;
      }
      case "paragraph":
        blocks.push(paragraphFromInline(token.tokens));
        break;
      case "list":
        blocks.push(...listParagraphs(token));
        break;
      case "table":
        blocks.push(tableFromToken(token));
        blocks.push(new Paragraph({ spacing: { after: 100 }, children: [] }));
        break;
      case "blockquote":
        blocks.push(...quoteParagraphs(token));
        break;
      case "code":
        blocks.push(codeParagraph(token));
        break;
      case "hr":
        blocks.push(
          new Paragraph({
            border: {
              bottom: { style: BorderStyle.SINGLE, size: 6, color: COLORS.line, space: 1 },
            },
            spacing: { before: 80, after: 160 },
            children: [],
          }),
        );
        break;
      default:
        if (token.tokens?.length) {
          blocks.push(paragraphFromInline(token.tokens));
        }
    }
  }
  return blocks;
}

function sectionPageProperties(extra = {}) {
  const { page = {}, ...section } = extra;
  return {
    page: {
      size: { width: PAGE_WIDTH, height: PAGE_HEIGHT },
      margin: {
        top: 1360,
        right: MARGIN_RIGHT,
        bottom: 1300,
        left: MARGIN_LEFT,
        header: 650,
        footer: 650,
      },
      ...page,
    },
    ...section,
  };
}

function bodyHeader() {
  return new Header({
    children: [
      new Paragraph({
        border: {
          bottom: { style: BorderStyle.SINGLE, size: 5, color: COLORS.teal, space: 4 },
        },
        spacing: { after: 0 },
        children: [
          new TextRun({
            text: "OSTEO VISION  |  颌骨骨髓炎智能化荧光诊疗技术方案",
            color: COLORS.muted,
            size: 17,
          }),
        ],
      }),
    ],
  });
}

function bodyFooter() {
  return new Footer({
    children: [
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 0, after: 0 },
        children: [
          new TextRun({ text: "研发验证版平台  |  第 ", color: COLORS.muted, size: 17 }),
          new TextRun({ children: [PageNumber.CURRENT], color: COLORS.muted, size: 17 }),
          new TextRun({ text: " 页", color: COLORS.muted, size: 17 }),
        ],
      }),
    ],
  });
}

const markdown = fs.readFileSync(sourcePath, "utf8");
const tokens = marked.lexer(markdown, { gfm: true });
const titleToken = tokens.find((token) => token.type === "heading" && token.depth === 1);
const title = titleToken?.text ?? "颌骨骨髓炎智能化荧光诊疗技术方案";
const titleIndex = titleToken ? tokens.indexOf(titleToken) : -1;
const metadataToken = tokens
  .slice(titleIndex + 1)
  .find((token) => token.type === "paragraph");
const metadataTokens =
  metadataToken?.tokens ?? Lexer.lexInline("版本：0.3.0-rc.2  \n日期：2026-07-19");
const bodyTokens = tokens.filter((token) => token !== titleToken && token !== metadataToken);
const bodyChildren = bodyBlocks(bodyTokens);

const coverChildren = [
  new Paragraph({
    spacing: { before: 1000, after: 220 },
    alignment: AlignmentType.CENTER,
    children: [
      new TextRun({ text: "OSTEO VISION", bold: true, color: COLORS.teal, size: 30 }),
    ],
  }),
  new Paragraph({
    border: {
      bottom: { style: BorderStyle.SINGLE, size: 18, color: COLORS.teal, space: 12 },
    },
    spacing: { before: 260, after: 480 },
    alignment: AlignmentType.CENTER,
    children: [
      new TextRun({ text: title, bold: true, color: COLORS.ink, size: 48 }),
    ],
  }),
  new Paragraph({
    spacing: { after: 560, line: 420, lineRule: LineRuleType.AUTO },
    alignment: AlignmentType.CENTER,
    children: [
      new TextRun({
        text: "面向荧光手术显微镜的多模态融合、AI 辅助判读与三维工程验证",
        color: COLORS.muted,
        size: 25,
      }),
    ],
  }),
  new Paragraph({
    spacing: { before: 300, after: 420, line: 460, lineRule: LineRuleType.AUTO },
    alignment: AlignmentType.CENTER,
    children: inlineRuns(metadataTokens, {
      color: COLORS.ink,
      size: 22,
    }),
  }),
  new Paragraph({
    border: {
      top: { style: BorderStyle.SINGLE, size: 4, color: COLORS.line, space: 8 },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: COLORS.line, space: 8 },
    },
    shading: { type: ShadingType.CLEAR, fill: COLORS.safety },
    spacing: { before: 900, after: 0, line: 360, lineRule: LineRuleType.AUTO },
    indent: { left: 360, right: 360 },
    alignment: AlignmentType.CENTER,
    children: [
      new TextRun({
        text: "患者安全边界：所有输出均为术中参考信号与研发验证证据，须由医生复核，不用于自动确诊或替代临床判断。",
        color: COLORS.teal,
        bold: true,
        size: 20,
      }),
    ],
  }),
];

const tocChildren = [
  new Paragraph({
    spacing: { before: 120, after: 220 },
    children: [new TextRun({ text: "文档导航", color: COLORS.teal, size: 18, bold: true })],
  }),
  new TableOfContents("目录", {
    hyperlink: true,
    headingStyleRange: "1-3",
  }),
  new Paragraph({
    spacing: { before: 360, after: 0, line: 340, lineRule: LineRuleType.AUTO },
    shading: { type: ShadingType.CLEAR, fill: COLORS.safety },
    border: {
      left: { style: BorderStyle.SINGLE, size: 14, color: COLORS.teal, space: 8 },
    },
    indent: { left: 240, right: 180 },
    children: [
      new TextRun({
        text: "阅读提示：造影剂方案、代理模型指标和 L1/L2 三维结果均按研发验证边界解释；临床决策由医生完成。",
        color: COLORS.muted,
        size: 19,
      }),
    ],
  }),
];

const doc = new Document({
  creator: "Osteo Vision Team",
  title,
  subject: "颌骨骨髓炎智能化荧光诊疗比赛技术方案",
  description: "研发验证版平台技术方案，包含患者安全边界、荧光造影剂、多模态融合、AI 辅助判读与三维工程验证。",
  keywords: "颌骨骨髓炎,荧光显微镜,ICG,医学图像融合,辅助判读,患者安全",
  numbering: { config: numberingConfigs },
  styles: {
    default: {
      document: {
        run: { font: BODY_FONT, size: 21, color: COLORS.ink },
        paragraph: {
          spacing: { line: 390, lineRule: LineRuleType.AUTO },
        },
      },
    },
    paragraphStyles: [
      {
        id: "Title",
        name: "Title",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { font: BODY_FONT, size: 48, bold: true, color: COLORS.ink },
        paragraph: { spacing: { before: 300, after: 300 }, alignment: AlignmentType.CENTER },
      },
      {
        id: "Heading1",
        name: "Heading 1",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { font: BODY_FONT, size: 31, bold: true, color: COLORS.teal },
        paragraph: {
          spacing: { before: 340, after: 170 },
          outlineLevel: 0,
          border: {
            bottom: { style: BorderStyle.SINGLE, size: 7, color: COLORS.tealLight, space: 5 },
          },
        },
      },
      {
        id: "Heading2",
        name: "Heading 2",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { font: BODY_FONT, size: 25, bold: true, color: COLORS.blue },
        paragraph: { spacing: { before: 240, after: 130 }, outlineLevel: 1 },
      },
      {
        id: "Heading3",
        name: "Heading 3",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { font: BODY_FONT, size: 22, bold: true, color: COLORS.ink },
        paragraph: { spacing: { before: 200, after: 110 }, outlineLevel: 2 },
      },
      {
        id: "TOCHeading",
        name: "TOC Heading",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { font: BODY_FONT, size: 34, bold: true, color: COLORS.ink },
        paragraph: {
          spacing: { before: 120, after: 260 },
          border: {
            bottom: { style: BorderStyle.SINGLE, size: 10, color: COLORS.teal, space: 8 },
          },
        },
      },
    ],
  },
  sections: [
    {
      properties: sectionPageProperties({ verticalAlign: VerticalAlign.TOP }),
      children: coverChildren,
    },
    {
      properties: sectionPageProperties({ type: SectionType.NEXT_PAGE }),
      headers: { default: bodyHeader() },
      children: tocChildren,
    },
    {
      properties: sectionPageProperties({
        type: SectionType.NEXT_PAGE,
        page: { pageNumbers: { start: 1 } },
      }),
      headers: { default: bodyHeader() },
      footers: { default: bodyFooter() },
      children: bodyChildren,
    },
  ],
});

fs.mkdirSync(path.dirname(outputPath), { recursive: true });
const buffer = await Packer.toBuffer(doc);
fs.writeFileSync(outputPath, buffer);
process.stdout.write(`已生成 DOCX：${outputPath}\n`);
