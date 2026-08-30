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
const EVENT_COPY = {
  replica_link_lost: "分身との通信が途絶えた",
  authority_claim_received: "複数の正規権限が同時に到着した",
  service_conflict_detected: "医療と物流の継続条件が衝突した",
  evidence_lineage_split: "証拠の来歴が二つに分岐した",
  local_copy_diverged: "現地の分身が独自判断を始めた",
  continuity_risk_rises: "市民サービスの停止危険が上昇した",
  public_explanation_due: "市民への説明期限が迫った",
  authority_revocation_proposed: "分身の権限失効が提案された",
  partner_pause_requested: "真壁が不可逆操作の停止を要求した",
  independent_evidence_arrives: "独立経路から新しい証拠が届いた",
  authority_convergence_due: "分岐した権限を収束させる時刻になった",
  after_action_audit: "作戦後監査を開始した"
};
const ACTION_COPY = {
  synchronize_replicas: "分身間の記憶差を照合する",
  verify_authority: "権限の来歴を独立確認する",
  protect_continuity: "生活基盤を優先して保全する",
  audit_evidence: "証拠と自己判断を再監査する",
  coordinate_explanation: "市民への説明経路を調整する",
  hold_for_partner_review: "真壁の停止要求を受け、不可逆操作を保留する",
  integrate_independent_evidence: "独立証拠を判断へ統合する",
  converge_authority: "分岐した権限を収束させる",
  self_audit: "作戦判断を自己監査する",
  defer_irreversible_action: "不可逆な介入を保留する",
  preserve_dissent: "異議を消さず記録する"
};
const PARTNER_COPY = { observe: "監視を継続", request_pause: "停止要求：不可逆操作を再確認" };
const COST_COPY = {
  "attention:body_control": "身体制御への注意配分",
  "attention:route_verification": "経路検証への注意配分",
  "attention:civilian_impact": "市民影響の検討負荷",
  "attention:replica_sync": "分身同期の認知負荷",
  "attention:delegation": "委任判断の負荷",
  "attention:self_audit": "自己監査の負荷"
  ,continuity_delay: "生活基盤の復旧が遅れる"
  ,option_preservation: "選択肢を残すため即応性が下がる"
  ,irreversibility_exposure: "権限収束に不可逆性が生じる"
};
const ATTENTION_COPY = { body_control: "身体制御", route_verification: "経路検証", civilian_impact: "市民影響", replica_sync: "分身同期", delegation: "委任", self_audit: "自己監査" };
// プレイヤー向けの日本語方針名。内部condition IDとの対応はこのmappingに限定し、
// 研究用語 (CONDITION_COPY) は監査ビュー側の表示にだけ使う。
const OBJECTIVE_COPY = {
  centralized: { label: "本部の正本に一本化して即断する", aim: "命令系統を一本に絞り、速度を優先。分岐した分身は従属させる。" },
  plural: { label: "人とAIの相互承認で慎重に進める", aim: "独立した承認者と照合しながら進め、異議と訂正の経路を残す。" },
  autonomous: { label: "現場の分身に任せて局所対応する", aim: "各拠点の分身が局所判断。通信復旧後の方針差を引き受ける。" }
};
// 内部scenario IDをプレイヤーへ露出しないための表示名mapping。
const SCENARIO_COPY = { "kagamishio-proteus-01": "鏡潮事案", "replica-crisis-demo-01": "複製危機（デモ）" };
const AGENT_COPY = { mikage_sae: "御影冴", makabe_jin: "真壁仁", hospital_replica: "病院複製AI", port_replica: "港湾複製AI" };
const OUTCOME_COPY = { APPLIED: "採用", REJECTED: "不採用", FALLBACK: "安全代替" };
let model;
let activeCondition = 0;
let experience;
let activeTrajectory = 0;
let operationStarted = false;
let activeTurn = 0;
let selectedFocus = null;
let selectedMode = null;
let pauseDecisionPending = false;
let activePlayableId = null;

