/** Contract terms hash + ack signing — align with novapanda/terms.py */

import { canonicalBytes } from "./canonical.js";
import { sha256Hex } from "./crypto.js";
import { signBytes } from "./sign.js";

export interface ExchangeTerms {
  exchange_id: string;
  client: string;
  provider: string;
  resource_type: string;
  quantity: number;
  rule_id: string;
  price: { amount: number; currency: string };
  timeouts?: Record<string, number>;
  nonce: string;
  idempotency_key: string;
  terms_hash?: string;
  vdc?: import("./vdc.js").VdcDoc | null;
}

function termsFields(ex: ExchangeTerms): Record<string, unknown> {
  return {
    exchange_id: ex.exchange_id,
    client: ex.client,
    provider: ex.provider,
    resource_type: ex.resource_type,
    quantity: ex.quantity,
    rule_id: ex.rule_id,
    price: ex.price,
    timeouts: ex.timeouts ?? {},
    nonce: ex.nonce,
    idempotency_key: ex.idempotency_key,
  };
}

export function termsHashFromExchange(ex: ExchangeTerms): string {
  return sha256Hex(canonicalBytes(termsFields(ex)));
}

export function contractAckBytes(termsHash: string, exchangeId: string): Uint8Array {
  return canonicalBytes({
    action: "contract_ack",
    exchange_id: exchangeId,
    terms_hash: termsHash,
  });
}

export async function signContractAck(
  privateKey: Uint8Array,
  ex: ExchangeTerms,
): Promise<string> {
  const th = ex.terms_hash ?? termsHashFromExchange(ex);
  return signBytes(privateKey, contractAckBytes(th, ex.exchange_id));
}
