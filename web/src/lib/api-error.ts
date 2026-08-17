export interface ExtractedApiError {
  status: number;
  message: string;
  code?: string;
}

export class ApiResponseError extends Error {
  readonly status: number;
  readonly code?: string;

  constructor(error: ExtractedApiError) {
    super(error.message);
    this.name = 'ApiResponseError';
    this.status = error.status;
    this.code = error.code;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value != null && typeof value === 'object' && !Array.isArray(value);
}

export async function extractApiError(
  response: Response,
  fallback: string,
): Promise<ExtractedApiError> {
  const payload: unknown = await response.json().catch(() => null);
  const root = isRecord(payload) ? payload : null;
  const detail = root?.detail;
  const detailRecord = isRecord(detail) ? detail : null;
  const firstValidationError = Array.isArray(detail) && detail.length > 0
    && isRecord(detail[0])
    ? detail[0]
    : null;
  const message = typeof detail === 'string'
    ? detail
    : typeof detailRecord?.message === 'string'
      ? detailRecord.message
      : typeof root?.message === 'string'
        ? root.message
        : typeof firstValidationError?.msg === 'string'
          ? firstValidationError.msg
          : fallback;
  const code = typeof detailRecord?.code === 'string'
    ? detailRecord.code
    : typeof root?.code === 'string'
      ? root.code
      : undefined;

  return {
    status: response.status,
    message,
    ...(code ? { code } : {}),
  };
}

export async function apiResponseError(
  response: Response,
  fallback: string,
): Promise<ApiResponseError> {
  return new ApiResponseError(await extractApiError(response, fallback));
}
