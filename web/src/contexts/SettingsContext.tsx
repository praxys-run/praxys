import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import type { ReactNode } from 'react';
import type { DisplayConfig, ExperimentalPlanDeliveryResponse, SettingsConfig, SettingsResponse, SettingsUpdate, SettingsUpdateResponse, TrainingBase, ThresholdValue, DetectedThreshold } from '../types/api';
import { API_BASE, getAuthHeaders } from '../hooks/useApi';

interface SettingsContextValue {
  config: SettingsConfig | null;
  display: DisplayConfig | null;
  connectionStatuses: SettingsResponse['connection_statuses'];
  platformCapabilities: SettingsResponse['platform_capabilities'];
  experimentalPlanDelivery: ExperimentalPlanDeliveryResponse;
  availableProviders: SettingsResponse['available_providers'];
  availableBases: TrainingBase[];
  effectiveThresholds: Record<string, ThresholdValue>;
  detectedThresholds: Record<string, DetectedThreshold>;
  loading: boolean;
  error: string | null;
  updateSettings: (update: SettingsUpdate) => Promise<void>;
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
  experimentalPlanDelivery: {},
  availableProviders: {},
  availableBases: ['power', 'hr', 'pace'],
  effectiveThresholds: {},
  detectedThresholds: {},
  loading: true,
  error: null,
  updateSettings: async () => {},
  refetch: () => {},
});

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<SettingsConfig | null>(null);
  const [display, setDisplay] = useState<DisplayConfig>(DEFAULT_DISPLAY);
  const [connectionStatuses, setConnectionStatuses] = useState<
    SettingsResponse['connection_statuses']
  >({});
  const [platformCapabilities, setPlatformCapabilities] = useState<
    SettingsResponse['platform_capabilities']
  >({});
  const [experimentalPlanDelivery, setExperimentalPlanDelivery] = useState<
    ExperimentalPlanDeliveryResponse
  >({});
  const [availableProviders, setAvailableProviders] = useState<
    SettingsResponse['available_providers']
  >({});
  const [availableBases, setAvailableBases] = useState<TrainingBase[]>(['power', 'hr', 'pace']);
  const [effectiveThresholds, setEffectiveThresholds] = useState<Record<string, ThresholdValue>>({});
  const [detectedThresholds, setDetectedThresholds] = useState<Record<string, DetectedThreshold>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fetchKey, setFetchKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    // Only show loading skeleton on initial fetch, not on refetches,
    // to avoid unmounting/remounting the Settings page.
    if (fetchKey === 0) setLoading(true);
    fetch(`${API_BASE}/api/settings`, { headers: getAuthHeaders() })
      .then((r) => {
        if (r.status === 401) {
          window.location.href = '/login';
          throw new Error('Unauthorized');
        }
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<SettingsResponse>;
      })
      .then((data) => {
        if (cancelled) return;
        setConfig(data.config);
        setDisplay(data.display);
        setConnectionStatuses(data.connection_statuses ?? {});
        setPlatformCapabilities(data.platform_capabilities ?? {});
        setExperimentalPlanDelivery(data.experimental_plan_delivery ?? {});
        setAvailableProviders(data.available_providers ?? {});
        setAvailableBases(data.available_bases);
        setEffectiveThresholds(data.effective_thresholds ?? {});
        setDetectedThresholds(data.detected_thresholds ?? {});
        setError(null);
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.message);
        setLoading(false);
      });
    return () => { cancelled = true; };
  }, [fetchKey]);

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
    const res = await fetch(`${API_BASE}/api/settings`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify(update),
    });
    if (res.status === 401) {
      window.location.href = '/login';
      throw new Error('Unauthorized');
    }
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
    const requestedGarminExperiment = (
      update.experimental_plan_delivery?.garmin
    );
    if (
      requestedGarminExperiment !== undefined
      && data.experimental_plan_delivery?.garmin?.enabled
      !== requestedGarminExperiment
    ) {
      throw new Error(
        'The active server did not confirm the Garmin delivery change. Retry shortly.',
      );
    }
    setConfig(data.config);
    setDisplay(data.display);
    setConnectionStatuses(
      data.connection_statuses ?? connectionStatuses,
    );
    setPlatformCapabilities(
      data.platform_capabilities ?? platformCapabilities,
    );
    setExperimentalPlanDelivery(
      data.experimental_plan_delivery ?? experimentalPlanDelivery,
    );
  };

  const refetch = useCallback(() => setFetchKey((k) => k + 1), []);

  return (
    <SettingsContext.Provider
      value={{ config, display, connectionStatuses, platformCapabilities, experimentalPlanDelivery, availableProviders, availableBases, effectiveThresholds, detectedThresholds, loading, error, updateSettings, refetch }}
    >
      {children}
    </SettingsContext.Provider>
  );
}

export function useSettings() {
  return useContext(SettingsContext);
}
