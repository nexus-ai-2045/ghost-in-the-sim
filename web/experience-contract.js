"use strict";

(function exposeExperienceContract(root) {
  const REQUIRED_EVENT_FIELDS = [
    "turn", "scenario_beat_id", "operative_action", "partner_action",
    "success_confidence", "cost_codes", "operative_state_before", "operative_state_after"
  ];

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
    if (!Array.isArray(payload.trajectories) || !payload.trajectories.length) {
      return unavailable("検証済みtrajectoryがありません");
    }
    const trajectories = payload.trajectories.map(validateBundle);
    if (trajectories.some(item => item === null)) {
      return unavailable("trajectoryのrun_id・replay・event順序を検証できません");
    }
    return { available: true, reason: "", trajectories, trajectory: trajectories[0] };
  }

  root.ExperienceContract = Object.freeze({ validate });
})(globalThis);
