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
  const canonical = value => JSON.stringify(value, (_, nested) => object(nested)
    ? Object.fromEntries(Object.entries(nested).sort(([left], [right]) => left.localeCompare(right)))
    : nested);
  const higher = new Set(["continuity", "evidence_calibration", "public_trust", "dissent_reach"]);
  const delta = (candidate, baseline, metric) => Number(
    (higher.has(metric) ? candidate - baseline : baseline - candidate).toFixed(6)
  );

  function projectRefutationChecks(payload, byModeSeed) {
    return [
      ["plural_always_better_without_tradeoff", "plural", "centralized"],
      ["centralized_always_better_without_tradeoff", "centralized", "plural"]
    ].map(([checkId, candidateMode, baselineMode]) => {
      const observationId = `${candidateMode}_dominates_${baselineMode}`;
      const observations = [...new Set(payload.seeds)].sort((a, b) => a - b).map(seed => {
        const candidate = byModeSeed.get(`${candidateMode}:${seed}`);
        const baseline = byModeSeed.get(`${baselineMode}:${seed}`);
        if (!candidate || !baseline || candidate.audit.fallback_applied || baseline.audit.fallback_applied
          || candidate.effective_mode !== candidateMode || baseline.effective_mode !== baselineMode) {
          return { check_id: observationId, seed, status: "not_observable", evidence: { reason: "required_effective_mode_missing" } };
        }
        const metrics = Object.keys(candidate.metrics).filter(metric => metric in baseline.metrics).sort();
        const deltas = Object.fromEntries(metrics.map(metric => [metric, delta(candidate.metrics[metric], baseline.metrics[metric], metric)]));
        const values = Object.values(deltas);
        const dominates = values.length > 0 && values.every(value => value >= 0) && values.some(value => value > 0);
        return {
          check_id: observationId,
          seed,
          status: dominates ? "triggered" : values.length ? "not_triggered" : "not_observable",
          evidence: {
            candidate_run_id: candidate.manifest.run_id,
            baseline_run_id: baseline.manifest.run_id,
            direction_adjusted_metric_deltas: deltas
          }
        };
      });
      const observable = observations.filter(item => item.status !== "not_observable");
      const complete = observations.length > 0 && observable.length === observations.length;
      return {
        check_id: checkId,
        seed: null,
        status: complete && observable.every(item => item.status === "triggered") ? "triggered" : complete ? "not_triggered" : "not_observable",
        evidence: { per_seed: observations }
      };
    });
  }

  function project(payload) {
    const runs = payload.runs;
    const failureRunIds = runs
      .filter(run => run.manifest.termination_reason !== "turn_limit_reached" || run.events.length !== run.manifest.turn_limit)
      .map(run => run.manifest.run_id).sort();
    const evidenceRuns = payload.ai_evidence_runs;
    const aiReplay = evidenceRuns === undefined ? null : {
      run_count: evidenceRuns.length,
      decision_sources: [...new Set(evidenceRuns.flatMap(run => run.decisions.map(item => item.decision_source)))].sort(),
      fallback_count: evidenceRuns.filter(run => run.audit.fallback_applied).length
    };
    const byModeSeed = new Map(runs.map(run => [`${run.requested_mode}:${run.seed}`, run]));
    const pairs = [...new Set(payload.seeds)].sort((a, b) => a - b).flatMap(seed => {
      const plural = byModeSeed.get(`plural:${seed}`); const centralized = byModeSeed.get(`centralized:${seed}`);
      return plural && centralized && !plural.audit.fallback_applied && !centralized.audit.fallback_applied ? [[plural, centralized]] : [];
    });
    const reversals = pairs.length ? Object.keys(pairs[0][0].metrics).sort().filter(metric => {
      const deltas = pairs.map(([plural, centralized]) => (higher.has(metric) ? 1 : -1) * (plural.metrics[metric] - centralized.metrics[metric]));
      return deltas.some(value => value < 0) && deltas.some(value => value > 0);
    }) : [];
    return {
      seeds: [...new Set(payload.seeds)].sort((a, b) => a - b),
      run_count: runs.length,
      failure_run_ids: failureRunIds,
      ai_replay: aiReplay,
      plural_vs_centralized_sign_reversals: reversals,
      refutation_checks: projectRefutationChecks(payload, byModeSeed)
    };
  }

  function validate(payload) {
    const card = payload?.result_card;
    if (card == null) return { card: null, invalid: false };
    const runs = payload.runs;
    const cardRuns = card.runs;
    const failures = card.failure_runs;
    const checks = card.refutation_checks;
    const limitations = card.limitations;
    const seeds = payload?.seeds;
    const runSeeds = Array.isArray(runs) && runs.every(rawRun) ? [...new Set(runs.map(run => run.seed))].sort((a, b) => a - b) : [];
    const canonicalSeeds = Array.isArray(seeds) ? [...new Set(seeds)].sort((a, b) => a - b) : [];
    let valid = object(card) && card.schema_version === "result-card-v1"
      && typeof payload.artifact_revision === "string" && payload.artifact_revision.length === 16
      && card.artifact_revision === payload.artifact_revision
      && Array.isArray(seeds) && seeds.length > 0 && seeds.every(Number.isInteger)
      && canonicalSeeds.length === seeds.length && canonical(seeds.slice().sort((a, b) => a - b)) === canonical(runSeeds)
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
    if (valid) {
      const projected = project(payload);
      valid = canonical(payload.evidence_summary) === canonical(projected)
        && canonical(failures.map(item => item.run_id).sort()) === canonical(projected.failure_run_ids)
        && canonical(replay ?? null) === canonical(projected.ai_replay)
        && canonical(card.seed_sensitivity?.plural_vs_centralized_sign_reversals) === canonical(projected.plural_vs_centralized_sign_reversals)
        && canonical(card.refutation_checks) === canonical(projected.refutation_checks);
    }
    return valid ? { card, invalid: false } : { card: null, invalid: true };
  }

  return { project, validate };
});
