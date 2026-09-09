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

interface TrailLifecycleEventTarget {
  addEventListener(type: string, listener: EventListener): void;
  removeEventListener(type: string, listener: EventListener): void;
}

export function bindTrailOwnerScopeInvalidation(
  target: TrailLifecycleEventTarget,
  initialOwnerScope: string,
  getCurrentOwnerScope: () => string,
  invalidate: () => void,
): () => void {
  let invalidated = false;
  const invalidateOnOwnerLoss: EventListener = () => {
    if (invalidated || getCurrentOwnerScope() === initialOwnerScope) return;
    invalidated = true;
    invalidate();
  };
  target.addEventListener('beforeunload', invalidateOnOwnerLoss);
  target.addEventListener('storage', invalidateOnOwnerLoss);
  return () => {
    target.removeEventListener('beforeunload', invalidateOnOwnerLoss);
    target.removeEventListener('storage', invalidateOnOwnerLoss);
  };
}

export function runTrailConfirmationCallback<TSectionKey extends string>(
  sectionKey: TSectionKey,
  hasActiveOperation: () => boolean,
  hasPendingIntent: () => boolean,
  confirm: (key: TSectionKey) => Promise<void>,
): Promise<void> | undefined {
  if (hasActiveOperation() || hasPendingIntent()) return undefined;
  return confirm(sectionKey);
}
