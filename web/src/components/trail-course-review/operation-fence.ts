export interface TrailOperationStamp {
  lifetime: number;
  ownerScope: string;
  requestId: number;
  revision: string;
  editGeneration: number;
}

export function isCurrentTrailOperation(
  started: TrailOperationStamp,
  current: TrailOperationStamp,
): boolean {
  return started.lifetime === current.lifetime
    && started.ownerScope === current.ownerScope
    && started.requestId === current.requestId
    && started.revision === current.revision
    && started.editGeneration === current.editGeneration;
}
