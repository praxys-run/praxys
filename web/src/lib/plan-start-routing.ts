interface PlanStartCapabilityRoute {
  capability_id?: string | null;
}

interface PlanStartCapabilityContract {
  id: string;
  constraint_schema_id: string;
}

export function hasSupportedPlanStartContract(
  capability: PlanStartCapabilityContract | null | undefined,
  supportedContracts: ReadonlyMap<string, string>,
): capability is PlanStartCapabilityContract {
  return Boolean(
    capability
    && supportedContracts.get(capability.id)
      === capability.constraint_schema_id,
  );
}

/**
 * Resolve a server route only when the exact capability is present and this
 * client explicitly understands its constraint contract. A matching ID alone
 * must never let an older client guess how to construct policy inputs.
 */
export function matchingPlanStartCapability<
  T extends PlanStartCapabilityContract,
>(
  capabilities: readonly T[],
  route: PlanStartCapabilityRoute | null | undefined,
  supportedContracts: ReadonlyMap<string, string>,
): T | null {
  const capabilityId = route?.capability_id;
  if (!capabilityId) return null;
  const capability = capabilities.find((item) => item.id === capabilityId);
  if (!capability) return null;
  return hasSupportedPlanStartContract(capability, supportedContracts)
    ? capability
    : null;
}
