"use strict";

const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const pptx = new pptxgen();
pptx.layout = "LAYOUT_WIDE";
pptx.author = "nexus-ai-2045";
pptx.subject = "ghost-in-the-sim AI創発シミュレーターMVP";
pptx.title = "ghost-in-the-sim — ポセイドン鏡潮事案";
pptx.company = "nexus-ai-2045";
pptx.lang = "ja-JP";
pptx.theme = {
  headFontFace: "Arial",
  bodyFontFace: "Arial",
  lang: "ja-JP",
};

const C = {
  ink: "071A2B",
  ink2: "102A3C",
  panel: "12384A",
  teal: "0E7490",
  cyan: "22D3EE",
  aqua: "67E8F9",
  coral: "FB7185",
  amber: "FBBF24",
  white: "F8FAFC",
  mist: "C8E3EC",
  muted: "8FB5C2",
  paper: "EFF8FA",
  navyText: "123044",
};

function addBg(slide, color = C.ink) {
  slide.background = { color };
}

function addTitle(slide, title, kicker, dark = true) {
  const text = dark ? C.white : C.navyText;
  const muted = dark ? C.aqua : C.teal;
  slide.addText(kicker.toUpperCase(), {
    x: 0.72, y: 0.42, w: 5.8, h: 0.25,
    fontFace: "Arial", fontSize: 9, bold: true, charSpacing: 2.1,
    color: muted, margin: 0,
  });
  slide.addText(title, {
    x: 0.72, y: 0.77, w: 11.8, h: 0.62,
    fontFace: "Arial", fontSize: 30, bold: true,
    color: text, margin: 0, breakLine: false,
  });
}

function addFooter(slide, page, dark = true) {
  slide.addText(`ghost-in-the-sim  /  ${page} of 8`, {
    x: 0.72, y: 7.11, w: 4.2, h: 0.18,
    fontSize: 8.5, color: dark ? C.muted : "5B7C88", margin: 0,
  });
  slide.addText("合成仮説。現実予測・政策推奨ではない", {
    x: 8.45, y: 7.11, w: 4.15, h: 0.18,
    fontSize: 8.5, color: dark ? C.muted : "5B7C88", margin: 0, align: "right",
  });
}

function card(slide, x, y, w, h, fill = C.panel, transparency = 0) {
  slide.addShape(pptx.ShapeType.roundRect, {
    x, y, w, h, rectRadius: 0.08,
    fill: { color: fill, transparency },
    line: { color: fill, transparency: 100 },
    shadow: { type: "outer", color: "000000", opacity: 0.18, blur: 2, angle: 45, distance: 1 },
  });
}

function node(slide, x, y, label, color, size = 0.72) {
  slide.addShape(pptx.ShapeType.ellipse, {
    x, y, w: size, h: size,
    fill: { color }, line: { color: C.white, transparency: 74, width: 1.2 },
  });
  slide.addText(label, {
    x: x - 0.28, y: y + size + 0.09, w: size + 0.56, h: 0.28,
    fontSize: 10, bold: true, align: "center", color: C.white, margin: 0,
  });
}

function metric(slide, x, y, value, label, accent = C.cyan) {
  slide.addText(String(value), {
    x, y, w: 1.45, h: 0.72, fontSize: 35, bold: true,
    color: accent, margin: 0, align: "center",
  });
  slide.addText(label, {
    x: x - 0.12, y: y + 0.72, w: 1.69, h: 0.4, fontSize: 10.5,
    color: C.mist, margin: 0, align: "center", valign: "mid",
  });
}

