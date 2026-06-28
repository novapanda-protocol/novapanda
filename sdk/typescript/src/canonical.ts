/** Canonical JSON (v0) — align with troodon/canonical.py */

function normalize(value: unknown): unknown {
  if (value === null || typeof value === "boolean") return value;
  if (typeof value === "number") {
    if (!Number.isInteger(value)) {
      throw new Error("canonical JSON v0 rejects non-integer numbers");
    }
    return value;
  }
  if (typeof value === "string") return value.normalize("NFC");
  if (Array.isArray(value)) return value.map(normalize);
  if (typeof value === "object") {
    const obj = value as Record<string, unknown>;
    const out: Record<string, unknown> = {};
    for (const key of Object.keys(obj).sort()) {
      out[key.normalize("NFC")] = normalize(obj[key]);
    }
    return out;
  }
  throw new Error(`unsupported type: ${typeof value}`);
}

export function canonicalString(value: unknown): string {
  return JSON.stringify(normalize(value));
}

export function canonicalBytes(value: unknown): Uint8Array {
  return new TextEncoder().encode(canonicalString(value));
}
