"use strict";

(function exposeExperienceContract(root) {
  const REQUIRED_EVENT_FIELDS = [
    "turn", "scenario_beat_id", "operative_action", "partner_action",
    "success_confidence", "cost_codes", "operative_state_before", "operative_state_after"
  ];
  const PLAYABLE_IDS = Object.freeze([
    "hospital-joint-hold",
    "port-joint-hold",
    "hospital-joint-proceed",
    "hospital-single-proceed",
  ]);
  const PLAYABLE_EXPECTATIONS = Object.freeze({
    "hospital-joint-hold": ["hospital", "plural", "hold"],
    "port-joint-hold": ["port", "plural", "hold"],
    "hospital-joint-proceed": ["hospital", "plural", "proceed"],
    "hospital-single-proceed": ["hospital", "centralized", "proceed"],
  });
  const AGENT_IDS = Object.freeze(["mikage_sae", "makabe_jin", "hospital_replica", "port_replica"]);
  const OUTCOME_STATUSES = new Set(["APPLIED", "REJECTED", "FALLBACK"]);

  function object(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value);
  }

  function unavailable(reason) {
    return { available: false, reason, trajectories: [] };
  }

  function validateBundle(bundle) {
    if (!object(bundle) || bundle.schema_version !== "meta-security-run-bundle/v1") return null;
    const runId = bundle.run_id;
    const request = bundle.run_request;
    const stream = bundle.event_stream;
    const replay = bundle.replay;
    const evidence = bundle.evidence;
    if (typeof runId !== "string" || !runId) return null;
    if (![request, stream, replay, evidence].every(section => object(section) && section.run_id === runId)) return null;
    if (evidence.verification !== "replay-match" || stream.ordering !== "turn-ascending/v1") return null;
    if (!object(request.scenario) || !Array.isArray(request.scenario.beats) || !object(request.operative_plan) || !object(request.operative_plan.attention)) return null;
    const attentionValues = Object.values(request.operative_plan.attention).map(Number);
    const attentionBudget = attentionValues.reduce((total, value) => total + value, 0);
    if (!Number.isInteger(request.seed) || attentionValues.some(value => !Number.isFinite(value)) || attentionBudget !== 100) return null;
    if (!Array.isArray(stream.events) || stream.events.length !== 12 || request.scenario.beats.length !== 12) return null;
    const events = stream.events;
    for (let index = 0; index < events.length; index += 1) {
      const event = events[index];
      if (!object(event) || event.run_id !== runId || event.seed !== request.seed) return null;
      if (event.turn !== index + 1 || REQUIRED_EVENT_FIELDS.some(field => !(field in event))) return null;
      if (!Array.isArray(event.cost_codes) || !object(event.operative_state_before) || !object(event.operative_state_after)) return null;
      if (request.scenario.beats[index]?.beat_id !== event.scenario_beat_id) return null;
      if (![event.operative_state_before, event.operative_state_after].every(state => Number.isFinite(Number(state.cognitive_integrity)) && Number.isFinite(Number(state.option_preservation)))) return null;
      const confidence = Number(event.success_confidence);
      if (!Number.isFinite(confidence) || confidence < 0 || confidence > 1) return null;
    }
    return {
      runId,
      seed: request.seed,
      conditionId: request.requested_mode,
      scenarioId: request.scenario.scenario_id,
      attentionBudget,
      attention: request.operative_plan.attention,
      beats: request.scenario.beats,
      events,
    };
  }

  function validate(payload) {
    if (!object(payload)) return unavailable("artifactがobjectではありません");
    const capability = payload.experience_capability;
    if (!object(capability)
      || capability.schema_version !== "ghost-in-the-sim-experience/v1"
      || capability.renderer_mode !== "artifact-only"
      || capability.operation_console !== true) {
      return unavailable("検証済みの操作体験capabilityがありません");
    }
    if (!Array.isArray(payload.playable_trajectories)) {
      return unavailable("プレイ用trajectoryがありません");
    }
    const entries = payload.playable_trajectories;
    if (entries.length !== PLAYABLE_IDS.length) return unavailable("プレイ用trajectoryの件数が不正です");
    const ids = entries.map(entry => entry?.trajectory_id);
    if (new Set(ids).size !== PLAYABLE_IDS.length || PLAYABLE_IDS.some(id => !ids.includes(id))) {
      return unavailable("プレイ用trajectory IDを検証できません");
    }
    const byId = {};
    const runIds = new Set();
    for (const entry of entries) {
      const trajectory = validateBundle(entry?.bundle);
      if (!trajectory) return unavailable("プレイ用bundleのrun_id・replay・event順序を検証できません");
      if (trajectory.seed !== 42 || runIds.has(trajectory.runId)) return unavailable("プレイ用runのseedまたはrun_idが不正です");
      runIds.add(trajectory.runId);
      const plan = entry.bundle.run_request.operative_plan;
      const [focus, mode, response] = PLAYABLE_EXPECTATIONS[entry.trajectory_id];
      if (plan.focus !== focus || trajectory.conditionId !== mode || plan.pause_response !== response) {
        return unavailable("プレイ用trajectoryの選択契約が不正です");
      }
      trajectory.trajectoryId = entry.trajectory_id;
      trajectory.focus = focus;
      trajectory.pauseResponse = response;
      trajectory.mode = mode;
      byId[entry.trajectory_id] = trajectory;
    }
    const comparablePrefix = trajectory => JSON.stringify(trajectory.events.slice(0, 7).map(event => {
      const { run_id: _runId, ...comparable } = event;
      return comparable;
    }));
    const holdPrefix = comparablePrefix(byId["hospital-joint-hold"]);
    const proceedPrefix = comparablePrefix(byId["hospital-joint-proceed"]);
    if (holdPrefix !== proceedPrefix) return unavailable("真壁判断前の履歴が一致しないため、安全に分岐できません");
    return { available: true, reason: "", trajectories: PLAYABLE_IDS.map(id => byId[id]), byId };
  }

  function validateEnsemble(payload) {
    if (!object(payload) || !("ensemble_runs" in payload)) {
      return { present: false, available: false, reason: "", runs: [] };
    }
    if (!Array.isArray(payload.ensemble_runs) || payload.ensemble_runs.length === 0) {
      return { present: true, available: false, reason: "AI創発runが空または配列ではありません", runs: [] };
    }
    const runs = [];
    const runIds = new Set();
    for (const bundle of payload.ensemble_runs) {
      const base = validateBundle(bundle);
      const replay = bundle?.replay;
      if (!base || !object(replay)
        || replay.protocol_version !== "ghost-agent-turn/v1"
        || replay.trajectory_class !== "recorded-agent-turns") {
        return { present: true, available: false, reason: "AI創発bundleの基礎契約を検証できません", runs: [] };
      }
      if (runIds.has(base.runId)) return { present: true, available: false, reason: "AI創発run_idが重複しています", runs: [] };
      runIds.add(base.runId);
      if (!Array.isArray(replay.agent_turns) || replay.agent_turns.length === 0
        || !Array.isArray(replay.interaction_refs) || !object(replay.emergence_metrics)) {
        return { present: true, available: false, reason: "AI創発のturn・interaction・指標が不足しています", runs: [] };
      }
      const seen = new Set();
      for (const record of replay.agent_turns) {
        const request = record?.request;
        const runRef = request?.run_ref;
        const agentId = request?.agent?.agent_id;
        if (!object(record) || !object(request) || !object(runRef)
          || runRef.environment_seed !== base.seed || runRef.scenario_id !== base.scenarioId
          || !Number.isInteger(runRef.turn) || runRef.turn < 1 || runRef.round !== 1
          || !AGENT_IDS.includes(agentId) || !OUTCOME_STATUSES.has(record.status)) {
          return { present: true, available: false, reason: "AI主体のrequestまたは結果状態が不正です", runs: [] };
        }
        const key = `${runRef.turn}:${agentId}`;
        if (seen.has(key)) return { present: true, available: false, reason: "同一turnのAI主体が重複しています", runs: [] };
        seen.add(key);
        if (record.status === "FALLBACK" && (typeof record.reason_code !== "string" || !record.reason_code)) {
          return { present: true, available: false, reason: "FALLBACKの理由がありません", runs: [] };
        }
        if (record.status !== "FALLBACK" && (!object(record.proposal) || record.proposal.agent_id !== agentId)) {
          return { present: true, available: false, reason: "AI提案と主体を照合できません", runs: [] };
        }
      }
      const metrics = replay.emergence_metrics;
      const requiredMetrics = ["validated_proposal_count", "applied_count", "rejected_count", "fallback_count", "proposal_conflict_count", "dissent_count", "cooperation_count", "unresolved_interaction_count"];
      if (requiredMetrics.some(key => !Number.isInteger(metrics[key]) || metrics[key] < 0)
        || ("false_consensus_count" in metrics && (!Number.isInteger(metrics.false_consensus_count) || metrics.false_consensus_count < 0))
        || metrics.applied_count + metrics.rejected_count + metrics.fallback_count !== replay.agent_turns.length) {
        return { present: true, available: false, reason: "AI創発指標を検証できません", runs: [] };
      }
      runs.push({ ...base, agentTurns: replay.agent_turns, interactionRefs: replay.interaction_refs, emergenceMetrics: metrics });
    }
    return { present: true, available: true, reason: "", runs };
  }

  root.ExperienceContract = Object.freeze({ validate, validateEnsemble });
})(globalThis);
