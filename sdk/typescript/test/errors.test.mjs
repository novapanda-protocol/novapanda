import assert from "node:assert/strict";
import test from "node:test";
import { NovaPandaError, parseErrorResponse } from "../dist/errors.js";

test("parseErrorResponse builds NovaPandaError from JSON body", async () => {
  const response = {
    status: 403,
    statusText: "Forbidden",
    json: async () => ({ code: "E_REPUTATION_LOW", msg: "score too low", score: 0.5 }),
  };
  const err = await parseErrorResponse(403, response);
  assert.ok(err instanceof NovaPandaError);
  assert.equal(err.status, 403);
  assert.equal(err.code, "E_REPUTATION_LOW");
  assert.equal(err.message, "score too low");
  assert.equal(err.body?.score, 0.5);
});
