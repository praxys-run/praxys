function syntheticActivityDetailRequest(options) {
  const response = (data, statusCode = 200) => ({ statusCode, data, header: { 'Cache-Control': 'private, no-store' } });
  const fixture = getApp().__activityDetailVerification;
  if (!fixture) return response({ detail: 'SYNTHETIC_FIXTURE_NOT_READY' }, 503);
  const path = String(options.url || '').replace(/^https?:\/\/[^/]+/, '').split('?')[0];
  const method = options.method || 'GET';
  if (method !== 'GET' || path !== '/api/history/native-synthetic-running/detail') {
    return response({ detail: 'SYNTHETIC_UNHANDLED_ROUTE' }, 503);
  }
  fixture.requests.push({ method, path });
  if (fixture.state === 'not_found') return response({ detail: 'Not found' }, 404);
  if (fixture.state === 'server_error') return response({ detail: 'Synthetic service unavailable' }, 503);
  if (fixture.state === 'network_error') throw new Error('request:fail synthetic offline');

  const split = (number, distance, duration, power, heart) => ({
    split_num: number,
    distance_km: distance,
    duration_sec: duration,
    avg_power: power,
    avg_hr: heart,
    max_hr: heart + 12,
    avg_pace_min_km: '6:40',
    power_source: 'synthetic',
  });
  const activity = {
    activity_id: 'native-synthetic-running',
    date: '2026-09-27',
    source: 'synthetic',
    start_time: { state: 'available', reason_codes: [], utc: '2026-09-27T08:00:00Z', timezone: 'UTC', provenance: 'activity_start_epoch' },
    activity_type: 'running',
    distance_km: 3.3,
    duration_sec: 1320,
    temperature_c: null,
    relative_humidity_pct: null,
    environment_source: null,
    avg_power: 234,
    max_power: 262,
    avg_hr: 147,
    max_hr: 162,
    avg_pace_min_km: '6:40',
    elevation_gain_m: 12,
    rss: null,
    cp_estimate: null,
    environment: { state: 'unavailable', reason_codes: [], model_version: '', science_decision_id: '', temperature_c: null, relative_humidity_pct: null, source: null, wet_bulb_c: null, wet_bulb_method: null, science_sources: [], limitations: [] },
    sample_coverage: {
      state: 'available', reason_codes: [], sample_count: 45, observed_duration_sec: 1320,
      activity_duration_sec: 1320, sample_coverage_ratio: 1, power_duration_sec: 1320,
      power_coverage_ratio: 1, heart_rate_duration_sec: 1320, heart_rate_coverage_ratio: 1,
      gap_count: 0,
    },
    provenance: {
      activity_provider: 'synthetic', sample_providers: ['synthetic'],
      power: { state: 'available', reason_codes: [], providers: ['synthetic'], basis: 'samples' },
      heart_rate: { state: 'available', reason_codes: [], providers: ['synthetic'], basis: 'samples' },
    },
    splits: [split(1, 1.65, 660, 226, 142), split(2, 1.65, 660, 242, 152)],
  };
  const sample = (index, gap = false) => ({
    offset_sec: index * 30,
    source: 'synthetic',
    power_watts: 232 + Math.round(18 * Math.sin(index / 4)),
    hr_bpm: 140 + Math.round(10 * Math.sin(index / 8)),
    pace_sec_km: 400 + Math.round(17 * Math.cos(index / 6)),
    cadence_spm: null, speed_ms: null, altitude_m: null, grade_pct: null,
    temperature_c: null, ground_time_ms: null, oscillation_mm: null,
    vertical_ratio: null, leg_spring_kn_m: null, form_power_watts: null,
    respiration_rate: null,
    power_watts_break: gap, hr_bpm_break: gap, pace_sec_km_break: gap,
    cadence_spm_break: false, speed_ms_break: false, altitude_m_break: false,
    grade_pct_break: false, temperature_c_break: false, ground_time_ms_break: false,
    oscillation_mm_break: false, vertical_ratio_break: false,
    leg_spring_kn_m_break: false, form_power_watts_break: false,
    respiration_rate_break: false,
  });
  let samples = Array.from({ length: 45 }, (_, index) => sample(index));
  if (fixture.state === 'sparse') {
    samples = [0, 1, 2, 14, 15, 16, 28, 29, 44].map((index) => sample(index, [14, 28, 44].includes(index)));
    samples[4].hr_bpm = null;
    samples[7].power_watts = null;
    activity.sample_coverage = { ...activity.sample_coverage,
      state: 'partial', sample_count: samples.length, observed_duration_sec: 240,
      sample_coverage_ratio: 0.18, power_duration_sec: 180, power_coverage_ratio: 0.14,
      heart_rate_duration_sec: 210, heart_rate_coverage_ratio: 0.16, gap_count: 3 };
  }
  if (fixture.state === 'single_metric' || fixture.state === 'distance_only') {
    samples = samples.map((entry) => ({ ...entry,
      power_watts: null, pace_sec_km: null,
      hr_bpm: fixture.state === 'distance_only' ? null : entry.hr_bpm }));
  }
  if (fixture.state === 'no_samples') samples = [];
  if (fixture.state === 'no_samples' || fixture.state === 'distance_only') {
    activity.sample_coverage = { ...activity.sample_coverage,
      state: 'unavailable', sample_count: samples.length,
      power_duration_sec: 0, power_coverage_ratio: 0,
      heart_rate_duration_sec: 0, heart_rate_coverage_ratio: 0 };
  }
  const kilometerSplits = [
    { split_num: 1, start_offset_sec: 0, end_offset_sec: 390, distance_km: 1, duration_sec: 390, pace_sec_km: 390 },
    { split_num: 2, start_offset_sec: 390, end_offset_sec: 810, distance_km: 1, duration_sec: 420, pace_sec_km: 420 },
    { split_num: 3, start_offset_sec: 810, end_offset_sec: 1200, distance_km: 1, duration_sec: 390, pace_sec_km: 390 },
    { split_num: 4, start_offset_sec: 1200, end_offset_sec: 1320, distance_km: 0.3, duration_sec: 120, pace_sec_km: 400 },
  ];
  return response({
    activity,
    training_base: 'power',
    samples,
    sample_count: samples.length,
    sample_sources: samples.length ? ['synthetic'] : [],
    time_origin: samples.length ? 'activity_start' : 'none',
    kilometer_splits: fixture.state === 'sparse' || fixture.state === 'no_samples' ? [] : kilometerSplits,
    kilometer_unavailable_reason: fixture.state === 'sparse' ? 'distance_trace_incomplete'
      : fixture.state === 'no_samples' ? 'samples_unavailable' : null,
    privacy: { gps_included: false, raw_distance_trace_included: false },
  });
}
