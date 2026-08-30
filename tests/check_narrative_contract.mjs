import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const source = fs.readFileSync(new URL("../web/narrative-contract.js", import.meta.url), "utf8");
const context = { globalThis: {} };
vm.createContext(context);
vm.runInContext(source, context);
const contract = context.globalThis.NarrativeContract;
const event = {
  turn: 8, actor_id: "evidence_verifier", claim: "独立確認が必要だ", reservation: "失効後は訂正できない",
  operative_action: "hold_for_partner_review", partner_action: "request_pause", success_confidence: 0.95,
  dissent_raised: true, dissent_delivered: true,
  observation_ids: ["obs-08"], rationale_refs: ["policy-plural", "obs-08"], cost_codes: ["option_preservation"]
};
const first = contract.project(event, "停止要求が届いた");
const second = contract.project(structuredClone(event), "停止要求が届いた");
assert.deepEqual(first, second, "same event must produce the same story");
assert.equal(first.available, true);
assert.equal(first.act, "転換");
assert.equal(first.dialogue.length, 3);
assert.equal(first.dialogue[2].role, "停止要求");
assert.match(first.dialogue[2].text, /戻せない/);
const undelivered = contract.project({ ...event, partner_action: "observe", dissent_delivered: false }, "未到達");
assert.equal(undelivered.dialogue[2].speaker, "異議チャネル");
assert.equal(undelivered.dialogue[2].role, "未到達");
const unknownAction = contract.project({ ...event, operative_action: "unknown_action" }, "未知");
assert.equal(unknownAction.available, false);
assert.equal(unknownAction.reason, "narrative_source_missing");
for (const invalidEvent of [
  { ...event, actor_id: "unknown_actor" },
  { ...event, actor_id: "__proto__" },
  { ...event, partner_action: "unknown_partner" },
  { ...event, operative_action: "toString" },
  { ...event, dissent_raised: false, dissent_delivered: true },
]) {
  const rejected = contract.project(invalidEvent, "不整合");
  assert.equal(rejected.available, false);
  assert.equal(rejected.reason, "narrative_source_missing");
}
const missing = contract.project({ turn: 8 }, "欠落");
assert.equal(missing.available, false);
assert.equal(missing.reason, "narrative_source_missing");
const invalid = contract.project({ turn: 13 }, "不正");
assert.equal(invalid.available, false);
assert.equal(invalid.reason, "turn_invalid");
const comparison = JSON.parse(fs.readFileSync(new URL("../web/data/comparison.json", import.meta.url), "utf8"));
for (const trajectory of comparison.playable_trajectories) {
  for (const recordedEvent of trajectory.bundle.event_stream.events) {
    const projected = contract.project(recordedEvent, recordedEvent.scenario_beat_id);
    assert.equal(projected.available, true, `${trajectory.trajectory_id} turn ${recordedEvent.turn} must be narratable`);
    assert.equal(projected.dialogue.length, 3);
  }
}
console.log("narrative-contract: PASS");
