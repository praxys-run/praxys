import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import type { ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { DisplayConfig, GoalPlanImpact, PlanDeliveryOption, SettingsConfig, SettingsResponse, SettingsUpdate, SettingsUpdateResponse, TrainingBase, ThresholdValue, DetectedThreshold } from '../types/api';
import { apiFetch, getAuthHeaders } from '../hooks/useApi';

interface SettingsContextValue {
  config: SettingsConfig | null;
  display: DisplayConfig | null;
  connectionStatuses: SettingsResponse['connection_statuses'];
  platformCapabilities: SettingsResponse['platform_capabilities'];
  planDeliveryOptions: PlanDeliveryOption[];
  availableProviders: SettingsResponse['available_providers'];
  availableBases: TrainingBase[];
  effectiveThresholds: Record<string, ThresholdValue>;
  detectedThresholds: Record<string, DetectedThreshold>;
  loading: boolean;
  error: string | null;
  goalPlanImpact: GoalPlanImpact | null;
  updateSettings: (update: SettingsUpdate) => Promise<SettingsUpdateResponse>;
  dismissGoalPlanImpact: () => void;
  refetch: () => void;
}

const DEFAULT_DISPLAY: DisplayConfig = {
  threshold_label: 'Critical Power',
  threshold_abbrev: 'CP',
  threshold_unit: 'W',
  load_label: 'RSS',
  load_unit: '',
  intensity_metric: 'Power',
  zone_names: ['Recovery', 'Endurance', 'Tempo', 'Threshold', 'VO2max'],
  trend_label: 'CP Trend',
};

const SettingsContext = createContext<SettingsContextValue>({
  config: null,
  display: DEFAULT_DISPLAY,
  connectionStatuses: {},
  platformCapabilities: {},
  planDeliveryOptions: [],
  availableProviders: {},
  availableBases: ['power', 'hr', 'pace'],
  effectiveThresholds: {},
  detectedThresholds: {},
  loading: true,
  error: null,
  goalPlanImpact: null,
  updateSettings: async () => {
    throw new Error('SettingsProvider is not mounted');
  },
  dismissGoalPlanImpact: () => {},
  refetch: () => {},
});

function planDeliveryOptionsFromResponse(
  data: Pick<
    SettingsResponse,
    'config' | 'platform_capabilities' | 'plan_delivery_options'
  >,
): PlanDeliveryOption[] {
  if (data.plan_delivery_options !== undefined) {
    return data.plan_delivery_options;
  }
  return data.config.connections.map((platform) => ({
    platform,
    selectable: data.platform_capabilities[platform]?.plan === true,
    reason: data.platform_capabilities[platform]?.plan === true
      ? null
      : 'delivery_not_supported',
  }));
}

function goalPlanImpactKey(impact: GoalPlanImpact): string {
  return [
    impact.plan_goal_snapshot_id,
    impact.current_goal_revision,
  ].join(':');
}

export function SettingsProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [config, setConfig] = useState<SettingsConfig | null>(null);
  const [display, setDisplay] = useState<DisplayConfig>(DEFAULT_DISPLAY);
  const [connectionStatuses, setConnectionStatuses] = useState<
    SettingsResponse['connection_statuses']
  >({});
  const [platformCapabilities, setPlatformCapabilities] = useState<
    SettingsResponse['platform_capabilities']
  >({});
  const [planDeliveryOptions, setPlanDeliveryOptions] = useState<
    PlanDeliveryOption[]
  >([]);
  const [availableProviders, setAvailableProviders] = useState<
    SettingsResponse['available_providers']
  >({});
  const [availableBases, setAvailableBases] = useState<TrainingBase[]>(['power', 'hr', 'pace']);
  const [effectiveThresholds, setEffectiveThresholds] = useState<Record<string, ThresholdValue>>({});
  const [detectedThresholds, setDetectedThresholds] = useState<Record<string, DetectedThreshold>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [goalPlanImpact, setGoalPlanImpact] =
    useState<GoalPlanImpact | null>(null);
  const dismissedGoalPlanImpactKey = useRef<string | null>(null);
  const [fetchKey, setFetchKey] = useState(0);
  const applyGoalPlanImpact = useCallback((impact: GoalPlanImpact | null) => {
    if (
      impact
      && goalPlanImpactKey(impact) === dismissedGoalPlanImpactKey.current
    ) {
      setGoalPlanImpact(null);
      return;
    }
    setGoalPlanImpact(impact);
  }, []);

  useEffect(() => {
    let cancelled = false;
    // Only show loading skeleton on initial fetch, not on refetches,
    // to avoid unmounting/remounting the Settings page.
    if (fetchKey === 0) setLoading(true);
    apiFetch('/api/settings', { headers: getAuthHeaders() })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<SettingsResponse>;
      })
      .then((data) => {
        if (cancelled) return;
        setConfig(data.config);
        setDisplay(data.display);
        setConnectionStatuses(data.connection_statuses ?? {});
        setPlatformCapabilities(data.platform_capabilities ?? {});
        setPlanDeliveryOptions(planDeliveryOptionsFromResponse(data));
        setAvailableProviders(data.available_providers ?? {});
        setAvailableBases(data.available_bases);
        setEffectiveThresholds(data.effective_thresholds ?? {});
        setDetectedThresholds(data.detected_thresholds ?? {});
        applyGoalPlanImpact(data.goal_plan_impact ?? null);
        setError(null);
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.message);
        setLoading(false);
      });
    return () => { cancelled = true; };
  }, [applyGoalPlanImpact, fetchKey]);

  useEffect(() => {
    const refreshAfterBackground = () => {
      setFetchKey((key) => key + 1);
    };
    window.addEventListener('focus', refreshAfterBackground);
    return () => {
      window.removeEventListener('focus', refreshAfterBackground);
    };
  }, []);

  const updateSettings = async (update: SettingsUpdate) => {
    const res = await apiFetch('/api/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify(update),
    });
    if (!res.ok) {
      let detail = '';
      try {
        const body = await res.json();
        if (body && typeof body === 'object') {
          detail = (body as { detail?: string; message?: string }).detail
            ?? (body as { detail?: string; message?: string }).message
            ?? '';
        }
      } catch { /* response not JSON — fall back to status code */ }
      throw new Error(detail || `HTTP ${res.status}`);
    }
    const data = await res.json() as SettingsUpdateResponse;
    setConfig(data.config);
    setDisplay(data.display);
    setConnectionStatuses(
      data.connection_statuses ?? connectionStatuses,
    );
    setPlatformCapabilities(
      data.platform_capabilities ?? platformCapabilities,
    );
    setPlanDeliveryOptions(planDeliveryOptionsFromResponse(data));
    if (update.goal !== undefined) {
      const impact = data.goal_plan_impact ?? null;
      if (impact) dismissedGoalPlanImpactKey.current = null;
      setGoalPlanImpact(impact);
      void Promise.allSettled([
        queryClient.invalidateQueries({ queryKey: ['/api/goal'] }),
        queryClient.invalidateQueries({
          queryKey: ['/api/plan/generation/capabilities'],
        }),
        queryClient.invalidateQueries({
          queryKey: ['/api/plan/proposals/current'],
        }),
      ]);
    }
    return data;
  };

  const dismissGoalPlanImpact = useCallback(() => {
    setGoalPlanImpact((impact) => {
      if (impact) {
        dismissedGoalPlanImpactKey.current = goalPlanImpactKey(impact);
      }
      return null;
    });
  }, []);
  const refetch = useCallback(() => setFetchKey((k) => k + 1), []);

  return (
    <SettingsContext.Provider
      value={{ config, display, connectionStatuses, platformCapabilities, planDeliveryOptions, availableProviders, availableBases, effectiveThresholds, detectedThresholds, loading, error, goalPlanImpact, updateSettings, dismissGoalPlanImpact, refetch }}
    >
      {children}
    </SettingsContext.Provider>
  );
}

export function useSettings() {
  return useContext(SettingsContext);
}
