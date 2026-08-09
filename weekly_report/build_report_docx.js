// 주간 보고서 JSON(+선택 AI JSON) → 양식(정책 동향 양식.hwp) 스타일 DOCX
// 사용: node build_report_docx.js <weekly.json> <out.docx> [ai.json]
// 이후 한글 COM으로 out.docx 를 열어 .hwpx 로 저장하면 네이티브 한글 문서가 된다.
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  WidthType, BorderStyle, ShadingType, AlignmentType, VerticalAlign,
  ExternalHyperlink, Header, Footer, PageNumber,
} = require("docx");

const [, , weeklyPath, outPath, aiPath] = process.argv;
const R = JSON.parse(fs.readFileSync(weeklyPath, "utf-8"));
const AI = aiPath ? JSON.parse(fs.readFileSync(aiPath, "utf-8")) : R.ai;
let CATMAP = {};
try {
  const cj = JSON.parse(fs.readFileSync(__dirname + "/../docs/data/categories.json", "utf-8"));
  (cj.categories || cj).forEach(c => CATMAP[c.id] = c.label);
} catch (e) {}

const FONT = { ascii: "Malgun Gothic", eastAsia: "Malgun Gothic", hAnsi: "Malgun Gothic" };
const NAVY = "1F3864", POINT_BG = "F0F4FA", HEAD_BG = "DFE6F2", C0_BG = "F5F7FB";
const W = 9638;
const run = (t, o = {}) => new TextRun({ text: t, font: FONT, size: 19, ...o });
const shortD = s => { if (!s || !s.includes("-")) return s || ""; const [y, m, d] = s.split("-"); return `${y.slice(2)}.${+m}.${+d}.`; };
const cut = (s, n) => (s || "").length > n ? s.slice(0, n - 1) + "…" : (s || "");
const thin = { style: BorderStyle.SINGLE, size: 4, color: "333333" };
const noB = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };

function link(url, label = "[원문]") {
  return new ExternalHyperlink({ link: url, children: [run(label, { size: 15, color: "1D4ED8", underline: {} })] });
}
function catRuns(cats) {
  return (cats || []).map(c => run(` ${CATMAP[c] || c}`, { size: 13, color: "4338CA" }));
}

// ○ 제목 (날짜) [원문]
const oTitle = (base) => new Paragraph({
  children: [run(`○ ${base.title}`, { bold: true, size: 21 }),
    run(`  (${shortD(base.date)})  `, { size: 16, color: "888888" }),
    link(base.link), ...catRuns(base.categories)],
  spacing: { before: 160, after: 30 }, keepNext: true,
});
const dash = (t) => new Paragraph({ children: [run(`- ${t}`, { size: 18 })], indent: { left: 280, hanging: 190 }, spacing: { after: 24 } });
const bul = (t) => new Paragraph({ children: [run(`• ${t}`, { size: 17 })], indent: { left: 620, hanging: 200 }, spacing: { after: 24 } });
const dot = (t) => new Paragraph({
  children: [run(`· ${t}`, { bold: true, size: 18 })],
  shading: { type: ShadingType.CLEAR, fill: POINT_BG },
  indent: { left: 300 }, spacing: { before: 40, after: 100 },
});

// 분야|주요내용 표
function fieldTable(t) {
  const cols = t.cols || ["분야", "주요내용"];
  const w0 = 2100, w1 = W - w0;
  const th = (s, w) => new TableCell({
    width: { size: w, type: WidthType.DXA }, shading: { type: ShadingType.CLEAR, fill: HEAD_BG },
    margins: { top: 40, bottom: 40, left: 80, right: 80 }, verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [run(s, { bold: true, size: 17 })] })],
  });
  const rows = [new TableRow({ tableHeader: true, children: [th(cols[0], w0), th(cols[1], w1)] })];
  for (const row of (t.rows || [])) {
    const field = row.field ?? row[0] ?? "";
    let content = row.content ?? row[1] ?? [];
    if (!Array.isArray(content)) content = [content];
    rows.push(new TableRow({ children: [
      new TableCell({ width: { size: w0, type: WidthType.DXA }, shading: { type: ShadingType.CLEAR, fill: C0_BG },
        verticalAlign: VerticalAlign.CENTER, margins: { top: 40, bottom: 40, left: 80, right: 80 },
        children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [run(field, { bold: true, size: 16 })] })] }),
      new TableCell({ width: { size: w1, type: WidthType.DXA }, margins: { top: 40, bottom: 40, left: 100, right: 80 },
        children: content.map(c => new Paragraph({ children: [run(`• ${c}`, { size: 16 })], indent: { left: 180, hanging: 180 }, spacing: { after: 20 } })) }),
    ] }));
  }
  return new Table({
    width: { size: W, type: WidthType.DXA }, columnWidths: [w0, W - w0],
    indent: { size: 280, type: WidthType.DXA },
    borders: { top: thin, bottom: thin, left: thin, right: thin, insideHorizontal: thin, insideVertical: thin },
    rows,
  });
}

// ☞ 사용자 코멘트 (보고서 스튜디오 편집에서 입력)
function cmt(text) {
  return new Paragraph({
    children: [run(`☞ ${text}`, { bold: true, size: 19 })],
    shading: { type: ShadingType.CLEAR, fill: "FFF6DD" },
    indent: { left: 280 }, spacing: { before: 40, after: 100 },
  });
}

