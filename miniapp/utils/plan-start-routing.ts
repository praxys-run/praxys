import type { PlanGenerationCapability } from '../types/api';

const SUPPORTED_PLAN_START_CAPABILITY_CONTRACTS: Record<string, string> = {
  outdoor_road_5k_v1: 'outdoor_road_5k_constraints_v1',
};

export function hasSupportedPlanStartContract(
  capability: PlanGenerationCapability | null | undefined,
): capability is PlanGenerationCapability {
  return Boolean(
    capability
    && SUPPORTED_PLAN_START_CAPABILITY_CONTRACTS[capability.id]
      === capability.constraint_schema_id,
  );
}
