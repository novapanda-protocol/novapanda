/** VDC build + sign — align with novapanda/vdc.py */

import { randomBytes } from "node:crypto";
import { canonicalBytes } from "./canonical.js";
import { canonicalCborBytes } from "./cbor.js";
import { agentIdFromPrivateKey } from "./sign.js";
import { signBytes } from "./sign.js";

export const VDC_VERSION = "0.1";
export const PROVIDER_PAYLOAD_ENCODINGS = ["json", "cbor"] as const;
export type ProviderPayloadEncoding = (typeof PROVIDER_PAYLOAD_ENCODINGS)[number];

export interface VdcDoc {
  vdc_version: string;
  vdc_id: string;
  parties: { client: string; provider: string };
  resource_type: string;
  quantity: number;
  result_hash: string;
  rule_id: string;
  evidence: {
    level: string;
    started_at: string;
    finished_at: string;
    metering?: Record<string, unknown>;
  };
  state: string;
  idempotency_key: string;
  nonce: string;
  prev_hash: string;
  created_at: string;
  signatures: Record<string, string>;
}

function nowIso(): string {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

export function buildVdc(input: {
  client: string;
  provider: string;
  resourceType: string;
  quantity: number;
  resultHash: string;
  ruleId: string;
  evidenceLevel?: string;
  startedAt?: string;
  finishedAt?: string;
  idempotencyKey: string;
  nonce?: string;
  state?: string;
  prevHash?: string;
  vdcId?: string;
  createdAt?: string;
}): VdcDoc {
  const started = input.startedAt ?? nowIso();
  const finished = input.finishedAt ?? started;
  return {
    vdc_version: VDC_VERSION,
    vdc_id: input.vdcId ?? randomBytes(16).toString("hex"),
    parties: { client: input.client, provider: input.provider },
    resource_type: input.resourceType,
    quantity: input.quantity,
    result_hash: input.resultHash,
    rule_id: input.ruleId,
    evidence: {
      level: input.evidenceLevel ?? "dual_signed",
      started_at: started,
      finished_at: finished,
    },
    state: input.state ?? "DELIVERED",
    idempotency_key: input.idempotencyKey,
    nonce: input.nonce ?? randomBytes(16).toString("hex"),
    prev_hash: input.prevHash ?? "GENESIS",
    created_at: input.createdAt ?? nowIso(),
    signatures: {},
  };
}

function stripVolatile(v: Record<string, unknown>): Record<string, unknown> {
  const out = { ...v };
  delete out.state;
  return out;
}

export function providerSigningPayload(vdc: VdcDoc): Record<string, unknown> {
  const v = stripVolatile(structuredClone(vdc) as unknown as Record<string, unknown>);
  delete v.signatures;
  return v;
}

export function providerSigningBytes(vdc: VdcDoc): Uint8Array {
  return canonicalBytes(providerSigningPayload(vdc));
}

export function providerSigningCborBytes(vdc: VdcDoc): Uint8Array {
  return canonicalCborBytes(providerSigningPayload(vdc));
}

export function providerPayloadEncoding(vdc: VdcDoc): ProviderPayloadEncoding {
  const enc = vdc.signatures.provider_payload_encoding;
  return enc === "cbor" ? "cbor" : "json";
}

export function providerPayloadBytes(
  vdc: VdcDoc,
  encoding?: ProviderPayloadEncoding,
): Uint8Array {
  const enc = encoding ?? providerPayloadEncoding(vdc);
  return enc === "cbor" ? providerSigningCborBytes(vdc) : providerSigningBytes(vdc);
}

export function clientSigningBytes(vdc: VdcDoc): Uint8Array {
  const v = structuredClone(vdc) as VdcDoc;
  const sigs = { ...v.signatures };
  delete sigs.client_sig;
  v.signatures = sigs;
  const raw = stripVolatile(v as unknown as Record<string, unknown>);
  return canonicalBytes(raw);
}

export async function providerSign(
  vdc: VdcDoc,
  privateKey: Uint8Array,
  encoding: ProviderPayloadEncoding = "json",
): Promise<VdcDoc> {
  const agentId = agentIdFromPrivateKey(privateKey);
  if (vdc.parties.provider !== agentId) {
    throw new Error("provider 身份与 VDC 不匹配");
  }
  vdc.signatures.provider_payload_encoding = encoding;
  vdc.signatures.provider_sig = await signBytes(
    privateKey,
    providerPayloadBytes(vdc, encoding),
  );
  return vdc;
}

export async function clientSign(vdc: VdcDoc, privateKey: Uint8Array): Promise<VdcDoc> {
  const agentId = agentIdFromPrivateKey(privateKey);
  if (vdc.parties.client !== agentId) {
    throw new Error("client 身份与 VDC 不匹配");
  }
  if (!vdc.signatures.provider_sig) {
    throw new Error("缺少 provider_sig，client 不能先于 provider 签名");
  }
  vdc.signatures.client_sig = await signBytes(privateKey, clientSigningBytes(vdc));
  return vdc;
}
