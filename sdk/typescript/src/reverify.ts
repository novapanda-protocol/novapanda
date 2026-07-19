/** Offline reverify — align with novapanda/reverify.py (sig + hash; no schema replay). */

import { resultHashOfJson } from "./hashing.js";
import {
  isValidSettled,
  verifyClient,
  verifyProvider,
  type VdcDoc,
} from "./vdc.js";

export type ReverifyChecks = {
  provider_sig_valid: boolean;
  client_sig_valid: boolean | null;
  settled_valid: boolean;
  result_hash_matches?: boolean;
};

export async function reverify(
  doc: VdcDoc,
  deliverable?: unknown,
): Promise<ReverifyChecks> {
  const checks: ReverifyChecks = {
    provider_sig_valid: await verifyProvider(doc),
    client_sig_valid: doc.signatures.client_sig
      ? await verifyClient(doc)
      : null,
    settled_valid: await isValidSettled(doc),
  };
  if (deliverable !== undefined) {
    checks.result_hash_matches = resultHashOfJson(deliverable) === doc.result_hash;
  }
  return checks;
}

export function allOk(checks: ReverifyChecks): boolean {
  for (const [k, v] of Object.entries(checks)) {
    if (k === "client_sig_valid" && v === null) continue;
    if (v === false) return false;
  }
  return true;
}
