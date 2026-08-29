"use strict";

(function expose(root, factory) {
  const contract = factory();
  if (typeof module === "object" && module.exports) module.exports = contract;
  if (root) root.ResultCardContract = contract;
})(typeof globalThis === "object" ? globalThis : this, function buildContract() {
  const STATUSES = new Set(["triggered", "not_triggered", "not_observable"]);
  const nonNegativeInteger = value => Number.isInteger(value) && value >= 0;
  const object = value => value !== null && typeof value === "object" && !Array.isArray(value);
  const runCard = value => object(value)
    && typeof value.run_id === "string" && value.run_id.length > 0
    && typeof value.mode === "string" && typeof value.effective_mode === "string"
    && Number.isInteger(value.seed) && typeof value.failed_run === "boolean"
    && Array.isArray(value.failure_reasons) && value.failure_reasons.every(item => typeof item === "string")
    && nonNegativeInteger(value.completed_turns) && nonNegativeInteger(value.turn_limit);
  const rawRun = value => object(value) && Number.isInteger(value.seed)
    && typeof value.requested_mode === "string" && typeof value.effective_mode === "string"
    && object(value.audit) && typeof value.audit.fallback_applied === "boolean"
    && object(value.manifest) && object(value.metrics)
    && Array.isArray(value.decisions) && Array.isArray(value.events);

  function validate(payload) {
    const card = payload?.result_card;
    if (card == null) return { card: null, invalid: false };
    const runs = payload.runs;
    const cardRuns = card.runs;
    const failures = card.failure_runs;
    const checks = card.refutation_checks;
    const limitations = card.limitations;
    let valid = object(card) && card.schema_version === "result-card-v1"
      && typeof payload.artifact_revision === "string" && payload.artifact_revision.length === 16
      && card.artifact_revision === payload.artifact_revision
      && nonNegativeInteger(card.run_count) && Array.isArray(runs) && card.run_count === runs.length && runs.every(rawRun)
      && Array.isArray(cardRuns) && cardRuns.length === card.run_count && cardRuns.every(runCard)
      && Array.isArray(failures) && failures.every(runCard)
      && Array.isArray(checks) && checks.every(item => object(item) && typeof item.check_id === "string" && STATUSES.has(item.status) && object(item.evidence))
      && Array.isArray(limitations) && limitations.every(item => typeof item === "string");
    if (valid) {
      const expected = cardRuns.filter(item => item.failed_run).map(item => item.run_id).sort();
      const actual = failures.map(item => item.run_id).sort();
      valid = JSON.stringify(expected) === JSON.stringify(actual);
    }
    const evidenceRuns = payload.ai_evidence_runs;
    const replay = card.ai_replay_evidence;
    const replayAbsent = evidenceRuns === undefined && replay === undefined;
    const replayValid = Array.isArray(evidenceRuns) && evidenceRuns.every(rawRun) && object(replay)
      && nonNegativeInteger(replay.run_count) && replay.run_count === evidenceRuns.length
      && nonNegativeInteger(replay.fallback_count) && replay.fallback_count <= replay.run_count
      && Array.isArray(replay.decision_sources) && replay.decision_sources.length > 0
      && replay.decision_sources.every(item => typeof item === "string" && item.length > 0);
    valid = valid && (replayAbsent || replayValid);
    return valid ? { card, invalid: false } : { card: null, invalid: true };
  }

  return { validate };
});
