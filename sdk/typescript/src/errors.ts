export interface NovaPandaErrorBody {
  code?: string;
  msg?: string;
  score?: number;
  [key: string]: unknown;
}

export class NovaPandaError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly body?: NovaPandaErrorBody;

  constructor(status: number, message: string, body?: NovaPandaErrorBody) {
    super(message);
    this.name = "NovaPandaError";
    this.status = status;
    this.code = body?.code;
    this.body = body;
  }
}

export async function parseErrorResponse(
  status: number,
  response: Response,
): Promise<NovaPandaError> {
  let body: NovaPandaErrorBody | undefined;
  try {
    body = (await response.json()) as NovaPandaErrorBody;
  } catch {
    body = undefined;
  }
  const msg = body?.msg ?? response.statusText ?? `HTTP ${status}`;
  return new NovaPandaError(status, msg, body);
}
