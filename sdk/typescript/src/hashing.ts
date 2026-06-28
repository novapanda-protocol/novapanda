/** Result hash — align with troodon/hashing.py */

import { canonicalBytes } from "./canonical.js";
import { sha256Hex } from "./crypto.js";

export function resultHash(data: Uint8Array): string {
  return `sha256:${sha256Hex(data)}`;
}

export function resultHashOfJson(value: unknown): string {
  return resultHash(canonicalBytes(value));
}