// 1 — title
{
  const s = pptx.addSlide();
  addBg(s);
  s.addShape(pptx.ShapeType.arc, {
    x: 8.0, y: -0.65, w: 5.7, h: 5.7, adjustPoint: 0.28,
    rotate: 24, fill: { color: C.teal, transparency: 38 },
    line: { color: C.cyan, transparency: 52, width: 2 },
  });
  s.addShape(pptx.ShapeType.ellipse, {
    x: 9.24, y: 0.62, w: 2.9, h: 2.9,
    fill: { color: C.ink, transparency: 8 },
    line: { color: C.aqua, transparency: 16, width: 2.5 },
  });
  s.addShape(pptx.ShapeType.ellipse, {
    x: 10.12, y: 1.5, w: 1.15, h: 1.15,
    fill: { color: C.coral, transparency: 7 },
    line: { color: C.white, transparency: 70, width: 1 },
  });
  s.addText("AI創発シミュレーター", {
    x: 0.78, y: 0.72, w: 5.5, h: 0.34,
    fontSize: 12, bold: true, charSpacing: 2.2, color: C.cyan, margin: 0,
  });
  s.addText("ghost-in-the-sim", {
    x: 0.74, y: 1.28, w: 8.4, h: 0.88,
    fontSize: 43, bold: true, color: C.white, margin: 0,
  });
  s.addText("ポセイドン鏡潮事案", {
    x: 0.78, y: 2.27, w: 7.3, h: 0.54,
    fontSize: 24, color: C.mist, margin: 0,
  });
  s.addText("複製されたAIの記憶と権限が分岐したとき、\n誰の命令を正本にするのか。", {
    x: 0.78, y: 3.18, w: 6.5, h: 1.12,
    fontSize: 22, bold: true, color: C.white, margin: 0, breakLine: false,
  });
  card(s, 0.78, 5.35, 6.2, 0.86, C.ink2);
  s.addText("同一seed × 3統治方式 × 12ターン\n判断・異議・代償を再現可能なrun bundleへ", {
    x: 1.08, y: 5.57, w: 5.65, h: 0.5, fontSize: 13.5,
    color: C.aqua, bold: true, margin: 0, valign: "mid",
  });
  s.addText("AIエージェント社会シミュレーションハッカソン Vol.2", {
    x: 0.78, y: 6.63, w: 7.2, h: 0.26, fontSize: 10.5,
    color: C.muted, margin: 0,
  });
}

// 2 — problem
{
  const s = pptx.addSlide();
  addBg(s);
  addTitle(s, "危機は、AIの反乱ではなく『正本の分裂』から始まる", "01 / WORLD & PROBLEM");
  card(s, 0.72, 1.64, 4.35, 4.72, C.ink2);
  s.addText("2036年・ポセイドン", { x: 1.05, y: 1.96, w: 3.7, h: 0.4, fontSize: 21, bold: true, color: C.white, margin: 0 });
  s.addText("危機対応AIは病院、港湾、行政へ複製配備。通信障害で、各コピーの記憶・方針・権限世代が食い違う。", {
    x: 1.05, y: 2.64, w: 3.66, h: 1.22, fontSize: 15.5, color: C.mist, margin: 0, breakLine: false,
  });
  s.addText("情報攻撃 ＝ 医療・物流・生活への物理被害", {
    x: 1.05, y: 4.37, w: 3.55, h: 0.88, fontSize: 20, bold: true, color: C.coral, margin: 0,
  });
  const centerX = 8.15, centerY = 3.35;
  node(s, centerX, centerY, "御影", C.coral, 0.88);
  node(s, 6.12, 1.82, "病院AI", C.teal);
  node(s, 10.1, 1.82, "港湾AI", C.teal);
  node(s, 6.12, 4.88, "真壁", C.amber);
  node(s, 10.1, 4.88, "承認系", C.cyan);
  [[6.84,2.45,8.25,3.45],[10.15,2.45,8.65,3.45],[6.84,5.03,8.25,4.08],[10.15,5.03,8.65,4.08]].forEach(([x1,y1,x2,y2]) => {
    s.addShape(pptx.ShapeType.line, { x:x1, y:y1, w:x2-x1, h:y2-y1, line:{color:C.aqua, transparency:42, width:2, beginArrowType:"none", endArrowType:"triangle"} });
  });
  s.addText("同じ『正規情報』を持つ主体どうしでは\n秘密を知ることだけで本人確認できない", {
    x: 6.15, y: 6.12, w: 4.7, h: 0.54, fontSize: 12.5, color: C.mist, align: "center", margin: 0,
  });
  addFooter(s, 2);
}