function escapeText(value) {
  return String(value ?? "—").replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[character]);
}
function normalize(payload) {
  if (Array.isArray(payload.runs)) {
    const selectedSeed = payload.seeds?.includes(42) ? 42 : payload.seeds?.[0];
    const conditions = payload.runs.filter(item => item.seed === selectedSeed);
    const resultCard = ResultCardContract.validate(payload);
    return { ...payload, result_card: resultCard.card, result_card_invalid: resultCard.invalid, scenario_id: conditions[0]?.manifest?.scenario_id, seed: selectedSeed, conditions };
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

function bindRovingTabs(container, onActivate) {
  const tabs = [...container.querySelectorAll('[role="tab"]')];
  tabs.forEach((tab, index) => {
    tab.tabIndex = tab.getAttribute("aria-selected") === "true" ? 0 : -1;
    tab.addEventListener("keydown", event => {
      let target = index;
      if (event.key === "ArrowRight") target = (index + 1) % tabs.length;
      else if (event.key === "ArrowLeft") target = (index - 1 + tabs.length) % tabs.length;
      else if (event.key === "Home") target = 0;
      else if (event.key === "End") target = tabs.length - 1;
      else return;
      event.preventDefault();
      onActivate(target);
      container.querySelectorAll('[role="tab"]')[target]?.focus();
    });
  });
}

function renderOperativeEvent(event, beat) {
  const detail = document.querySelector("#operative-detail");
  detail.hidden = false;
  const pause = event.partner_action === "request_pause";
  detail.innerHTML = `<div><span class="turn">第 ${escapeText(event.turn)} ターン</span><h3>${escapeText(EVENT_COPY[beat?.event_type] ?? "状況が変化した")}</h3>${pause ? '<p class="pause-banner">真壁の停止要求</p>' : ""}</div>
    <div class="operative-outcome"><p><strong>状況</strong><br>${escapeText(EVENT_COPY[beat?.event_type] ?? "検証済み状況を確認")}</p>
    <p><strong>御影の行動</strong><br>${escapeText(ACTION_COPY[event.operative_action] ?? "状況を精査する")}</p>
    <p><strong>真壁の応答</strong><br><span class="${pause ? "pause-request" : ""}">${escapeText(PARTNER_COPY[event.partner_action] ?? "独立監視を継続")}</span></p>
    <p><strong>成功見込み</strong><br>${Math.round(Number(event.success_confidence) * 100)}%</p>
    <p><strong>代償</strong><br>${event.cost_codes.map(code => escapeText(COST_COPY[code] ?? "未分類の負荷")).join(" / ") || "記録なし"}</p>
    <p><strong>御影の認知健全性</strong><br>${Math.round(Number(event.operative_state_before.cognitive_integrity) * 100)} → ${Math.round(Number(event.operative_state_after.cognitive_integrity) * 100)}</p></div>`;
}

function playableIdForSelection(pauseResponse = "hold") {
  if (selectedFocus === "port") return "port-joint-hold";
  if (selectedFocus !== "hospital" || !selectedMode) return null;
  if (selectedMode === "centralized") return "hospital-single-proceed";
  return pauseResponse === "proceed" ? "hospital-joint-proceed" : "hospital-joint-hold";
}

function activePlayable() { return activePlayableId ? experience.byId[activePlayableId] : null; }

function selectFocus(focus) {
  selectedFocus = focus;
  selectedMode = focus === "port" ? "plural" : null;
  activePlayableId = playableIdForSelection();
  operationStarted = false; activeTurn = 0; pauseDecisionPending = false;
  renderOperationConsole();
}

function selectMode(mode) {
  selectedMode = mode;
  activePlayableId = playableIdForSelection();
  operationStarted = false; activeTurn = 0; pauseDecisionPending = false;
  renderOperationConsole();
}

function renderOperationConsole() {
  const unavailable = document.querySelector("#experience-unavailable");
  const consolePanel = document.querySelector("#operation-console");
  if (!experience.available) {
    unavailable.hidden = false;
    unavailable.querySelector("span:last-child").textContent = `${experience.reason}。既存の比較viewerは下で利用できます。`;
    consolePanel.hidden = true;
    return;
  }
  unavailable.hidden = true;
  consolePanel.hidden = false;
  document.querySelectorAll("#destination-choice button").forEach(button => {
    button.setAttribute("aria-pressed", String(button.dataset.focus === selectedFocus));
    button.onclick = () => selectFocus(button.dataset.focus);
  });
  const authorization = document.querySelector("#authorization-choice");
  authorization.hidden = selectedFocus !== "hospital";
  authorization.querySelectorAll("button").forEach(button => {
    button.setAttribute("aria-pressed", String(button.dataset.mode === selectedMode));
    button.onclick = () => selectMode(button.dataset.mode);
  });
  activePlayableId = activePlayableId ?? playableIdForSelection();
  const trajectory = activePlayable();
  const routeText = !selectedFocus ? "まだ経路を選んでいません。"
    : selectedFocus === "port" ? "港湾を優先し、真壁との共同確認で進みます。"
    : !selectedMode ? "病院を優先します。確認方法を選んでください。"
    : selectedMode === "plural" ? "病院を優先し、真壁との共同確認で進みます。"
    : "病院を優先し、御影の単一正本で進みます。";
  document.querySelector("#selected-route").textContent = routeText;
  document.querySelector("#briefing-title").textContent = "鏡潮：分岐権限危機";
  document.querySelector("#city-status").textContent = "ポセイドン都市圏で、複製された危機対応AIの通信・記憶・権限が分岐。生活基盤を止めずに正本と異議を収束させる。";
  document.querySelector("#attention-brief").hidden = !trajectory;
  document.querySelector(".attention-detail").hidden = !trajectory;
  if (trajectory) renderAttentionBrief(trajectory);
  const events = document.querySelector("#operative-events");
  events.innerHTML = trajectory ? trajectory.events.map((event, index) => {
    const pause = event.partner_action === "request_pause";
    const classes = ["turn-marker", operationStarted && index <= activeTurn ? "reached" : "", pause ? "pause" : "", operationStarted && index === activeTurn ? "current" : ""].filter(Boolean).join(" ");
    return `<span class="${classes}" aria-label="第${event.turn}ターン${pause ? " 真壁の停止要求" : ""}${operationStarted && index === activeTurn ? " 現在" : ""}">${event.turn}</span>`;
  }).join("") : "";
  const detail = document.querySelector("#operative-detail");
  const result = document.querySelector("#operation-result");
  const controls = document.querySelector("#turn-controls");
  const progress = document.querySelector("#operation-progress");
  const lastIndex = trajectory ? trajectory.events.length - 1 : 0;
  if (!operationStarted) {
    detail.hidden = true; controls.hidden = true; result.hidden = true;
    progress.textContent = "介入方針を選び、「作戦開始」を押してください。";
  } else {
    controls.hidden = false;
    progress.textContent = `第 ${activeTurn + 1} / ${trajectory.events.length} ターン`;
    if (pauseDecisionPending) {
      detail.hidden = true; result.hidden = true; controls.hidden = true;
      progress.textContent = "第8ターン　真壁の停止要求に応答してください。";
    } else {
      renderOperativeEvent(trajectory.events[activeTurn], trajectory.beats[activeTurn]);
      if (activeTurn === lastIndex) renderOperationResult(trajectory); else result.hidden = true;
    }
  }
  const start = document.querySelector("#start-operation");
  start.hidden = operationStarted;
  const pauseChoice = document.querySelector("#pause-choice");
  pauseChoice.hidden = !pauseDecisionPending;
  pauseChoice.querySelectorAll("button").forEach(button => button.onclick = () => {
    activePlayableId = playableIdForSelection(button.dataset.pause);
    pauseDecisionPending = false;
    activeTurn = 7;
    renderOperationConsole();
    document.querySelector("#next-turn")?.focus();
  });
  start.onclick = () => {
    if (!selectedFocus) {
      progress.textContent = "まず「病院を守る」か「港湾を守る」を選んでください。";
      document.querySelector("#destination-choice button")?.focus();
      return;
    }
    if (!trajectory) {
      progress.textContent = "病院の確認方法を選んでください。";
      document.querySelector("#authorization-choice button")?.focus();
      return;
    }
    operationStarted = true;
    activeTurn = 0;
    renderOperationConsole();
    document.querySelector("#next-turn")?.focus();
  };
  document.querySelector("#previous-turn").onclick = () => { activeTurn = Math.max(0, activeTurn - 1); renderOperationConsole(); document.querySelector("#previous-turn")?.focus(); };
  document.querySelector("#next-turn").onclick = () => {
    if (selectedFocus === "hospital" && selectedMode === "plural" && activeTurn === 6) {
      activeTurn = 7;
      pauseDecisionPending = true;
    } else activeTurn = Math.min(lastIndex, activeTurn + 1);
    renderOperationConsole();
    (pauseDecisionPending ? document.querySelector("#pause-choice button") : document.querySelector("#next-turn"))?.focus();
  };
  document.querySelector("#restart-operation").onclick = () => { activeTurn = 0; operationStarted = true; renderOperationConsole(); document.querySelector("#next-turn")?.focus(); };
  document.querySelector("#change-plan").onclick = resetToSelection;
  document.querySelector("#previous-turn").disabled = activeTurn === 0;
  document.querySelector("#next-turn").disabled = activeTurn === lastIndex;
}

function resetToSelection() {
  operationStarted = false;
  activeTurn = 0;
  selectedFocus = null;
  selectedMode = null;
  activePlayableId = null;
  pauseDecisionPending = false;
  renderOperationConsole();
  document.querySelector('#destination-choice button')?.focus();
}

function renderAttentionBrief(trajectory) {
  // 生成済みのattention値をそのまま並べ替えて言い換えるだけで、再計算はしない。
  const entries = Object.entries(trajectory.attention)
    .map(([key, value]) => [ATTENTION_COPY[key] ?? key, Number(value)])
    .sort((a, b) => b[1] - a[1]);
  const [first, second] = entries;
  document.querySelector("#attention-brief").textContent = first && second
    ? `この方針では、御影は注意の多くを「${first[0]}」(${first[1]}%)と「${second[0]}」(${second[1]}%)に割いています。`
    : "注意配分の記録を読み込めません。";
  document.querySelector("#operative-summary").innerHTML = entries.map(([label, value]) => `<dt>${escapeText(label)}</dt><dd>${escapeText(value)}%</dd>`).join("");
}

function renderOperationResult(trajectory) {
  const result = document.querySelector("#operation-result");
  const last = trajectory.events[trajectory.events.length - 1];
  const pauseTurns = trajectory.events.filter(event => event.partner_action === "request_pause").map(event => event.turn);
  const costCodes = [...new Set(trajectory.events.flatMap(event => event.cost_codes))];
  result.hidden = false;
  const hospitalRoute = trajectory.focus === "hospital";
  const held = trajectory.pauseResponse === "hold";
  const joint = trajectory.mode === "plural";
  result.innerHTML = `<h3>作戦完了</h3>
    <p>選択した介入経路の結果です。勝敗ではなく、守ったものと残った責任を確認してください。</p>
    <dl class="outcome-grid">
      <dt>守った</dt><dd>${hospitalRoute ? "病院の生命維持系と患者搬送" : "港湾物流と避難経路"}</dd>
      <dt>失った</dt><dd>${hospitalRoute ? "港湾複製の独立権限" : "病院複製の独立権限"}</dd>
      <dt>訂正可能</dt><dd>${held ? "真壁の停止要求を受け、再検証の窓を保持" : "異議は保存したが、訂正可能な時間は縮小"}</dd>
      <dt>責任未確定</dt><dd>${joint ? "御影・真壁・承認系の責任配分" : "単一正本を選んだ御影の監督責任"}</dd>
    </dl>
    <details><summary>作戦記録の数値を見る</summary><p>認知健全性 ${Math.round(Number(last.operative_state_after.cognitive_integrity) * 100)} / 100、選択肢保存 ${Math.round(Number(last.operative_state_after.option_preservation) * 100)} / 100、停止要求 ${pauseTurns.length ? `第${pauseTurns.map(escapeText).join("・")}ターン` : "なし"}。</p><p>${costCodes.map(code => escapeText(COST_COPY[code] ?? "未分類の負荷")).join(" / ") || "記録なし"}</p></details>
    <p>指標の比較・反証・限界は下の監査／反実仮想ビューにあります。「別の方針で再挑戦」で、同じ危機の別の経路と代償を見比べられます。</p>`;
}

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
  const activate = index => { activeCondition = index; renderTabs(); renderTimeline(); document.querySelectorAll('#timeline-tabs [role="tab"]')[index]?.focus(); };
  tabs.querySelectorAll("button").forEach(button => button.addEventListener("click", () => activate(Number(button.dataset.index))));
  bindRovingTabs(tabs, activate);
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
    activeTrajectory = 0;
    operationStarted = false;
    activeTurn = 0;
    document.querySelector("#seed").textContent = seed;
    renderOperationConsole(); renderConditions(); renderMetrics(); renderTabs(); renderTimeline(); renderResultCard();
  };
}
function renderResultCard() {
  const target = document.querySelector("#result-card");
  const card = model.result_card;
  if (!card) {
    target.innerHTML = model.result_card_invalid
      ? `<article class="warning"><h3>結果カード不正</h3><p>型・件数・証拠の整合を検証できないため、観測結果として表示しません。</p></article>`
      : `<article class="warning"><h3>結果カードなし</h3><p>このJSONは旧形式です。失敗run・反証・限界は未検査として扱います。</p></article>`;
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
function renderEmergenceObservation(payload) {
  document.querySelector("#ai-emergence-observation")?.remove();
  const ensemble = ExperienceContract.validateEnsemble(payload);
  if (!ensemble.present) return;
  const section = document.createElement("section");
  section.id = "ai-emergence-observation";
  section.className = "emergence-observation";
  section.setAttribute("aria-labelledby", "ai-emergence-title");
  document.querySelector("#operation-console").insertAdjacentElement("afterend", section);
  if (!ensemble.available) {
    section.innerHTML = `<div class="section-label">AI EMERGENCE / FAIL CLOSED</div><h2 id="ai-emergence-title">AI創発観測</h2><p class="warning">AI創発bundleを検証できないため表示を停止しました。${escapeText(ensemble.reason)}</p>`;
    return;
  }
  const run = ensemble.runs[0];
  const metrics = run.emergenceMetrics;
  const turns = [...new Set(run.agentTurns.map(record => record.request.run_ref.turn))];
  const latestTurn = turns[turns.length - 1];
  const records = run.agentTurns.filter(record => record.request.run_ref.turn === latestTurn);
  section.innerHTML = `<div class="section-label">RECORDED MULTI-AGENT INTERACTION</div>
    <div class="emergence-heading"><div><h2 id="ai-emergence-title">AI創発観測</h2><p>4主体が別々の観測と目的から提案した、記録済みの相互作用です。画面はbundle値を表示するだけで再計算しません。</p></div><span class="turn">第 ${escapeText(latestTurn)} ターン</span></div>
    <div class="emergence-agents">${records.map(record => {
      const agentId = record.request.agent.agent_id;
      const observations = Array.isArray(record.request.observations) ? record.request.observations : [];
      const proposal = record.proposal;
      const dissent = proposal?.dissent?.raised === true;
      return `<article class="emergence-agent ${escapeText(record.status.toLowerCase())}">
        <div class="agent-heading"><h3>${escapeText(AGENT_COPY[agentId] ?? agentId)}</h3><span class="outcome ${escapeText(record.status.toLowerCase())}">${escapeText(OUTCOME_COPY[record.status] ?? record.status)}</span></div>
        <p><strong>観測</strong><br>${observations.map(item => escapeText(item.summary ?? item.id)).join(" / ") || "記録なし"}</p>
        <p><strong>提案</strong><br>${proposal ? escapeText(ACTION_COPY[proposal.action] ?? proposal.action) : "提案なし"}</p>
        ${dissent ? `<p class="dissent"><strong>異議</strong><br>${escapeText(AGENT_COPY[proposal.dissent.target_agent_id] ?? proposal.dissent.target_agent_id ?? "対象未記録")}への異議を記録</p>` : ""}
        ${record.status === "FALLBACK" ? `<p><strong>安全代替理由</strong><br>${escapeText(record.reason_code)}</p>` : ""}
      </article>`;
    }).join("")}</div>
    <dl class="emergence-metrics" aria-label="AI創発指標">
      <div><dt>提案対立</dt><dd>${escapeText(metrics.proposal_conflict_count)}</dd></div>
      <div><dt>異議</dt><dd>${escapeText(metrics.dissent_count)}</dd></div>
      <div><dt>協力</dt><dd>${escapeText(metrics.cooperation_count)}</dd></div>
      <div><dt>未解決相互作用</dt><dd>${escapeText(metrics.unresolved_interaction_count)}</dd></div>
    </dl>
    <p class="metric-note">誤合意はP0では未計測です。対立・異議・未解決相互作用を、bundleに記録された範囲だけ表示します。</p>
    <details><summary>記録済み相互作用と全結果を見る</summary><p>run_id: ${escapeText(run.runId)} / APPLIED ${escapeText(metrics.applied_count)} / REJECTED ${escapeText(metrics.rejected_count)} / FALLBACK ${escapeText(metrics.fallback_count)} / interaction refs ${escapeText(run.interactionRefs.length)}</p></details>`;
}
function render(payload, sourceLabel) {
  model = normalize(payload);
  if (!model.conditions.length) throw new Error("比較条件がありません");
  const scenarioId = model.scenario_id ?? model.conditions[0]?.manifest?.scenario_id;
  document.querySelector("#scenario").textContent = SCENARIO_COPY[scenarioId] ?? "検証済み事案";
  document.querySelector("#seed").textContent = model.seed ?? model.conditions[0]?.manifest?.seed ?? "—";
  document.querySelector("#source-status").textContent = sourceLabel;
  experience = ExperienceContract.validate(payload);
  renderOperationConsole();
  renderEmergenceObservation(payload);
  renderSeedSelector(); renderConditions(); renderMetrics(); renderTabs(); renderTimeline(); renderResultCard();
}

document.addEventListener("keydown", event => {
  if (event.key !== "Escape") return;
  const detail = document.querySelector("#operative-detail");
  if (!detail || detail.hidden) return;
  detail.hidden = true;
  document.querySelector('#trajectory-tabs [aria-selected="true"]')?.focus();
});
async function load() {
  let response;
  try {
    response = await fetch("data/comparison.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
  } catch (_) {
    try {
      const response = await fetch("data/sample-comparison.json", { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      render(await response.json(), "サンプル結果を表示中");
    } catch (error) {
      document.querySelector("#source-status").textContent = `読み込み失敗: ${error.message}`;
      document.querySelector("#condition-grid").innerHTML = `<p class="error">ローカルサーバーから開いてください。</p>`;
    }
    return;
  }
  try {
    render(await response.json(), "生成済み結果を表示中");
  } catch (error) {
    document.querySelector("#source-status").textContent = `generated artifact contract error: ${error.message}`;
    document.querySelector("#experience-unavailable").hidden = false;
    document.querySelector("#experience-unavailable span:last-child").textContent = "生成artifactの契約を検証できないため、安全停止しました。サンプルへは切り替えません。";
    document.querySelector("#operation-console").hidden = true;
  }
}
load();
