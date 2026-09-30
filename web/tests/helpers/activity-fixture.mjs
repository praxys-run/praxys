import { readFileSync } from 'node:fs';

export function activityFixture(state = 'normal') {
  const source = readFileSync(new URL('../../../tests/fixtures/activity-detail/native-request-mock.js', import.meta.url), 'utf8');
  const request = new Function('getApp', `return (${source});`)(() => ({
    __activityDetailVerification: { state, requests: [] },
  }));
  const detail = request({ url: '/api/history/native-synthetic-running/detail' }).data;
  detail.activity.source = 'garmin';
  detail.activity.environment_source = 'garmin_activity_weather';
  detail.activity.temperature_c = 18;
  detail.activity.relative_humidity_pct = 60;
  detail.activity.rss = 42;
  detail.activity.cp_estimate = 250;
  detail.sample_sources = detail.samples.length ? ['stryd'] : [];
  detail.samples.forEach((sample) => { sample.source = 'stryd'; });
  return detail;
}

export function allMetricFixture() {
  const detail = activityFixture();
  detail.samples.forEach((sample, index) => Object.assign(sample, {
    cadence_spm: 170 + index % 5, speed_ms: 2.5 + index % 3 / 10, altitude_m: 10 + index,
    grade_pct: index % 7 - 3, temperature_c: 18 + index % 3, ground_time_ms: 240 + index % 8,
    oscillation_mm: 80 + index % 4, vertical_ratio: 7, leg_spring_kn_m: 9 + index % 4 / 10,
    form_power_watts: 60 + index % 5, respiration_rate: 30 + index % 4,
  }));
  return detail;
}
