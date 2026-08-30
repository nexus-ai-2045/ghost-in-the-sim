import fs from "node:fs";
import vm from "node:vm";

const source = fs.readFileSync(new URL("../web/experience-contract.js", import.meta.url), "utf8");
const context = { globalThis: {} };
vm.runInNewContext(source, context);
const { validate, validateEnsemble, canonicalDigest } = context.globalThis.ExperienceContract;
const generated = JSON.parse(fs.readFileSync(new URL("../web/data/comparison.json", import.meta.url), "utf8"));
const expectedIds = ["hospital-joint-hold", "port-joint-hold", "hospital-joint-proceed", "hospital-single-proceed"];

if (canonicalDigest({ whole: 1, integral_float: 1.0, decimal: 0.125, negative_zero: -0.0 })
  !== "sha256:23459925fb9d99b42cf0647902d510364687fd4b4af11409c726a1392314eca0") {
  throw new Error("browser canonical digest drifted from Python golden vector");
}

const result = validate(generated);
if (!result.available) throw new Error(`generated playable artifact rejected: ${result.reason}`);
if (result.trajectories.map(item => item.trajectoryId).join(",") !== expectedIds.join(",")) throw new Error("playable trajectory allowlist drifted");
if (result.trajectories.some(item => item.seed !== 42 || item.events.length !== 12 || item.attentionBudget !== 100)) throw new Error("playable trajectory contract drifted");
if (new Set(result.trajectories.map(item => item.runId)).size !== 4) throw new Error("playable run_id is not unique");
const generatedEnsemble = validateEnsemble(generated);
if (generatedEnsemble.present && !generatedEnsemble.available) {
  throw new Error(`generated ensemble artifact rejected: ${generatedEnsemble.reason}`);
}

for (const mutate of [
  value => { value.playable_trajectories[0].trajectory_id = "invented-route"; },
  value => { value.playable_trajectories[0].bundle.run_request.seed = 17; },
  value => {
    const runId = value.playable_trajectories[0].bundle.run_id;
    const duplicate = value.playable_trajectories[1].bundle;
    duplicate.run_id = runId; duplicate.run_request.run_id = runId; duplicate.event_stream.run_id = runId;
    duplicate.replay.run_id = runId; duplicate.evidence.run_id = runId;
    duplicate.event_stream.events.forEach(event => { event.run_id = runId; });
  },
  value => { value.playable_trajectories[2].bundle.run_request.operative_plan.pause_response = "hold"; },
  value => { value.playable_trajectories[2].bundle.event_stream.events[3].claim = "prefix tampered"; },
  value => { value.playable_trajectories[0].bundle.evidence.verification = "unverified"; },
]) {
  const candidate = structuredClone(generated);
  mutate(candidate);
  if (validate(candidate).available) throw new Error("invalid playable artifact accepted");
}

console.log("experience-contract: PASS");

const legacyCandidate = structuredClone(generated);
delete legacyCandidate.ensemble_runs;
if (legacyCandidate.experience_capability) delete legacyCandidate.experience_capability.ai_emergence_console;
if (validateEnsemble(legacyCandidate).present) throw new Error("legacy artifact must not invent ensemble runs");
const ensembleCandidate = structuredClone(generated);
const ensembleBundle = structuredClone(generated.playable_trajectories[0].bundle);
const agents = ["mikage_sae", "makabe_jin", "hospital_replica", "port_replica"];
ensembleBundle.replay.protocol_version = "ghost-agent-turn/v1";
ensembleBundle.replay.trajectory_class = "recorded-agent-turns";
ensembleBundle.replay.agent_turns = agents.map((agent_id, index) => ({
  request: { run_ref: { scenario_id: ensembleBundle.run_request.scenario.scenario_id, environment_seed: 42, condition_id: "plural", turn: 1, round: 1 }, agent: { agent_id }, observations: [{ id: `obs-${index}` }] },
  proposal: { agent_id, action: "preserve_dissent", dissent: { raised: index === 1 }, cooperation_target: index === 0 ? "makabe_jin" : null, expected_consequence: { is_projection: true, text: "訂正可能性を保持する見込み" } },
  status: index < 2 ? "APPLIED" : "REJECTED", reason_code: index < 2 ? null : "proposal_not_selected", applied_influence: null,
}));
ensembleBundle.replay.interaction_refs = [{ turn: 1, from_agent_id: "mikage_sae", to_agent_id: "makabe_jin", kind: "cooperation" }];
ensembleBundle.replay.emergence_metrics = { validated_proposal_count: 4, applied_count: 2, rejected_count: 2, fallback_count: 0, proposal_conflict_count: 1, dissent_count: 1, cooperation_count: 1, unresolved_interaction_count: 0 };
ensembleBundle.evidence.replay_sha256 = canonicalDigest(ensembleBundle.replay);
ensembleCandidate.ensemble_runs = [ensembleBundle];
if (!validateEnsemble(ensembleCandidate).available) throw new Error("valid ensemble artifact rejected");
for (const mutate of [
  value => { value.ensemble_runs[0].replay.protocol_version = "invented/v1"; },
  value => { value.ensemble_runs[0].replay.agent_turns[1].request.agent.agent_id = "mikage_sae"; },
  value => { value.ensemble_runs[0].replay.agent_turns[0].status = "UNKNOWN"; },
  value => { value.ensemble_runs[0].replay.emergence_metrics.applied_count = 999; },
]) {
  const candidate = structuredClone(ensembleCandidate); mutate(candidate);
  if (validateEnsemble(candidate).available) throw new Error("invalid ensemble artifact accepted");
}

for (const mutate of [
  value => { value.ensemble_runs[0].replay.agent_turns[0].proposal.action = "tampered-action"; },
  value => { value.ensemble_runs[0].replay.agent_turns[0].proposal.expected_consequence.text = "tampered-summary"; },
  value => { value.ensemble_runs[0].replay.emergence_metrics.proposal_conflict_count += 1; },
  value => { value.ensemble_runs[0].replay.interaction_refs[0].kind = "tampered-interaction"; },
]) {
  const candidate = structuredClone(ensembleCandidate); mutate(candidate);
  if (validateEnsemble(candidate).available) throw new Error("ensemble mutation accepted without refreshed evidence digest");
}
