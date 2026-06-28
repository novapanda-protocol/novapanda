/** Request auth headers — host supplies Ed25519 signing in production via createEd25519Signer. */

export type AuthHeaders = Record<string, string>;

export type RequestSigner = (
  method: string,
  path: string,
  body: Uint8Array,
) => Promise<AuthHeaders> | AuthHeaders;

/** Stub signer for tests / unsigned nodes (auth=false). */
export const unsignedSigner: RequestSigner = () => ({});
