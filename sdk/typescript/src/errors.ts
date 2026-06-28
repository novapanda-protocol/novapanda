export interface TroodonErrorBody {
  code?: string;
  msg?: string;
  score?: number;
  [key: string]: unknown;
}

export class TroodonError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly body?: TroodonErrorBody;

  constructor(status: number, message: string, body?: TroodonErrorBody) {
    super(message);
    this.name = "TroodonError";
    this.status = status;
    this.code = body?.code;
    this.body = body;
  }
}

export async function parseErrorResponse(
  status: number,
  response: Response,
): Promise<TroodonError> {
  let body: TroodonErrorBody | undefined;
  try {
    body = (await response.json()) as TroodonErrorBody;
  } catch {
    body = undefined;
  }
  const msg = body?.msg ?? response.statusText ?? `HTTP ${status}`;
  return new TroodonError(status, msg, body);
}
