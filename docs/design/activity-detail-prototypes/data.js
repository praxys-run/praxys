export const metricDefinitions = {
  power: { label: '功率', unit: 'W', group: '强度', decimals: 0, tone: 'power' },
  heartRate: { label: '心率', unit: 'bpm', group: '强度', decimals: 0, tone: 'heart' },
  pace: { label: '配速', unit: '/km', group: '节奏', decimals: 0, tone: 'pace' },
  cadence: { label: '步频', unit: 'spm', group: '节奏', decimals: 0, tone: 'cadence' },
  speed: { label: '速度', unit: 'm/s', group: '节奏', decimals: 2, tone: 'speed' },
  altitude: { label: '海拔', unit: 'm', group: '地形', decimals: 0, tone: 'altitude' },
  grade: { label: '坡度', unit: '%', group: '地形', decimals: 1, tone: 'grade' },
  temperature: { label: '温度', unit: '°C', group: '环境', decimals: 1, tone: 'temperature' },
  groundTime: { label: '触地时间', unit: 'ms', group: '跑姿', decimals: 0, tone: 'dynamics' },
  oscillation: { label: '垂直振幅', unit: 'mm', group: '跑姿', decimals: 0, tone: 'dynamics' },
  verticalRatio: { label: '垂直比', unit: '%', group: '跑姿', decimals: 1, tone: 'dynamics' },
  legSpring: { label: '腿部弹簧刚度', unit: 'kN/m', group: '跑姿', decimals: 1, tone: 'dynamics' },
  formPower: { label: '姿态功率', unit: 'W', group: '跑姿', decimals: 0, tone: 'dynamics' },
  respiration: { label: '呼吸频率', unit: '次/分', group: '生理', decimals: 0, tone: 'respiration' },
};

function makeSplits(segments) {
  let elapsed = 0;
  return segments.map((segment, index) => {
    const split = { ...segment, index, start: elapsed, end: elapsed + segment.seconds };
    elapsed = split.end;
    return split;
  });
}

const fullSplits = makeSplits([
  { title: '进入节奏', distance: 3.1, seconds: 980, pace: '5:16', power: 205, heartRate: 130 },
  { title: '保持巡航', distance: 3.1, seconds: 947, pace: '5:05', power: 218, heartRate: 139 },
  { title: '向前推进', distance: 3.1, seconds: 923, pace: '4:58', power: 234, heartRate: 148 },
  { title: '收尾阶段', distance: 3.1, seconds: 884, pace: '4:45', power: 250, heartRate: 157 },
]);

const sparseSplits = makeSplits([
  { title: '前段', distance: 2.0, seconds: 840, pace: '7:00', power: null, heartRate: 128 },
  { title: '中段', distance: 2.0, seconds: 820, pace: '6:50', power: null, heartRate: 136 },
  { title: '后段', distance: 2.2, seconds: 860, pace: '6:31', power: null, heartRate: 143 },
]);

function makeDistanceTimeline(laps) {
  const activity = { id: 'full', splits: laps, duration: laps.at(-1).end };
  const timeline = [{ time: 0, distance: 0 }];
  let covered = 0;
  for (const lap of laps) {
    const speeds = Array.from({ length: lap.seconds + 1 }, (_, index) => sampleValue(activity, 'speed', lap.start + index));
    const intervals = speeds.slice(1).map((speed, index) => (speed + speeds[index]) / 2000);
    const unscaledDistance = intervals.reduce((total, distance) => total + distance, 0);
    let lapDistance = 0;
    intervals.forEach((distance, index) => {
      lapDistance += distance / unscaledDistance * lap.distance;
      timeline.push({ time: lap.start + index + 1, distance: covered + lapDistance });
    });
    covered += lap.distance;
  }
  return timeline;
}

