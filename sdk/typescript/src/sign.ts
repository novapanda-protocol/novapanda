/** Ed25519 request signing — aligned with troodon/auth.py */

import { createHash, randomBytes } from "node:crypto";
import * as ed from "@noble/ed25519";
import { canonicalBytes } from "./canonical.js";
import {
  agentIdFromPublicKey,
  b64urlEncode,
  sha256Hex,
} from "./crypto.js";
import type { RequestSigner } from "./auth.js";

ed.etc.sha512Sync = (...messages: Uint8Array[]) => {
  const h = createHash("sha512");
  for (const m of messages) h.update(m);
  return new Uint8Array(h.digest());
};

export async function signBytes(privateKey: Uint8Array, message: Uint8Array): Promise<string> {
  const sig = await ed.signAsync(message, privateKey);
  return b64urlEncode(sig);
}

export function requestSigningBytes(
  method: string,
  path: string,
  nonce: string,
  body: Uint8Array,
): Uint8Array {
  return canonicalBytes({
    method: method.toUpperCase(),
    path,
    nonce,
    body_sha256: sha256Hex(body),
  });
}

export async function signRequest(
  privateKey: Uint8Array,
  method: string,
  path: string,
  nonce: string,
  body: Uint8Array,
): Promise<string> {
  const msg = requestSigningBytes(method, path, nonce, body);
  const sig = await ed.signAsync(msg, privateKey);
  return b64urlEncode(sig);
}

export function agentIdFromPrivateKey(privateKey: Uint8Array): string {
  return agentIdFromPublicKey(ed.getPublicKey(privateKey));
}

export function createEd25519Signer(
  privateKey: Uint8Array,
  agentId?: string,
): RequestSigner {
  const resolvedAgentId = agentId ?? agentIdFromPrivateKey(privateKey);
  return async (method, path, body) => {
    const nonce = randomBytes(16).toString("hex");
    const signature = await signRequest(privateKey, method, path, nonce, body);
    return {
      "X-Agent-Id": resolvedAgentId,
      "X-Nonce": nonce,
      "X-Signature": signature,
    };
  };
}
