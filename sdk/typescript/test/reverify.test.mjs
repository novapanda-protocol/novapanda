import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import {
  allOk,
  clientSign,
  providerSign,
  reverify,
  verifyClient,
  verifyProvider,
} from "../dist/index.js";

const FIXTURE = join(
  dirname(fileURLToPath(import.meta.url)),
  "../../../tests/fixtures/sdk_parity_vector.json",
);
const vector = JSON.parse(readFileSync(FIXTURE, "utf8"));

test("fixture provider_sig verifies offline", async () => {
  const doc = structuredClone(vector.unsigned_vdc);
  doc.signatures = { provider_sig: vector.provider_sig };
  assert.equal(await verifyProvider(doc), true);
});

test("fixture client_sig verifies without provider_payload_encoding", async () => {
  // Historical vector: client signed before encoding field was always written.
  const doc = structuredClone(vector.unsigned_vdc);
  doc.signatures = {
    provider_sig: vector.provider_sig,
    client_sig: vector.client_sig,
  };
  assert.equal(await verifyClient(doc), true);
});

test("L0 offline reverify after dual-sign + SETTLED", async () => {
  const providerKey = Buffer.from(vector.provider_private_key_hex, "hex");
  const clientKey = Buffer.from(vector.client_private_key_hex, "hex");
  const doc = structuredClone(vector.unsigned_vdc);
  await providerSign(doc, providerKey);
  await clientSign(doc, clientKey);
  doc.state = "SETTLED";
  const checks = await reverify(doc, vector.deliverable);
  assert.equal(checks.provider_sig_valid, true);
  assert.equal(checks.client_sig_valid, true);
  assert.equal(checks.settled_valid, true);
  assert.equal(checks.result_hash_matches, true);
  assert.equal(allOk(checks), true);
});