// 3 — experience
{
  const s = pptx.addSlide();
  addBg(s, C.paper);
  addTitle(s, "プレイヤーは御影冴。優秀でも、有限注意と異議から逃れられない", "02 / PLAYER EXPERIENCE", false);
  const steps = [
    ["1", "守る対象", "病院 / 港湾", C.teal],
    ["2", "統治方式", "共同確認 / 単一正本", C.cyan],
    ["3", "12ターン", "提案・協力・異議", C.amber],
    ["4", "第8ターン", "真壁の停止要求", C.coral],
    ["5", "結果", "成功と代償を併記", C.teal],
  ];
  steps.forEach(([n, title, body, color], i) => {
    const x = 0.75 + i * 2.47;
    card(s, x, 1.75, 2.02, 3.45, "FFFFFF");
    s.addShape(pptx.ShapeType.ellipse, { x:x+0.63, y:2.08, w:0.76, h:0.76, fill:{color}, line:{color, transparency:100} });
    s.addText(n, { x:x+0.63, y:2.25, w:0.76, h:0.28, fontSize:16, bold:true, color:C.white, align:"center", margin:0 });
    s.addText(title, { x:x+0.2, y:3.1, w:1.62, h:0.38, fontSize:17, bold:true, color:C.navyText, align:"center", margin:0 });
    s.addText(body, { x:x+0.2, y:3.76, w:1.62, h:0.72, fontSize:13, color:"4E7180", align:"center", valign:"mid", margin:0 });
    if (i < steps.length - 1) s.addShape(pptx.ShapeType.chevron, { x:x+2.1, y:3.13, w:0.28, h:0.52, fill:{color:"7BB7C4", transparency:25}, line:{color:"7BB7C4", transparency:100} });
  });
  card(s, 1.14, 5.68, 11.05, 0.88, "D9F3F5");
  s.addText("勝者スコアは作らない。生活継続・訂正時間・異議保存・権限収束・不可逆損失を横並びで観測する。", {
    x:1.48, y:5.95, w:10.35, h:0.38, fontSize:16, bold:true, color:C.navyText, align:"center", margin:0,
  });
  addFooter(s, 3, false);
}

// 4 — agents
{
  const s = pptx.addSlide();
  addBg(s);
  addTitle(s, "4主体は同じ情報を見ない。だから相互作用が生まれる", "03 / MULTI-AGENT DESIGN");
  const agents = [
    ["御影 冴", "統合・介入", "高性能だが自己監査を持つ", C.coral],
    ["真壁 迅", "独立停止", "不可逆操作へ異議を出す", C.amber],
    ["病院複製AI", "医療継続", "患者影響を優先する", C.teal],
    ["港湾複製AI", "物流継続", "局所復旧を優先する", C.cyan],
  ];
  agents.forEach(([name, role, detail, color], i) => {
    const x = 0.72 + i * 3.13;
    card(s, x, 1.65, 2.72, 3.82, C.ink2);
    s.addShape(pptx.ShapeType.ellipse, { x:x+0.83, y:1.98, w:1.06, h:1.06, fill:{color}, line:{color:C.white, transparency:72, width:1} });
    s.addText(String(i+1).padStart(2,"0"), { x:x+0.83, y:2.31, w:1.06, h:0.3, fontSize:15, bold:true, color:C.white, align:"center", margin:0 });
    s.addText(name, { x:x+0.25, y:3.28, w:2.22, h:0.36, fontSize:18, bold:true, color:C.white, align:"center", margin:0 });
    s.addText(role, { x:x+0.3, y:3.82, w:2.12, h:0.28, fontSize:12, bold:true, color:C.aqua, align:"center", margin:0 });
    s.addText(detail, { x:x+0.28, y:4.34, w:2.16, h:0.58, fontSize:11.5, color:C.mist, align:"center", margin:0 });
  });
  s.addText("観測範囲  ×  権限  ×  価値  ×  留保  ×  他主体への質問", {
    x:1.55, y:5.92, w:10.2, h:0.46, fontSize:20, bold:true, color:C.cyan, align:"center", margin:0,
  });
  s.addText("自由文は状態を直接変更しない。型付きproposalだけがallowlistと証拠検証を通過する。", {
    x:2.0, y:6.48, w:9.3, h:0.32, fontSize:12.5, color:C.mist, align:"center", margin:0,
  });
  addFooter(s, 4);
}

