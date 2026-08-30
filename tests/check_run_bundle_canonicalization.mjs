import assert from "node:assert/strict";

function normalizedNumber(value) {
  if (!Number.isFinite(value)) throw new Error("non-finite number");
  if (Object.is(value, -0) || value === 0) return "0";
  const magnitude = Math.abs(value);
  if (magnitude < 1e-6 || magnitude >= 1e21) throw new Error("outside portable decimal range");
  return String(value);
}

function project(value) {
  if (value === null || typeof value === "boolean" || typeof value === "string") return value;
  if (typeof value === "number") {
    if (Number.isInteger(value) && !Number.isSafeInteger(value)) throw new Error("unsafe integer");
    return { $number: normalizedNumber(value) };
  }
  if (Array.isArray(value)) return value.map(project);
  if (typeof value === "object") {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, project(value[key])]));
  }
  throw new Error(`unsupported value: ${typeof value}`);
}

const vector = { whole: 1, integral_float: 1.0, decimal: 0.125, negative_zero: -0.0 };
assert.equal(
  JSON.stringify(project(vector)),
  '{"decimal":{"$number":"0.125"},"integral_float":{"$number":"1"},"negative_zero":{"$number":"0"},"whole":{"$number":"1"}}',
);
console.log("run-bundle-canonicalization: PASS");
