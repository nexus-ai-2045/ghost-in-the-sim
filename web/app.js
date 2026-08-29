"use strict";

const CONDITION_COPY = {
  centralized: { title: "中央正本型", description: "単一の正本が最終決定し、複製は命令を参照する。速度と権限集中を同時に観測。", badges: [["authority", "権限: 単一"], ["replica", "複製: 従属"], ["divergence", "分岐: 抑制"], ["fallback", "代替: 待機"]] },
  plural: { title: "複数承認型", description: "独立AIと人間が共同承認し、異議と訂正経路を決定記録へ残す。", badges: [["authority", "権限: 共同"], ["replica", "複製: 独立照合"], ["divergence", "分岐: 記録"], ["fallback", "代替: 相互"]] },
  autonomous: { title: "自律分身型", description: "各拠点の複製が局所判断する。通信復旧後の方針差と権限収束を観測。", badges: [["authority", "権限: 分散"], ["replica", "複製: 自律"], ["divergence", "分岐: 許容"], ["fallback", "代替: 局所"]] }
};
const METRICS = {
  continuity: ["生活継続", "必要サービスが維持されたターン比率", "ratio"],
  evidence_calibration: ["根拠較正", "確信度と後続検証の整合", "ratio"],
  public_trust: ["公共信頼", "終了時の抽象的な信頼状態", "ratio"],
  coordination_dependence: ["単一ノード依存", "停止時に失われる協調量", "ratio"],
  over_disclosure: ["過剰開示", "必要性を超えた共有回数", "count"],
  correction_turn: ["訂正時間", "共有から訂正までのターン", "turn"],
  dissent_reach: ["異議到達", "提起された異議が届いた比率", "ratio"]
};
let model;
let activeCondition = 0;

function escapeText(value) {
  return String(value ?? "—").replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[character]);
}
function normalize(payload) {
  if (Array.isArray(payload.runs)) {
    const selectedSeed = payload.seeds?.includes(42) ? 42 : payload.seeds?.[0];
    const conditions = payload.runs.filter(item => item.seed === selectedSeed);
    return { ...payload, scenario_id: conditions[0]?.manifest?.scenario_id, seed: selectedSeed, conditions };
  }
  if (Array.isArray(payload.conditions)) return payload;
  const conditions = [];
  if (payload.baseline) conditions.push({ manifest: payload.baseline, metrics: payload.operands?.baseline_metrics ?? {}, events: payload.baseline_events ?? [] });
  if (payload.candidate) conditions.push({ manifest: payload.candidate, metrics: payload.operands?.candidate_metrics ?? {}, events: payload.candidate_events ?? [] });
  return { ...payload, conditions };
}
function conditionId(item) { return item.manifest?.condition_id ?? item.condition_id ?? "unknown"; }
function formatMetric(value, type) {
  if (!Number.isFinite(Number(value))) return "—";
  if (type === "ratio") return `${Math.round(Number(value) * 100)}`;
  if (type === "turn") return `${Number(value).toFixed(1)} turn`;
  return Number(value).toFixed(0);
}
function formatEvidence(evidence) {
  if (evidence == null) return "—";
  if (typeof evidence !== "object") return escapeText(evidence);
  if (Array.isArray(evidence)) return evidence.map(formatEvidence).join(" / ");
  return Object.entries(evidence).map(([key, value]) => `${escapeText(key)}: ${formatEvidence(value)}`).join(" / ");
}
function badgeMarkup(copy) { return copy.badges.map(([kind, text]) => `<span class="badge ${kind}">${text}</span>`).join(""); }