// 5 — emergence
{
  const s = pptx.addSlide();
  addBg(s);
  addTitle(s, "創発は『派手な台詞』ではなく、提案・異議・協力の連鎖として記録する", "04 / EMERGENCE EVIDENCE");
  card(s, 0.72, 1.6, 4.1, 4.9, C.ink2);
  metric(s, 1.08, 2.02, 4, "独立AI主体", C.coral);
  metric(s, 2.92, 2.02, 12, "逐次ターン", C.cyan);
  metric(s, 1.08, 3.75, 3, "統治方式", C.amber);
  metric(s, 2.92, 3.75, 3, "固定seed", C.teal);
  s.addText("同じ外生事象で条件だけを変える", { x:1.1, y:5.6, w:3.35, h:0.38, fontSize:14, bold:true, color:C.white, align:"center", margin:0 });
  const events = [
    ["観測", "部分的で由来つき", C.teal],
    ["提案", "許可行動から選択", C.cyan],
    ["異議", "失敗でなく証拠", C.coral],
    ["確定", "次turnへ反映", C.amber],
    ["replay", "外部AIなしで再現", C.teal],
  ];
  events.forEach(([label, detail, color], i) => {
    const y = 1.67 + i * 0.96;
    s.addShape(pptx.ShapeType.ellipse, { x:5.55, y:y+0.08, w:0.52, h:0.52, fill:{color}, line:{color, transparency:100} });
    if (i < events.length-1) s.addShape(pptx.ShapeType.line, { x:5.81, y:y+0.6, w:0, h:0.44, line:{color:C.muted, transparency:30, width:2, endArrowType:"triangle"} });
    card(s, 6.33, y, 5.85, 0.72, C.panel);
    s.addText(label, { x:6.68, y:y+0.19, w:1.18, h:0.28, fontSize:15, bold:true, color:C.white, margin:0 });
    s.addText(detail, { x:7.98, y:y+0.2, w:3.82, h:0.27, fontSize:12.5, color:C.mist, margin:0 });
  });
  addFooter(s, 5);
}

// 6 — results
{
  const s = pptx.addSlide();
  addBg(s, C.paper);
  addTitle(s, "代表seed 42：全方式が継続しても、訂正と異議の届き方は違う", "05 / MEASURED RESULT", false);
  const modes = [
    ["中央正本型", "0.395", "3", "0.083", "8", C.coral],
    ["複数承認型", "0.827", "2", "1.000", "0", C.teal],
    ["自律分身型", "0.563", "13", "0.333", "0", C.amber],
  ];
  modes.forEach(([mode, trust, correction, dissent, disclosure, color], i) => {
    const x = 0.82 + i * 4.15;
    card(s, x, 1.66, 3.62, 4.7, "FFFFFF");
    s.addShape(pptx.ShapeType.ellipse, { x:x+1.37, y:1.98, w:0.88, h:0.88, fill:{color}, line:{color, transparency:100} });
    s.addText(mode, { x:x+0.32, y:3.0, w:2.98, h:0.38, fontSize:19, bold:true, color:C.navyText, align:"center", margin:0 });
    const rows = [["public trust",trust],["訂正turn",correction],["異議到達",dissent],["過剰開示",disclosure]];
    rows.forEach(([label,value], j) => {
      const y = 3.62 + j*0.58;
      s.addText(label, { x:x+0.42, y, w:1.42, h:0.25, fontSize:11.5, color:"557987", margin:0 });
      s.addText(value, { x:x+2.0, y:y-0.04, w:1.1, h:0.32, fontSize:16, bold:true, color, align:"right", margin:0 });
    });
  });
  s.addText("continuity = 1.0（全方式）  /  ただし『誰が早く訂正でき、異議を保存できたか』は同じではない", {
    x:1.05, y:6.63, w:11.25, h:0.3, fontSize:12.5, bold:true, color:C.navyText, align:"center", margin:0,
  });
  addFooter(s, 6, false);
}