function makeDistanceSplits(timeline, laps, totalDistance) {
  function timeAtDistance(distance) {
    if (distance === 0) return 0;
    if (distance >= totalDistance) return timeline.at(-1).time;
    const nextIndex = timeline.findIndex((sample) => sample.distance >= distance);
    if (nextIndex < 1) return timeline.at(-1).time;
    const previous = timeline[nextIndex - 1];
    const next = timeline[nextIndex];
    return previous.time + (distance - previous.distance) / (next.distance - previous.distance) * (next.time - previous.time);
  }

  const boundaries = Array.from({ length: Math.floor(totalDistance) + 1 }, (_, index) => index);
  if (boundaries.at(-1) < totalDistance) boundaries.push(totalDistance);
  return boundaries.slice(1).map((endDistance, index) => {
    const startDistance = boundaries[index];
    const start = timeAtDistance(startDistance);
    const end = timeAtDistance(endDistance);
    const distance = Number((endDistance - startDistance).toFixed(1));
    const weightedAverage = (metric) => {
      const overlapping = laps.map((lap) => ({ seconds: Math.max(0, Math.min(end, lap.end) - Math.max(start, lap.start)), value: lap[metric] }))
        .filter((entry) => entry.seconds > 0 && entry.value != null);
      const coveredSeconds = overlapping.reduce((total, entry) => total + entry.seconds, 0);
      return coveredSeconds ? Math.round(overlapping.reduce((total, entry) => total + entry.seconds * entry.value, 0) / coveredSeconds) : null;
    };
    return {
      index,
      title: `${startDistance}–${Number(endDistance.toFixed(1))} km`,
      distance,
      seconds: end - start,
      start,
      end,
      pace: formatTime((end - start) / distance),
      power: weightedAverage('power'),
      heartRate: weightedAverage('heartRate'),
    };
  });
}

const fullDistanceTimeline = makeDistanceTimeline(fullSplits);

