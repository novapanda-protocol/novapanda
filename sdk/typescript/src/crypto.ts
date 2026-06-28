/** Base58 + SHA-256 helpers aligned with troodon/identity.py & hashing.py */

import { createHash } from "node:crypto";

const B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";

export function b58encode(data: Uint8Array): string {
  let n = 0n;
  for (const byte of data) {
    n = (n << 8n) + BigInt(byte);
  }
  let out = "";
  while (n > 0n) {
    const rem = Number(n % 58n);
    n /= 58n;
    out = B58_ALPHABET[rem] + out;
  }
  let pad = 0;
  for (const byte of data) {
    if (byte === 0) pad += 1;
    else break;
  }
  return B58_ALPHABET[0]!.repeat(pad) + out;
}

export function b58decode(s: string): Uint8Array {
  let n = 0n;
  for (const ch of s) {
    n = n * 58n + BigInt(B58_ALPHABET.indexOf(ch));
  }
  let body: Uint8Array;
  if (n === 0n) {
    body = new Uint8Array();
  } else {
    const hex = n.toString(16);
    const padded = hex.length % 2 === 0 ? hex : `0${hex}`;
    body = hexToBytes(padded);
  }
  let pad = 0;
  for (const ch of s) {
    if (ch === B58_ALPHABET[0]) pad += 1;
    else break;
  }
  if (pad === 0) return body;
  const out = new Uint8Array(pad + body.length);
  out.set(body, pad);
  return out;
}

function hexToBytes(hex: string): Uint8Array {
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i += 1) {
    out[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  }
  return out;
}

export function sha256Hex(data: Uint8Array): string {
  return createHash("sha256").update(data).digest("hex");
}

export function b64urlEncode(data: Uint8Array): string {
  return Buffer.from(data)
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
}

export function agentIdFromPublicKey(publicKey: Uint8Array): string {
  return `ed25519:${b58encode(publicKey)}`;
}

export function pubkeyFromAgentId(agentId: string): Uint8Array {
  if (!agentId.startsWith("ed25519:")) {
    throw new Error(`invalid agent_id prefix: ${agentId}`);
  }
  return b58decode(agentId.slice("ed25519:".length));
}
