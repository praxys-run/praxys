interface DeliveryChoice<T extends string> {
  platform: T;
  selectable: boolean;
}

export type PlanTargetSelectionState = 'external' | 'active' | 'paused';

/**
 * Resolve the execution target without ever defaulting to an unavailable
 * platform. An explicit in-session choice wins; otherwise the athlete's
 * primary activity source, durable target, and sole selectable option are
 * considered in that order.
 */
export function choosePlanDeliveryTarget<T extends string>(
  options: readonly DeliveryChoice<T>[],
  explicitChoice: T | null,
  primaryActivitySource: T | null,
  configuredTarget: T | null,
): T | null {
  const selectable = options
    .filter((option) => option.selectable)
    .map((option) => option.platform);
  if (explicitChoice && selectable.includes(explicitChoice)) {
    return explicitChoice;
  }
  if (primaryActivitySource && selectable.includes(primaryActivitySource)) {
    return primaryActivitySource;
  }
  if (configuredTarget && selectable.includes(configuredTarget)) {
    return configuredTarget;
  }
  return selectable.length === 1 ? selectable[0] : null;
}

/**
 * Resolve the target shown by the managed-plan selector.
 *
 * Active delivery is intentionally read-only. Paused delivery starts from the
 * durable target but may stage another eligible choice without resuming.
 * External mode keeps the existing adoption defaults.
 */
export function planTargetSelection<T extends string>(
  state: PlanTargetSelectionState,
  options: readonly DeliveryChoice<T>[],
  explicitChoice: T | null,
  primaryActivitySource: T | null,
  configuredTarget: T | null,
): T | null {
  if (state === 'active') return configuredTarget;
  const explicitSelectable = explicitChoice != null
    && options.some(
      (option) => (
        option.platform === explicitChoice && option.selectable
      ),
    );
  if (state === 'paused') {
    if (explicitSelectable) return explicitChoice;
    if (configuredTarget) return configuredTarget;
  }
  return choosePlanDeliveryTarget(
    options,
    explicitChoice,
    primaryActivitySource,
    configuredTarget,
  );
}
