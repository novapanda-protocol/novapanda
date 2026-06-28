import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import {
  contractAckBytes,
  providerSigningBytes,
  providerSigningCborBytes,
  providerSign,
  resultHashOfJson,
  signContractAck,
  termsHashFromExchange,
} from "../dist/index.js";

const FIXTURE = join(
  dirname(fileURLToPath(import.meta.url)),
  "../../../tests/fixtures/sdk_parity_vector.json",
);
const vector = JSON.parse(readFileSync(FIXTURE, "utf8"));

test("termsHashFromExchange matches Python", () => {
  assert.equal(termsHashFromExchange(vector.exchange), vector.terms_hash);
});

test("contractAckBytes matches Python", () => {
  const bytes = contractAckBytes(vector.terms_hash, vector.exchange.exchange_id);
  assert.equal(Buffer.from(bytes).toString("hex"), vector.contract_ack_bytes_hex);
});

test("signContractAck matches Python", async () => {
  const sk = Buffer.from(vector.provider_private_key_hex, "hex");
  const sig = await signContractAck(sk, vector.exchange);
  assert.equal(sig, vector.contract_ack_sig);
});

test("resultHashOfJson matches Python", () => {
  assert.equal(resultHashOfJson(vector.deliverable), vector.result_hash);
});

test("providerSigningBytes matches Python", () => {
  const bytes = providerSigningBytes(vector.unsigned_vdc);
  assert.equal(Buffer.from(bytes).toString("hex"), vector.provider_signing_bytes_hex);
});

test("providerSigningCborBytes matches Python", () => {
  const bytes = providerSigningCborBytes(vector.unsigned_vdc);
  assert.equal(Buffer.from(bytes).toString("hex"), vector.provider_signing_cbor_bytes_hex);
});

test("providerSign matches Python", async () => {
  const sk = Buffer.from(vector.provider_private_key_hex, "hex");
  const doc = structuredClone(vector.unsigned_vdc);
  await providerSign(doc, sk);
  assert.equal(doc.signatures.provider_sig, vector.provider_sig);
});