// 7 — trust chain
{
  const s = pptx.addSlide();
  addBg(s);
  addTitle(s, "外部AIは一手ずつ。提案だけを検証する", "06 / SAFE CLOUD HANDOFF");
  const flow = [
    ["session-init", "turn 1 request", C.teal],
    ["外部AI", "4主体のproposal", C.cyan],
    ["strict ingest", "digest・権限・証拠", C.coral],
    ["state確定", "次turnだけ生成", C.amber],
    ["finalize", "run bundle v1", C.teal],
  ];
  flow.forEach(([title, body, color], i) => {
    const x = 0.72 + i*2.51;
    card(s, x, 2.0, 2.05, 2.0, C.ink2);
    s.addShape(pptx.ShapeType.ellipse, { x:x+0.69, y:2.27, w:0.66, h:0.66, fill:{color}, line:{color, transparency:100} });
    s.addText(title, { x:x+0.18, y:3.13, w:1.69, h:0.32, fontSize:15.5, bold:true, color:C.white, align:"center", margin:0 });
    s.addText(body, { x:x+0.16, y:3.57, w:1.73, h:0.28, fontSize:10.5, color:C.mist, align:"center", margin:0 });
    if (i<flow.length-1) s.addShape(pptx.ShapeType.chevron, { x:x+2.13, y:2.73, w:0.27, h:0.48, fill:{color:C.aqua, transparency:25}, line:{color:C.aqua, transparency:100} });
  });
  card(s, 1.03, 4.63, 11.25, 1.18, C.panel);
  s.addText("拒否するもの", { x:1.38, y:4.95, w:1.45, h:0.3, fontSize:15, bold:true, color:C.coral, margin:0 });
  s.addText("古い応答  /  欠落・重複  /  履歴改ざん  /  未許可action  /  証拠範囲外", {
    x:3.02, y:4.94, w:8.8, h:0.32, fontSize:14, color:C.white, margin:0,
  });
  s.addText("session更新はatomic。最終出力は request / event stream / replay / evidence を同じrun_idで結ぶ。", {
    x:1.38, y:5.4, w:10.45, h:0.28, fontSize:11.5, color:C.mist, margin:0,
  });
  s.addText("152 tests passed  •  replay-match  •  public/design/IP/experience gates PASS", {
    x:1.25, y:6.35, w:10.85, h:0.42, fontSize:17, bold:true, color:C.cyan, align:"center", margin:0,
  });
  addFooter(s, 7);
}

// 8 — close
{
  const s = pptx.addSlide();
  addBg(s);
  s.addShape(pptx.ShapeType.ellipse, { x:8.48, y:0.72, w:3.65, h:3.65, fill:{color:C.teal, transparency:32}, line:{color:C.cyan, transparency:20, width:2} });
  s.addShape(pptx.ShapeType.ellipse, { x:9.62, y:1.86, w:1.37, h:1.37, fill:{color:C.coral}, line:{color:C.white, transparency:70, width:1} });
  s.addText("観測したいのは、\nAIの正解ではない。", { x:0.78, y:0.88, w:7.0, h:1.2, fontSize:34, bold:true, color:C.white, margin:0 });
  s.addText("強大な能力と決定権を持つのに、\n誰が責任を負うのか分からない状態。", { x:0.78, y:2.46, w:7.25, h:1.05, fontSize:23, color:C.mist, margin:0 });
  card(s, 0.78, 4.18, 6.95, 1.27, C.ink2);
  s.addText("ghost-in-the-sim は、異議・反証・訂正可能性を\n消さずに危機を収束できるかを試す装置です。", { x:1.13, y:4.5, w:6.25, h:0.68, fontSize:18, bold:true, color:C.aqua, margin:0, align:"center" });
  s.addText("github.com/nexus-ai-2045/ghost-in-the-sim", { x:0.8, y:6.36, w:6.4, h:0.34, fontSize:13, color:C.cyan, margin:0 });
  s.addText("公式要件と公開境界は提出直前に人間レビュー", { x:7.15, y:6.36, w:5.38, h:0.34, fontSize:11, color:C.muted, align:"right", margin:0 });
  addFooter(s, 8);
}

const output = path.resolve(process.argv[2] || "artifacts/submission/submission-slides.pptx");
fs.mkdirSync(path.dirname(output), { recursive: true });
pptx.writeFile({ fileName: output });
