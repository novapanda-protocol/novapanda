export { canonicalBytes, canonicalString } from "./canonical.js";
export type { AuthHeaders, RequestSigner } from "./auth.js";
export { unsignedSigner } from "./auth.js";
export type { NovaPandaErrorBody } from "./errors.js";
export { NovaPandaError, parseErrorResponse } from "./errors.js";
export {
  agentIdFromPublicKey,
  b58decode,
  b58encode,
  b64urlDecode,
  b64urlEncode,
  pubkeyFromAgentId,
  sha256Hex,
} from "./crypto.js";
export { resultHash, resultHashOfJson } from "./hashing.js";
export {
  agentIdFromPrivateKey,
  createEd25519Signer,
  requestSigningBytes,
  signBytes,
  signRequest,
  verifyBytes,
} from "./sign.js";
export type { ExchangeTerms } from "./terms.js";
export {
  contractAckBytes,
  signContractAck,
  termsHashFromExchange,
} from "./terms.js";
export type { VdcDoc } from "./vdc.js";
export {
  buildVdc,
  clientSign,
  clientSigningBytes,
  isValidSettled,
  providerPayloadBytes,
  providerPayloadEncoding,
  providerSign,
  providerSigningBytes,
  providerSigningCborBytes,
  providerSigningPayload,
  verifyClient,
  verifyProvider,
} from "./vdc.js";
export type { ReverifyChecks } from "./reverify.js";
export { allOk, reverify } from "./reverify.js";
export { canonicalCborBytes } from "./cbor.js";

export type ExchangeState =
  | "PROPOSED"
  | "CONTRACTED"
  | "ESCROWED"
  | "DELIVERED"
  | "VERIFIED"
  | "SETTLED"
  | "REJECTED"
  | "DISPUTED"
  | "EXPIRED_REFUNDED"
  | "CANCELLED";

export interface NovaPandaClientOptions {
  baseUrl: string;
  agentId?: string;
  privateKey?: Uint8Array;
  fetchImpl?: typeof fetch;
  signer?: import("./auth.js").RequestSigner;
}

import { canonicalBytes } from "./canonical.js";
import { unsignedSigner } from "./auth.js";
import { resultHashOfJson } from "./hashing.js";
import { agentIdFromPrivateKey, createEd25519Signer } from "./sign.js";
import { signContractAck, type ExchangeTerms } from "./terms.js";
import { buildVdc, clientSign, providerSign } from "./vdc.js";
import { parseErrorResponse } from "./errors.js";

export class NovaPandaClient {
  readonly baseUrl: string;
  readonly agentId: string;
  readonly privateKey?: Uint8Array;
  private readonly fetchImpl: typeof fetch;
  private readonly signer: import("./auth.js").RequestSigner;

  constructor(opts: NovaPandaClientOptions) {
    this.baseUrl = opts.baseUrl.replace(/\/$/, "");
    this.privateKey = opts.privateKey;
    this.agentId =
      opts.agentId ??
      (opts.privateKey ? agentIdFromPrivateKey(opts.privateKey) : "");
    this.fetchImpl = opts.fetchImpl ?? fetch;
    this.signer =
      opts.signer ??
      (opts.privateKey ? createEd25519Signer(opts.privateKey) : unsignedSigner);
  }

  private requireKey(): Uint8Array {
    if (!this.privateKey) {
      throw new Error("NovaPandaClient 需要 privateKey 才能本地签名");
    }
    return this.privateKey;
  }

  private async request(method: string, path: string, body?: unknown): Promise<unknown> {
    const payload = body === undefined ? new Uint8Array() : canonicalBytes(body);
    const headers: Record<string, string> = {
      ...(await this.signer(method, path, payload)),
    };
    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
    }
    const r = await this.fetchImpl(this.baseUrl + path, {
      method,
      headers,
      body: body === undefined ? undefined : new TextDecoder().decode(payload),
    });
    if (!r.ok) {
      throw await parseErrorResponse(r.status, r);
    }
    return r.json();
  }

  async getReputationScore(
    agentId: string,
    weights?: Record<string, number>,
  ): Promise<Record<string, unknown>> {
    const qs =
      weights === undefined
        ? ""
        : `?weights=${encodeURIComponent(JSON.stringify(weights))}`;
    return (await this.request(
      "GET",
      `/v2/reputation/${encodeURIComponent(agentId)}/score${qs}`,
    )) as Record<string, unknown>;
  }

  async getExchange(exchangeId: string): Promise<Record<string, unknown>> {
    return (await this.request("GET", `/exchanges/${exchangeId}`)) as Record<string, unknown>;
  }

  async getVdc(vdcId: string): Promise<unknown> {
    return this.request("GET", `/vdc/${vdcId}`);
  }

  async propose(input: {
    provider: string;
    resourceType: string;
    quantity: number;
    ruleId: string;
    price: { amount: number; currency: string };
    idempotencyKey: string;
    timeouts?: Record<string, number>;
  }): Promise<unknown> {
    const body: Record<string, unknown> = {
      client: this.agentId,
      provider: input.provider,
      resource_type: input.resourceType,
      quantity: input.quantity,
      rule_id: input.ruleId,
      price: input.price,
      idempotency_key: input.idempotencyKey,
    };
    if (input.timeouts !== undefined) {
      body.timeouts = input.timeouts;
    }
    return this.request("POST", "/exchanges", body);
  }

  async contract(exchangeId: string): Promise<unknown> {
    const ex = (await this.getExchange(exchangeId)) as unknown as import("./terms.js").ExchangeTerms;
    const signature = await signContractAck(this.requireKey(), ex);
    return this.request("POST", `/exchanges/${exchangeId}/contract`, { signature });
  }

  async escrow(exchangeId: string, amount: number, currency: string): Promise<unknown> {
    return this.request("POST", `/exchanges/${exchangeId}/escrow`, { amount, currency });
  }

  async verify(exchangeId: string): Promise<unknown> {
    return this.request("POST", `/exchanges/${exchangeId}/verify`);
  }

  async confirm(exchangeId: string): Promise<unknown> {
    const ex = await this.getExchange(exchangeId);
    const doc = ex.vdc as import("./vdc.js").VdcDoc | null | undefined;
    if (!doc) throw new Error("Exchange 尚无 VDC，无法 confirm");
    if (doc.parties.client !== this.agentId) {
      throw new Error("当前身份不是该交换的 client");
    }
    const signed = structuredClone(doc);
    await clientSign(signed, this.requireKey());
    return this.request("POST", `/exchanges/${exchangeId}/confirm`, { vdc: signed });
  }

  async deliver(
    exchangeId: string,
    deliverable: unknown,
    evidenceLevel = "dual_signed",
  ): Promise<unknown> {
    const ex = await this.getExchange(exchangeId);
    if (ex.provider !== this.agentId) {
      throw new Error("当前身份不是该交换的 provider");
    }
    const doc = buildVdc({
      client: ex.client as string,
      provider: ex.provider as string,
      resourceType: ex.resource_type as string,
      quantity: ex.quantity as number,
      resultHash: resultHashOfJson(deliverable),
      ruleId: ex.rule_id as string,
      evidenceLevel,
      idempotencyKey: ex.idempotency_key as string,
      nonce: ex.nonce as string,
      state: "DELIVERED",
    });
    await providerSign(doc, this.requireKey());
    return this.request("POST", `/exchanges/${exchangeId}/deliver`, {
      vdc: doc,
      deliverable,
    });
  }

  async reputation(agentId: string): Promise<unknown> {
    return this.request("GET", `/reputation/${agentId}`);
  }
}
