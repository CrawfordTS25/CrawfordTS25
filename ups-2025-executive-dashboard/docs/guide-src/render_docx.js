const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType,
  PageOrientation, PageBreak, Header, Footer, PageNumber,
} = require("docx");
const { meta, blocks } = require("./content.js");

const PAGE_W = 12240, PAGE_H = 15840, MARGIN = 1440;
const INK = "1A1A1A", MUTED = "5F5E5A", ACCENT = "1F5FA9",
      WARN = "8A5A00", CRIT = "A32020",
      RULE = "D8D7D0", BAND = "F3F5F8", CODEBG = "F2F2EF", HEADFILL = "E9ECF1";

const KIND = { info: ACCENT, warn: WARN, crit: CRIT };

// A run object from content.js -> a docx TextRun.
const toRun = (r, opts = {}) =>
  new TextRun({
    text: r.text,
    bold: r.bold || opts.bold,
    italics: r.italic,
    font: r.code ? "Consolas" : undefined,
    size: r.code ? (opts.size ? opts.size - 2 : 19) : (opts.size ?? 21),
    color: r.code ? "1A3A5A" : (opts.color ?? INK),
  });

const para = (runs, opts = {}) =>
  new Paragraph({
    spacing: { before: opts.before ?? 0, after: opts.after ?? 130, line: 278 },
    alignment: opts.align,
    indent: opts.indent,
    shading: opts.fill ? { type: ShadingType.CLEAR, fill: opts.fill } : undefined,
    border: opts.border,
    children: runs.map((r) => toRun(r, opts)),
  });

const heading = (text, level) => {
  const spec = {
    1: { size: 30, before: 380, after: 170, color: INK, level: HeadingLevel.HEADING_1 },
    2: { size: 24, before: 300, after: 130, color: INK, level: HeadingLevel.HEADING_2 },
    3: { size: 21, before: 220, after: 110, color: MUTED, level: HeadingLevel.HEADING_3 },
  }[level];
  return new Paragraph({
    heading: spec.level,
    spacing: { before: spec.before, after: spec.after },
    children: [new TextRun({ text, size: spec.size, bold: true, color: spec.color })],
  });
};

const codeBlock = (lines) =>
  lines.map((l, idx) =>
    new Paragraph({
      spacing: {
        before: idx === 0 ? 110 : 0,
        after: idx === lines.length - 1 ? 170 : 0,
        line: 262,
      },
      shading: { type: ShadingType.CLEAR, fill: CODEBG },
      indent: { left: 190, right: 190 },
      children: [new TextRun({ text: l || " ", font: "Consolas", size: 18, color: "26323A" })],
    }));

const callout = (label, body, kind) => {
  const colour = KIND[kind] || ACCENT;
  const border = { left: { style: BorderStyle.SINGLE, size: 18, color: colour, space: 10 } };
  return [
    new Paragraph({
      spacing: { before: 170, after: 0, line: 278 },
      shading: { type: ShadingType.CLEAR, fill: BAND },
      indent: { left: 170, right: 170 },
      border,
      children: [new TextRun({ text: label, bold: true, size: 20, color: colour })],
    }),
    new Paragraph({
      spacing: { before: 50, after: 210, line: 278 },
      shading: { type: ShadingType.CLEAR, fill: BAND },
      indent: { left: 170, right: 170 },
      border,
      children: body.map((r) => toRun(r, { size: 20 })),
    }),
  ];
};

const CELL_BORDERS = {
  top: { style: BorderStyle.SINGLE, size: 2, color: RULE },
  bottom: { style: BorderStyle.SINGLE, size: 2, color: RULE },
  left: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
  right: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
};

// A cell is an array of lines; each line is an array of runs.
const makeCell = (lines, width, opts = {}) =>
  new TableCell({
    width: { size: width, type: WidthType.DXA },
    borders: CELL_BORDERS,
    shading: opts.fill ? { type: ShadingType.CLEAR, fill: opts.fill } : undefined,
    margins: { top: 95, bottom: 95, left: 135, right: 135 },
    children: lines.map((line, idx) =>
      new Paragraph({
        spacing: { after: idx === lines.length - 1 ? 0 : 70, line: 262 },
        children: line.map((r) => toRun(r, { size: 19, color: opts.color, bold: opts.bold })),
      })),
  });

const makeTable = (widths, header, rows) =>
  new Table({
    columnWidths: widths,
    width: { size: widths.reduce((a, x) => a + x, 0), type: WidthType.DXA },
    rows: [
      new TableRow({
        tableHeader: true,
        children: header.map((h, idx) =>
          makeCell([[{ text: h }]], widths[idx],
                   { fill: HEADFILL, bold: true, color: MUTED })),
      }),
      ...rows.map((row) =>
        new TableRow({
          children: row.map((cellLines, idx) => makeCell(cellLines, widths[idx])),
        })),
    ],
  });

// ------------------------------------------------------------------ build

const children = [];

// Cover
children.push(new Paragraph({
  spacing: { before: 1700, after: 0 },
  children: [new TextRun({ text: meta.eyebrow, size: 22, color: MUTED })],
}));
children.push(new Paragraph({
  spacing: { before: 70, after: 100 },
  children: [new TextRun({ text: meta.title, size: 46, bold: true, color: INK })],
}));
children.push(new Paragraph({
  spacing: { after: 260 },
  children: [new TextRun({ text: meta.subtitle, size: 26, color: ACCENT })],
}));
children.push(new Paragraph({
  spacing: { after: 90 },
  border: { top: { style: BorderStyle.SINGLE, size: 6, color: RULE, space: 10 } },
  children: [],
}));
meta.facts.forEach((f) => children.push(para(f, { color: MUTED })));

for (const block of blocks) {
  switch (block.t) {
    case "h1": children.push(heading(block.text, 1)); break;
    case "h2": children.push(heading(block.text, 2)); break;
    case "h3": children.push(heading(block.text, 3)); break;
    case "p":
      children.push(para(block.runs,
        block.muted ? { color: MUTED, size: 20 } : {}));
      break;
    case "code": children.push(...codeBlock(block.lines)); break;
    case "callout": children.push(...callout(block.label, block.body, block.kind)); break;
    case "table":
      children.push(makeTable(block.widths, block.header, block.rows));
      children.push(new Paragraph({ spacing: { after: 200 }, children: [] }));
      break;
    case "pagebreak":
      children.push(new Paragraph({ children: [new PageBreak()] }));
      break;
    case "hr":
      children.push(new Paragraph({
        spacing: { before: 180, after: 210 },
        border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: RULE, space: 6 } },
        children: [],
      }));
      break;
    default: throw new Error("unknown block type: " + block.t);
  }
}

const doc = new Document({
  creator: "UPS 2025 Executive Dashboard build",
  title: meta.title,
  description: meta.subtitle,
  styles: { default: { document: { run: { font: "Calibri", size: 21, color: INK } } } },
  sections: [{
    properties: {
      page: {
        size: { width: PAGE_W, height: PAGE_H, orientation: PageOrientation.PORTRAIT },
        margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN },
      },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          spacing: { after: 90 },
          border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: RULE, space: 6 } },
          children: [new TextRun({ text: meta.header, size: 17, color: MUTED })],
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          children: [new TextRun({
            children: ["Page ", PageNumber.CURRENT, " of ", PageNumber.TOTAL_PAGES],
            size: 17, color: MUTED,
          })],
        })],
      }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  const out = process.argv[2] || "guide.docx";
  fs.writeFileSync(out, buf);
  console.log("docx:", out, buf.length, "bytes");
});