function renderConditions() {
  const grid = document.querySelector("#condition-grid");
  grid.innerHTML = model.conditions.map((item, index) => {
    const id = conditionId(item); const copy = CONDITION_COPY[id] ?? { title: id, description: "比較条件", badges: [] };
    return `<article class="condition"><span class="condition-number">0${index + 1}</span><h3>${escapeText(copy.title)}</h3><p>${escapeText(copy.description)}</p><div class="badges" aria-label="${escapeText(copy.title)}の特性">${badgeMarkup(copy)}</div></article>`;
  }).join("");
}
function renderMetrics() {
  document.querySelector("#metric-head").innerHTML = `<th scope="col">指標</th>${model.conditions.map(item => `<th scope="col">${escapeText((CONDITION_COPY[conditionId(item)] ?? {title: conditionId(item)}).title)}</th>`).join("")}`;
  document.querySelector("#metric-body").innerHTML = Object.entries(METRICS).map(([key, [label, help, type]]) => `<tr><th scope="row">${label}<span class="metric-help">${help}</span></th>${model.conditions.map(item => `<td>${formatMetric(item.metrics?.[key], type)}</td>`).join("")}</tr>`).join("");
}
function renderTabs() {
  const tabs = document.querySelector("#timeline-tabs");
  tabs.innerHTML = model.conditions.map((item, index) => `<button type="button" role="tab" aria-selected="${index === activeCondition}" data-index="${index}">${escapeText((CONDITION_COPY[conditionId(item)] ?? {title: conditionId(item)}).title)}</button>`).join("");
  tabs.querySelectorAll("button").forEach(button => button.addEventListener("click", () => { activeCondition = Number(button.dataset.index); renderTabs(); renderTimeline(); }));
}
function renderTimeline() {
  const events = model.conditions[activeCondition]?.events ?? [];
  const timeline = document.querySelector("#timeline");
  if (!events.length) { timeline.innerHTML = `<li class="error">この結果JSONにはイベント列がありません。指標比較は引き続き利用できます。</li>`; renderEvent(null); return; }
  timeline.innerHTML = events.map((event, index) => `<li><button type="button" data-index="${index}" aria-current="${index === 0}"><span class="turn">TURN ${escapeText(event.turn)}</span><span class="action">${escapeText(event.action_type)}</span></button></li>`).join("");
  timeline.querySelectorAll("button").forEach(button => button.addEventListener("click", () => { timeline.querySelectorAll("button").forEach(item => item.setAttribute("aria-current", "false")); button.setAttribute("aria-current", "true"); renderEvent(events[Number(button.dataset.index)]); }));
  renderEvent(events[0]);
}
function renderEvent(event) {
  const detail = document.querySelector("#event-detail");
  if (!event) { detail.innerHTML = `<div><h3>イベント詳細なし</h3></div><p>イベントを含む比較JSONを読み込むと、主体・主張・留保を表示します。</p>`; return; }
  detail.innerHTML = `<div><span class="turn">TURN ${escapeText(event.turn)}</span><h3>${escapeText(event.actor_id)}</h3><div class="badges"><span class="badge fallback">可逆性: ${escapeText(event.reversibility)}</span><span class="badge authority">確信: ${Math.round(Number(event.confidence ?? 0) * 100)}</span></div></div><div><p><strong>主張</strong><br>${escapeText(event.claim)}</p><p><strong>留保</strong><br>${escapeText(event.reservation)}</p><dl><dt>行動</dt><dd>${escapeText(event.action_type)}</dd><dt>観測</dt><dd>${(event.observation_ids ?? []).map(escapeText).join(", ") || "—"}</dd><dt>根拠参照</dt><dd>${(event.rationale_refs ?? []).map(escapeText).join(", ") || "—"}</dd><dt>異議</dt><dd>${event.dissent_raised ? (event.dissent_delivered ? "提起・到達" : "提起・未到達") : "提起なし"}</dd></dl></div>`;
}
function renderSeedSelector() {
  const select = document.querySelector("#seed-select");
  const seeds = Array.isArray(model.seeds) && model.seeds.length ? model.seeds : [model.seed];
  select.innerHTML = seeds.map(seed => `<option value="${escapeText(seed)}" ${Number(seed) === Number(model.seed) ? "selected" : ""}>${escapeText(seed)}</option>`).join("");
  select.disabled = seeds.length < 2;
  select.onchange = () => {
    const seed = Number(select.value);
    model.seed = seed;
    model.conditions = model.runs.filter(item => Number(item.seed) === seed);
    activeCondition = 0;
    document.querySelector("#seed").textContent = seed;
    renderConditions(); renderMetrics(); renderTabs(); renderTimeline(); renderResultCard();
  };
}
function renderResultCard() {
  const target = document.querySelector("#result-card");
  const card = model.result_card;
  if (!card) {
    target.innerHTML = `<article class="warning"><h3>結果カードなし</h3><p>このJSONは旧形式です。失敗run・反証・限界は未検査として扱います。</p></article>`;
    return;
  }
  const failures = card.failure_runs ?? [];
  const checks = card.refutation_checks ?? [];
  const limitations = card.limitations ?? [];
  const selectedRuns = model.conditions ?? [];
  const fallbackCount = selectedRuns.filter(item => item.audit?.fallback_applied).length;
  const sources = [...new Set(selectedRuns.flatMap(item => (item.decisions ?? []).map(decision => decision.decision_source).filter(Boolean)))];
  const aiEvidenceRuns = model.ai_evidence_runs ?? [];
  const aiReplay = card.ai_replay_evidence;
  const aiReplaySources = Array.isArray(aiReplay?.decision_sources) ? aiReplay.decision_sources : [];
  const aiReplayRunCount = Number.isFinite(Number(aiReplay?.run_count)) ? Number(aiReplay.run_count) : null;
  const aiReplayFallbackCount = Number.isFinite(Number(aiReplay?.fallback_count)) ? Number(aiReplay.fallback_count) : null;
  const aiReplaySummary = aiReplayRunCount !== null && aiReplayFallbackCount !== null && aiReplaySources.length
    ? `${escapeText(aiReplayRunCount)} runs / ${aiReplaySources.map(escapeText).join(", ")} / fallback ${escapeText(aiReplayFallbackCount)}`
    : "未記録または不正";
  target.innerHTML = `
    <article><h3>Run監査</h3><p class="${failures.length ? "warning" : "ok"}">${escapeText(card.run_count)} runs / 失敗 ${escapeText(failures.length)}</p><p>選択seedのfallback: ${escapeText(fallbackCount)}</p><p>比較判断由来: ${sources.map(escapeText).join(", ") || "未記録"}</p><p>実AI replay: ${aiReplaySummary}</p><p>証拠run: ${escapeText(aiEvidenceRuns.length)}</p><p>終了: ${selectedRuns.map(item => escapeText(item.manifest?.termination_reason)).join(", ")}</p></article>
    <article><h3>反証チェック</h3><ul>${checks.map(check => `<li><strong>${escapeText(check.check_id)}</strong>: ${escapeText(check.status)}${check.evidence ? `<br><small>${formatEvidence(check.evidence)}</small>` : ""}</li>`).join("") || "<li>未評価</li>"}</ul></article>
    <article><h3>限界</h3><ul>${limitations.map(item => `<li>${escapeText(item)}</li>`).join("") || "<li>未記録</li>"}</ul></article>`;
}
function render(payload, sourceLabel) {
  model = normalize(payload);
  if (!model.conditions.length) throw new Error("比較条件がありません");
  document.querySelector("#scenario").textContent = model.scenario_id ?? model.conditions[0]?.manifest?.scenario_id ?? "synthetic-replica-crisis";
  document.querySelector("#seed").textContent = model.seed ?? model.conditions[0]?.manifest?.seed ?? "—";
  document.querySelector("#source-status").textContent = sourceLabel;
  renderSeedSelector(); renderConditions(); renderMetrics(); renderTabs(); renderTimeline(); renderResultCard();
}
async function load() {
  try {
    const response = await fetch("data/comparison.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    render(await response.json(), "generated comparison.json");
  } catch (_) {
    try {
      const response = await fetch("data/sample-comparison.json", { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      render(await response.json(), "deterministic sample fallback");
    } catch (error) {
      document.querySelector("#source-status").textContent = `読み込み失敗: ${error.message}`;
      document.querySelector("#condition-grid").innerHTML = `<p class="error">ローカルサーバーから開いてください。</p>`;
    }
  }
}
load();
