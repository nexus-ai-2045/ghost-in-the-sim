import fs from "node:fs";
import vm from "node:vm";

const source = fs.readFileSync(new URL("../web/experience-contract.js", import.meta.url), "utf8");
const context = { globalThis: {} };
vm.runInNewContext(source, context);
const { validate } = context.globalThis.ExperienceContract;
const generated = JSON.parse(fs.readFileSync(new URL("../web/data/comparison.json", import.meta.url), "utf8"));
const expectedIds = ["hospital-joint-hold", "port-joint-hold", "hospital-joint-proceed", "hospital-single-proceed"];

const result = validate(generated);
if (!result.available) throw new Error(`generated playable artifact rejected: ${result.reason}`);
if (result.trajectories.map(item => item.trajectoryId).join(",") !== expectedIds.join(",")) throw new Error("playable trajectory allowlist drifted");
if (result.trajectories.some(item => item.seed !== 42 || item.events.length !== 12 || item.attentionBudget !== 100)) throw new Error("playable trajectory contract drifted");
if (new Set(result.trajectories.map(item => item.runId)).size !== 4) throw new Error("playable run_id is not unique");

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
