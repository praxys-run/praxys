export class TrailMutationResponseError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'TrailMutationResponseError';
    this.status = status;
  }
}

export function preservesPendingTrailEdits(error: unknown): boolean {
  return error instanceof TrailMutationResponseError && error.status === 412;
}
