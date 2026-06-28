/** RFC 8949 canonical CBOR — byte-compatible with Python cbor2 (canonical=True). */

import { canonicalString } from "./canonical.js";

function concat(parts: Uint8Array[]): Uint8Array {
  const total = parts.reduce((n, p) => n + p.length, 0);
  const out = new Uint8Array(total);
  let off = 0;
  for (const p of parts) {
    out.set(p, off);
    off += p.length;
  }
  return out;
}

function compareBytes(a: Uint8Array, b: Uint8Array): number {
  const n = Math.min(a.length, b.length);
  for (let i = 0; i < n; i++) {
    if (a[i] !== b[i]) return a[i] - b[i];
  }
  return a.length - b.length;
}

function encodeLength(major: number, length: number): Uint8Array {
  const mt = major << 5;
  if (length <= 23) return new Uint8Array([mt + length]);
  if (length <= 0xff) return new Uint8Array([mt + 24, length]);
  if (length <= 0xffff) {
    return new Uint8Array([mt + 25, (length >> 8) & 0xff, length & 0xff]);
  }
  if (length <= 0xffffffff) {
    return new Uint8Array([
      mt + 26,
      (length >>> 24) & 0xff,
      (length >>> 16) & 0xff,
      (length >>> 8) & 0xff,
      length & 0xff,
    ]);
  }
  throw new Error("CBOR length too large");
}

function encodeUnsigned(n: number): Uint8Array {
  if (!Number.isInteger(n) || n < 0) {
    throw new Error(`CBOR unsigned int required, got ${n}`);
  }
  if (n <= 23) return new Uint8Array([n]);
  if (n <= 0xff) return new Uint8Array([0x18, n]);
  if (n <= 0xffff) return new Uint8Array([0x19, (n >> 8) & 0xff, n & 0xff]);
  if (n <= 0xffffffff) {
    return new Uint8Array([0x1a, (n >>> 24) & 0xff, (n >>> 16) & 0xff, (n >>> 8) & 0xff, n & 0xff]);
  }
  throw new Error("integer too large");
}

function encodeText(s: string): Uint8Array {
  const body = new TextEncoder().encode(s);
  return concat([encodeLength(3, body.length), body]);
}

function encodeArray(items: unknown[]): Uint8Array {
  const parts: Uint8Array[] = [encodeLength(4, items.length)];
  for (const item of items) parts.push(encodeValue(item));
  return concat(parts);
}

function encodeMap(obj: Record<string, unknown>): Uint8Array {
  const entries = Object.entries(obj).map(([k, v]) => ({
    keyBytes: encodeText(k),
    value: v,
  }));
  entries.sort((a, b) => compareBytes(a.keyBytes, b.keyBytes));
  const parts: Uint8Array[] = [encodeLength(5, entries.length)];
  for (const e of entries) {
    parts.push(e.keyBytes);
    parts.push(encodeValue(e.value));
  }
  return concat(parts);
}

function encodeValue(value: unknown): Uint8Array {
  if (value === null) return new Uint8Array([0xf6]);
  if (value === true) return new Uint8Array([0xf5]);
  if (value === false) return new Uint8Array([0xf4]);
  if (typeof value === "number") return encodeUnsigned(value);
  if (typeof value === "string") return encodeText(value);
  if (Array.isArray(value)) return encodeArray(value);
  if (typeof value === "object") return encodeMap(value as Record<string, unknown>);
  throw new Error(`unsupported CBOR type: ${typeof value}`);
}

export function canonicalCborBytes(value: unknown): Uint8Array {
  const normalized = JSON.parse(canonicalString(value));
  return encodeValue(normalized);
}
