import fs from "node:fs";
import vm from "node:vm";

const source = fs.readFileSync(new URL("../web/experience-contract.js", import.meta.url), "utf8");
const context = { globalThis: {} };
vm.runInNewContext(source, context);
const { validate } = context.globalThis.ExperienceContract;

const bundle = {
    schema_version: "meta-security-run-bundle/v1",
    run_id: "run-verified-42",
    run_request: {
      run_id: "run-verified-42",
      seed: 42,
      requested_mode: "plural",
      scenario: { scenario_id: "kagamishio-v1", beats: Array.from({ length: 12 }, (_, index) => ({ turn: index + 1, beat_id: `beat-${index + 1}`, event_type: "replica_link_lost" })) },
      operative_plan: {
        attention: {
          body_control: 18,
          route_verification: 18,
          civilian_impact: 18,
          replica_sync: 16,
          delegation: 14,
          self_audit: 16,
        },
      },
    },
    event_stream: { run_id: "run-verified-42", ordering: "turn-ascending/v1", events: Array.from({ length: 12 }, (_, index) => ({
      run_id: "run-verified-42",
      seed: 42,
      event_index: index,
      turn: index + 1,
      scenario_beat_id: `beat-${index + 1}`,
      operative_action: "verify_lineage",
      partner_action: "request_pause",
      success_confidence: 0.74,
      cost_codes: ["attention_spent"],
      operative_state_before: { cognitive_integrity: 0.96, option_preservation: 0.94 },
      operative_state_after: { cognitive_integrity: 0.95, option_preservation: 0.93 },
    }))},
    replay: { run_id: "run-verified-42" },
    evidence: { run_id: "run-verified-42", verification: "replay-match" },
};
const base = {
  experience_capability: {
    schema_version: "ghost-in-the-sim-experience/v1",
    renderer_mode: "artifact-only",
    operation_console: true,
  },
  trajectories: [bundle],
};

const valid = validate(base);
if (!valid.available || valid.trajectory.runId !== bundle.run_id) throw new Error("verified artifact rejected");
if (valid.trajectory.attention.route_verification !== 18) throw new Error("attention allocation drifted");

const generated = JSON.parse(fs.readFileSync(new URL("../web/data/comparison.json", import.meta.url), "utf8"));
const generatedResult = validate(generated);
if (!generatedResult.available || generatedResult.trajectories.length !== 9) throw new Error("generated artifact rejected");
if (generatedResult.trajectories.some(item => item.events.length !== 12 || item.attentionBudget !== 100)) throw new Error("generated trajectory drifted");

for (const mutate of [
  value => { value.trajectories[0].evidence.verification = "unverified"; },
  value => { value.trajectories[0].replay.run_id = "other"; },
  value => { delete value.trajectories[0].event_stream.events[0].operative_state_after; },
  value => { value.experience_capability.renderer_mode = "client-simulation"; },
]) {
  const candidate = structuredClone(base);
  mutate(candidate);
  if (validate(candidate).available) throw new Error("invalid artifact accepted");
}

console.log("experience-contract: PASS");