export const scenarios = {
  full: {
    id: 'full',
    label: '多指标活动',
    name: '晨间渐进跑',
    date: '2026年9月14日 · 周一',
    started: '07:02',
    type: '跑步',
    distance: '12.4',
    distanceNumber: 12.4,
    duration: 3734,
    averagePace: '5:01',
    averageHeartRate: '143',
    averagePower: '226',
    elevationGain: '46',
    source: 'Garmin + Stryd',
    sampleDescription: '合成采样 · 约每 30 秒一点 · 有短暂缺口',
    gaps: [{ start: 1040, end: 1115 }, { start: 2510, end: 2595 }],
    splits: fullSplits,
    distanceSplits: makeDistanceSplits(fullDistanceTimeline, fullSplits, 12.4),
    streams: {
      power: { value: '226', source: 'Stryd', coverage: '96%' },
      heartRate: { value: '143', source: 'Garmin', coverage: '96%' },
      pace: { value: '5:01', source: 'Garmin', coverage: '96%' },
      cadence: { value: '174', source: 'Garmin', coverage: '96%' },
      speed: { value: '3.32', source: 'Garmin', coverage: '96%' },
      altitude: { value: '55', source: 'Garmin', coverage: '96%' },
      grade: { value: '0.4', source: 'Garmin', coverage: '96%' },
      temperature: { value: '17.2', source: 'Garmin', coverage: '96%' },
      groundTime: { value: '248', source: 'Stryd', coverage: '96%' },
      oscillation: { value: '78', source: 'Stryd', coverage: '96%' },
      verticalRatio: { value: '8.0', source: 'Stryd', coverage: '96%' },
      legSpring: { value: '10.3', source: 'Stryd', coverage: '96%' },
      formPower: { value: '63', source: 'Stryd', coverage: '96%' },
      respiration: { value: '30', source: 'Garmin', coverage: '96%' },
    },
    summaries: [
      { label: '距离', value: '12.4', unit: 'km', group: '概要', source: 'Garmin' },
      { label: '运动时长', value: '1:02:14', unit: '', group: '概要', source: 'Garmin' },
      { label: '累计爬升', value: '46', unit: 'm', group: '概要', source: 'Garmin' },
      { label: '最大功率', value: '314', unit: 'W', group: '强度', source: 'Stryd' },
      { label: '最高心率', value: '166', unit: 'bpm', group: '强度', source: 'Garmin' },
      { label: 'RSS', value: '74', unit: '', group: '训练记录', source: 'Stryd', description: '跑步训练负荷分数；来源平台的整场汇总，不是逐时曲线。' },
      { label: 'CP 估计', value: '268', unit: 'W', group: '训练记录', source: 'Stryd', description: '临界功率估计；是来源平台的参考值，不是本次平均功率。' },
      { label: '相对湿度', value: '64', unit: '%', group: '环境', source: 'Stryd' },
    ],
  },
  sparse: {
    id: 'sparse',
    label: '采样不完整',
    name: '河边轻松跑',
    date: '2026年9月16日 · 周三',
    started: '06:48',
    type: '跑步',
    distance: '6.2',
    distanceNumber: 6.2,
    duration: 2520,
    averagePace: '6:46',
    averageHeartRate: '136',
    averagePower: null,
    elevationGain: '24',
    source: 'Garmin',
    sampleDescription: '心率采样覆盖约 69% · 中途存在记录缺口',
    reportSampleNote: '中途存在心率记录缺口；曲线不跨缺口补画。',
    gaps: [{ start: 865, end: 1635 }],
    splits: sparseSplits,
    distanceSplits: [],
    streams: { heartRate: { value: '136', source: 'Garmin', coverage: '69%' } },
    summaries: [
      { label: '距离', value: '6.2', unit: 'km', group: '概要', source: 'Garmin' },
      { label: '运动时长', value: '42:00', unit: '', group: '概要', source: 'Garmin' },
      { label: '平均配速', value: '6:46', unit: '/km', group: '节奏', source: 'Garmin' },
      { label: '累计爬升', value: '24', unit: 'm', group: '概要', source: 'Garmin' },
      { label: '最高心率', value: '155', unit: 'bpm', group: '强度', source: 'Garmin' },
    ],
  },
  summary: {
    id: 'summary',
    label: '只有汇总',
    name: '通勤慢跑',
    date: '2026年9月18日 · 周五',
    started: '18:21',
    type: '跑步',
    distance: '4.8',
    distanceNumber: 4.8,
    duration: 1800,
    averagePace: '6:15',
    averageHeartRate: '128',
    averagePower: null,
    elevationGain: '12',
    source: 'Garmin',
    sampleDescription: '此活动未保存逐时采样，不能展示曲线或局部读数',
    gaps: [],
    splits: [],
    distanceSplits: [],
    streams: {},
    summaries: [
      { label: '距离', value: '4.8', unit: 'km', group: '概要', source: 'Garmin' },
      { label: '运动时长', value: '30:00', unit: '', group: '概要', source: 'Garmin' },
      { label: '平均配速', value: '6:15', unit: '/km', group: '节奏', source: 'Garmin' },
      { label: '平均心率', value: '128', unit: 'bpm', group: '强度', source: 'Garmin' },
      { label: '累计爬升', value: '12', unit: 'm', group: '概要', source: 'Garmin' },
    ],
  },
};

const cachedSeries = new Map();

export function formatTime(seconds) {
  const clampedSeconds = Math.max(0, Math.round(seconds));
  const hours = Math.floor(clampedSeconds / 3600);
  const minutes = Math.floor((clampedSeconds % 3600) / 60);
  const remaining = clampedSeconds % 60;
  return hours
    ? `${hours}:${String(minutes).padStart(2, '0')}:${String(remaining).padStart(2, '0')}`
    : `${minutes}:${String(remaining).padStart(2, '0')}`;
}

