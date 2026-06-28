import assert from "node:assert/strict";
import test from "node:test";
import { canonicalString } from "../dist/canonical.js";

test("canonicalString sorts keys", () => {
  const a = canonicalString({ b: 1, a: "x" });
  const b = canonicalString({ a: "x", b: 1 });
  assert.equal(a, b);
  assert.equal(a, '{"a":"x","b":1}');
});
