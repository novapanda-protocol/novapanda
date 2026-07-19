/**
 * TS SDK auth 节点全生命周期冒烟（由 pytest 启动 uvicorn 或手动传入 base URL）。
 *
 *   node test/plugfest_lifecycle.mjs http://127.0.0.1:8765
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { NovaPandaClient, allOk, reverify } from "../dist/index.js";

const baseUrl = process.argv[2];
if (!baseUrl) {
  console.error("usage: node test/plugfest_lifecycle.mjs <baseUrl>");
  process.exit(2);
}

const FIXTURE = join(
  dirname(fileURLToPath(import.meta.url)),
  "../../../tests/fixtures/sdk_parity_vector.json",
);
const vector = JSON.parse(readFileSync(FIXTURE, "utf8"));
const clientKey = Buffer.from(vector.client_private_key_hex, "hex");
const providerKey = Buffer.from(vector.provider_private_key_hex, "hex");

const client = new NovaPandaClient({ baseUrl, privateKey: clientKey });
const provider = new NovaPandaClient({ baseUrl, privateKey: providerKey });

const GOOD = { invoice_no: "TS-001", total: "100.00", currency: "USD" };
const idem = `ts-plugfest-${Date.now()}`;

const ex = await client.propose({
  provider: provider.agentId,
  resourceType: "data.extraction.structured",
  quantity: 1,
  ruleId: "R-extract-invoice-v1",
  price: { amount: 100, currency: "USD" },
  idempotencyKey: idem,
});
const eid = ex.exchange_id;
assert.ok(eid);

await client.contract(eid);
await provider.contract(eid);
await client.escrow(eid, 100, "USD");
await provider.deliver(eid, GOOD);
const verified = await client.verify(eid);
assert.equal(verified.state, "VERIFIED");
const settled = await client.confirm(eid);
assert.equal(settled.state, "SETTLED");
assert.ok(settled.vdc?.signatures?.client_sig);

// L0: offline reverify — no further HTTP; node may be gone
const checks = await reverify(settled.vdc, GOOD);
assert.equal(allOk(checks), true);

console.log(
  JSON.stringify({
    ok: true,
    exchange_id: eid,
    vdc_id: settled.vdc.vdc_id,
    reverify: checks,
  }),
);