export function formatReading(metricKey, value) {
  if (value == null) return '—';
  if (metricKey === 'pace') return formatTime(value);
  const definition = metricDefinitions[metricKey];
  return value.toFixed(definition?.decimals ?? 0);
}

function sampleValue(activity, metricKey, elapsedSeconds) {
  const split = activity.splits.find((entry) => elapsedSeconds <= entry.end) ?? activity.splits.at(-1);
  const splitIndex = split?.index ?? 0;
  const progress = elapsedSeconds / activity.duration;
  const ripple = Math.sin(progress * 48) * 0.64 + Math.sin(progress * 137) * 0.25;
  const rolling = Math.sin(progress * 17) * 0.8 + Math.cos(progress * 31) * 0.2;

  if (activity.id === 'sparse') return (split?.heartRate ?? 136) + ripple * 4 + rolling * 2;

  switch (metricKey) {
    case 'power': return [205, 218, 234, 250][splitIndex] + ripple * 12 + rolling * 7;
    case 'heartRate': {
      const baseline = [130, 139, 148, 157];
      const previous = baseline[Math.max(0, splitIndex - 1)];
      const rise = Math.min(1, Math.max(0, elapsedSeconds - (split?.start ?? 0)) / 175);
      return previous + (baseline[splitIndex] - previous) * rise + progress * 2.6 + Math.sin(progress * 19 - 0.7) * 1.7 + Math.cos(progress * 9) * 0.9;
    }
    case 'pace': return [316, 307, 297, 284][splitIndex] + ripple * 9 + rolling * 4;
    case 'cadence': return [169, 172, 174, 178][splitIndex] + ripple * 2 + rolling;
    case 'speed': return 1000 / ([316, 307, 297, 284][splitIndex] + ripple * 9 + rolling * 4);
    case 'altitude': return 42 + progress * 26 + Math.sin(progress * 11) * 6 + rolling * 1.2;
    case 'grade': return Math.sin(progress * 11) * 1.4 + rolling * 0.6;
    case 'temperature': return 16.4 + progress * 1.7 + rolling * 0.25;
    case 'groundTime': return [257, 251, 246, 239][splitIndex] + ripple * 4;
    case 'oscillation': return [80, 79, 78, 75][splitIndex] + ripple * 2;
    case 'verticalRatio': return [8.2, 8.1, 7.9, 7.7][splitIndex] + ripple * 0.16;
    case 'legSpring': return [10.0, 10.2, 10.4, 10.6][splitIndex] + ripple * 0.2;
    case 'formPower': return [60, 62, 64, 66][splitIndex] + ripple * 3;
    case 'respiration': return [26, 28, 30, 34][splitIndex] + ripple * 1.5;
    default: return null;
  }
}

export function getSeries(activity, metricKey) {
  if (!activity.streams[metricKey]) return [];
  const cacheKey = `${activity.id}:${metricKey}`;
  if (cachedSeries.has(cacheKey)) return cachedSeries.get(cacheKey);
  const points = Array.from({ length: 145 }, (_, index) => {
    const time = activity.duration * index / 144;
    const missing = activity.gaps.some((gap) => time >= gap.start && time <= gap.end);
    return { time, value: missing ? null : sampleValue(activity, metricKey, time) };
  });
  cachedSeries.set(cacheKey, points);
  return points;
}

export function readingAt(activity, metricKey, time) {
  const series = getSeries(activity, metricKey);
  if (!series.length) return null;
  if (activity.gaps.some((gap) => time >= gap.start && time <= gap.end)) return null;
  const nearest = series.reduce((best, point) => (
    Math.abs(point.time - time) < Math.abs(best.time - time) ? point : best
  ));
  return nearest.value;
}

export function splitAt(activity, time, mode = 'laps') {
  const splits = mode === 'distance' ? activity.distanceSplits : activity.splits;
  return splits.find((split) => time >= split.start && time < split.end)
    ?? (time === activity.duration ? splits.at(-1) ?? null : null);
}