function richItem(base, rep, out) {
  if (base.excluded) return;               // 편집에서 제외한 항목
  out.push(oTitle(base));
  if (rep.lead) out.push(dash(rep.lead));
  for (const p of (rep.points || [])) {
    if (typeof p === "string") out.push(dash(p));
    else if (p.table) out.push(fieldTable(p.table));
    else if (p.h || p.header) { out.push(dash(p.h || p.header)); (p.items || p.sub || []).forEach(s => out.push(bul(s))); }
  }
  if (rep.insight) out.push(dot(rep.insight));
  if (base.userComment) out.push(cmt(base.userComment));
}

// ▨ 부처명 (양식 마커)
function deptHead(dept, count) {
  return new Paragraph({
    children: [run("▨ ", { size: 24, color: NAVY }), run(dept, { bold: true, size: 24 }),
      run(`  (${count}건)`, { size: 14, color: "999999" })],
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: NAVY, space: 2 } },
    spacing: { before: 320, after: 120 }, keepNext: true,
  });
}

// ── 본문 조립 ──
const children = [];
children.push(new Paragraph({ alignment: AlignmentType.CENTER, children: [run("2026 포항테크노파크 미래전략팀", { bold: true, size: 22 })], spacing: { after: 20 } }));
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  children: [run(`${R.weekLabel} 정부정책 발표 주요 내용`, { bold: true, size: 36 }), run(`  (${R.period})`, { bold: true, size: 24, color: "555555" })],
  spacing: { after: 180 },
}));

// 키워드 박스
const kwPars = [];
if (AI && AI.keywords) {
  for (const [d, k] of Object.entries(AI.keywords))
    kwPars.push(new Paragraph({ children: [run("○ "), run(`${d} : `, { bold: true }), run(Array.isArray(k) ? k.join(", ") : k)], indent: { left: 200, hanging: 200 }, spacing: { after: 40 } }));
} else {
  for (const g of R.groups)
    kwPars.push(new Paragraph({ children: [run("○ "), run(`${g.dept} : `, { bold: true }), run(g.items.slice(0, 3).map(i => cut(i.title, 34)).join(" / "))], indent: { left: 200, hanging: 200 }, spacing: { after: 40 } }));
}
children.push(new Table({
  width: { size: W, type: WidthType.DXA }, columnWidths: [W],
  borders: { top: thin, bottom: thin, left: thin, right: thin },
  rows: [new TableRow({ children: [new TableCell({ width: { size: W, type: WidthType.DXA }, margins: { top: 120, bottom: 120, left: 160, right: 160 }, children: kwPars })] })],
}));
children.push(new Paragraph({
  alignment: AlignmentType.RIGHT,
  children: [run(`(출처 : 대한민국 정책브리핑 · KDI 경제정보센터 수집자료 ${R.total}건, ${R.start}~${R.end}${AI ? " / AI 요약 적용" : ""})`, { size: 15, color: "666666" })],
  spacing: { before: 60, after: 40 },
}));

// 부처별 섹션
for (const g of R.groups) {
  children.push(deptHead(g.dept, g.items.length));
  const reports = AI && AI.reports && AI.reports[g.dept];
  if (reports && reports.length) {
    const used = new Set();
    for (const rep of reports) {
      let base = (typeof rep.idx === "number") ? g.items[rep.idx] : null;
      if (!base) base = g.items.find(i => i.title === rep.title);
      if (!base) continue;
      used.add(base.title);
      richItem(base, rep, children);
    }
    const rest = g.items.filter(i => !used.has(i.title));
    if (rest.length) children.push(new Paragraph({ children: [run(`그 외 ${rest.length}건: ` + rest.slice(0, 8).map(i => i.title).join(" / "), { size: 15, color: "888888" })], indent: { left: 280 }, spacing: { after: 40 } }));
  } else {
    for (const i of g.items.slice(0, 6)) {
      if (i.excluded) continue;            // 편집에서 제외한 항목
      children.push(oTitle(i));
      (i.bullets || []).forEach(b => children.push(dash(b)));
      if (i.userComment) children.push(cmt(i.userComment));
    }
  }
}

// 기타 부처 표
if (R.others && R.others.length) {
  children.push(deptHead("기타 부처", R.others.reduce((a, g) => a + g.items.length, 0)));
  const w0 = 1900;
  const rows = R.others.map(g => new TableRow({ children: [
    new TableCell({ width: { size: w0, type: WidthType.DXA }, shading: { type: ShadingType.CLEAR, fill: "F5F5F5" }, verticalAlign: VerticalAlign.CENTER, margins: { top: 40, bottom: 40, left: 100, right: 60 },
      children: [new Paragraph({ children: [run(`${g.dept} (${g.items.length})`, { bold: true, size: 16 })] })] }),
    new TableCell({ width: { size: W - w0, type: WidthType.DXA }, margins: { top: 40, bottom: 40, left: 100, right: 80 },
      children: [new Paragraph({ children: [
        ...g.items.slice(0, 4).flatMap((i, n) => [run((n ? " / " : "") + i.title, { size: 15 }), run(` (${shortD(i.date)})`, { size: 13, color: "999999" })]),
        ...(g.items.length > 4 ? [run(` 외 ${g.items.length - 4}건`, { size: 14, color: "999999" })] : []),
      ] })] }),
  ] }));
  children.push(new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [w0, W - w0],
    borders: { top: thin, bottom: thin, left: thin, right: thin, insideHorizontal: thin, insideVertical: thin }, rows }));
}

const doc = new Document({
  styles: { default: { document: { run: { font: FONT, size: 19 } } } },
  sections: [{
    properties: { page: { margin: { top: 1000, bottom: 1000, left: 1134, right: 1134 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: ["- ", PageNumber.CURRENT, " -"], font: FONT, size: 16 })] })] }) },
    children,
  }],
});
Packer.toBuffer(doc).then(buf => { fs.writeFileSync(outPath, buf); console.log("saved:", outPath, buf.length, "bytes"); });
