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

  root.ExperienceContract = Object.freeze({ validate });
})(globalThis);
