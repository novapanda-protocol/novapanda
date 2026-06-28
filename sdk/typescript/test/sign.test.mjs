import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import {
  agentIdFromPrivateKey,
  requestSigningBytes,
  signRequest,
} from "../dist/sign.js";

const FIXTURE = join(
  dirname(fileURLToPath(import.meta.url)),
  "../../../tests/fixtures/ed25519_signing_vector.json",
);
const vector = JSON.parse(readFileSync(FIXTURE, "utf8"));

test("agentIdFromPrivateKey matches Python vector", () => {
  const sk = Buffer.from(vector.private_key_hex, "hex");
  assert.equal(agentIdFromPrivateKey(sk), vector.agent_id);
});

test("signRequest matches Python vector", async () => {
  const sk = Buffer.from(vector.private_key_hex, "hex");
  const body = Buffer.from(vector.body, "utf8");
  const sig = await signRequest(sk, vector.method, vector.path, vector.nonce, body);
  assert.equal(sig, vector.signature);
});

test("requestSigningBytes matches Python vector", () => {
  const body = Buffer.from(vector.body, "utf8");
  const bytes = requestSigningBytes(vector.method, vector.path, vector.nonce, body);
  assert.equal(Buffer.from(bytes).toString("hex"), vector.signing_bytes_hex);
});
