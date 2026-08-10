interface WetBulbDomainBin {
  lower_wet_bulb_c: number;
  upper_wet_bulb_c: number;
}

interface WetBulbPoint {
  wet_bulb_c: number;
}

export function getWetBulbChartDomain(
  supportBins: WetBulbDomainBin[],
): [number, number] | null {
  if (supportBins.length === 0) return null;
  return [
    Math.min(...supportBins.map((bin) => bin.lower_wet_bulb_c)),
    Math.max(...supportBins.map((bin) => bin.upper_wet_bulb_c)),
  ];
}

export function getWetBulbPointDomain(
  points: WetBulbPoint[],
): [number, number] | null {
  if (points.length === 0) return null;
  const values = points.map((point) => point.wet_bulb_c);
  return [Math.min(...values), Math.max(...values)];
}

export function getMarkerLabelPosition(
  value: number,
  domain: [number, number],
): 'insideTopLeft' | 'insideTopRight' {
  return value > (domain[0] + domain[1]) / 2
    ? 'insideTopRight'
    : 'insideTopLeft';
}
