function syntheticDFARequest(options) {
  const fixture = getApp().__dfaVerification;
  const response = (data, statusCode = 200) => ({statusCode, data, header: {'Cache-Control': 'private, no-store'}});
  if (!fixture) return response({detail: 'SYNTHETIC_FIXTURE_NOT_READY'}, 503);
  const path = String(options.url || '').replace(/^https?:\/\/[^/]+/, '').split('?')[0];
  const method = options.method || 'GET';
  const activity = 'dfa-synthetic-running';
  const prefix = '/api/activities/' + activity + '/dfa-alpha1';
  const start = Date.UTC(2026, 8, 27, 0, 0, 0);
  const input = (index) => ({provider: 'garmin', user_id: 'synthetic', account_id: 'synthetic', activity_id: activity, snapshot_id: 'snapshot-' + index, parse_id: 'parse-' + index, sha256: 'a'.repeat(64), parser_version: 'fitdecode-0.11.0/praxys-1'});
  const proof = () => ({id: 'synthetic-proof', snapshot_id: input(fixture.selected).snapshot_id, parse_id: input(fixture.selected).parse_id, sensor_ref: 's'.repeat(32), sensor_label: 'Polar H10', statement_version: 'dfa-source-attestation-v1', created_at: '2026-09-27T00:00:00', source_assurance: 'user_confirmed'});
  const base = (status, phase) => ({id: 'synthetic-run', phase, status, generation: fixture.generation, freshness: fixture.state === 'withdrawn' ? 'stale' : 'current', progress: status, error_code: status === 'unavailable' ? 'source_unsupported' : null, created_at: new Date().toISOString(), completed_at: null, expires_at: null, method_version: 'dfa-alpha1-raw120-v1', science_contract_digest: 'sha256:' + 'a'.repeat(64), snapshot_id: input(fixture.selected).snapshot_id, parse_id: input(fixture.selected).parse_id, source_confirmation_id: phase === 'compute' ? 'synthetic-proof' : null, result_revision: phase === 'compute' ? 'synthetic-result' : null});
  const prepared = () => ({...base('awaiting_source_confirmation', 'prepare'), sensors: [{sensor_ref: 's'.repeat(32), label: 'Polar H10', rule_fingerprint: 'r'.repeat(64)}], evidence_digest: 'e'.repeat(64), statement_version: 'dfa-source-attestation-v1'});
  const fullResult = () => {
    const blocks = [[start, start + 1800000], [start + 1820000, start + 3720000]];
    const windows = [];
    for (let block = 0; block < blocks.length; block++) {
      for (let end = blocks[block][0] + 120000; end <= blocks[block][1]; end += 5000) {
        const index = windows.length, gap = fixture.state === 'no_valid' || (index % 120 >= 35 && index % 120 < 48);
        windows.push({index, block, start_ms: end - 120000, end_ms: end, alpha1: gap ? null : 0.92 + 0.15 * Math.sin(index / 11), r2: gap ? null : 0.94, hr_bpm: gap ? null : 145 + 7 * Math.sin(index / 20), reasons: gap ? ['rr_suspect'] : [], flags: [], beat_count: 288, coverage_ms: 119400, offset_ms: 0, offset_width_ms: 2000, rr_index_start: index * 12, rr_index_end: index * 12 + 287});
      }
    }
    const valid = windows.filter(w => w.alpha1 !== null), support = [];
    for (const w of valid) {
      const prior = support[support.length - 1];
      if (prior && w.start_ms <= prior[1]) prior[1] = Math.max(prior[1], w.end_ms);
      else support.push([w.start_ms, w.end_ms]);
    }
    return {...base('complete', 'compute'), source_assurance: 'user_confirmed', time_alignment: 'estimated', availability: valid.length ? 'available' : 'no_valid_windows', summary: {scheduled_windows: windows.length, valid_windows: valid.length, window_success_rate: valid.length / windows.length, supported_time_ratio: support.reduce((sum, [a, b]) => sum + b - a, 0) / 3700000, short_blocks: 0, excluded_reasons: {rr_suspect: windows.length - valid.length}}, navigation: {start_ms: start, end_ms: start + 3720000, timer_blocks: blocks, support, page_size: 120, page_anchors: windows.filter((_, i) => i % 120 === 0).map(w => ({offset: w.index, time_ms: w.end_ms}))}, windows};
  };
  if (path === '/api/history') return response({activities: [{activity_id: activity, date: '2026-09-27', activity_type: 'running', distance_km: 10, duration_sec: 3720, source: 'garmin', splits: []}], total: 1});
  if (!path.startsWith(prefix)) return response({detail: 'SYNTHETIC_UNHANDLED_ROUTE'}, 503);
  fixture.requests.push({method, path}); // Fixed synthetic paths only; no headers or credentials.
  if (method === 'DELETE') { fixture.proof = null; fixture.run = null; fixture.state = 'prepare'; return response({deleted: true}); }
  if (path.endsWith('/source-confirmations') && method === 'POST') { fixture.proof = proof(); return response(fixture.proof); }
  if (path.endsWith('/cancel') && method === 'POST') { fixture.generation++; fixture.run = base('cancelled', 'compute'); return response(fixture.run); }
  if (path === prefix && method === 'POST') {
    const body = typeof options.data === 'string' ? JSON.parse(options.data) : options.data || {};
    fixture.selected = body.input && body.input.snapshot_id === 'snapshot-1' ? 1 : 0;
    fixture.polls = 0;
    fixture.run = base('queued', body.source_confirmation_id ? 'compute' : 'prepare');
    return response(fixture.run, 202);
  }
  if (path === prefix) {
    if (['complete', 'no_valid', 'expired', 'withdrawn'].includes(fixture.state) && !fixture.proof) fixture.proof = proof();
    if (['complete', 'no_valid'].includes(fixture.state) && !fixture.run) fixture.run = base('complete', 'compute');
    if (fixture.state === 'withdrawn' && !fixture.run) fixture.run = base('running', 'compute');
    return response({activity_id: activity, inputs: (fixture.state === 'multiple' ? [0, 1] : [0]).map(i => ({input: input(i), created_at: '2026-09-27T00:00:00'})), catalog_revision: 'c'.repeat(64), source_confirmations: fixture.proof ? [fixture.proof] : [], latest_run: fixture.run, availability: 'ready', policy_active: true, processing_authorized: fixture.state !== 'withdrawn', statement_version: 'dfa-source-attestation-v1'});
  }
  const offset = Number((String(options.url).match(/[?&]offset=(\d+)/) || [])[1] || 0);
  if (path.endsWith('/context')) return response({result_revision: 'synthetic-result', samples_revision: '1', overlay_version: 'held2s-support80-v1', offset, windows: fullResult().windows.slice(offset, offset + 120).map(w => ({index: w.index, power_watts: w.index % 120 < 75 ? 250 : null, pace_sec_km: 300}))});
  if (fixture.run && ['queued', 'running'].includes(fixture.run.status) && fixture.state !== 'withdrawn') {
    fixture.polls++;
    fixture.run = fixture.polls < 2 ? base('running', fixture.run.phase) : fixture.state === 'unavailable' ? base('unavailable', 'prepare') : fixture.run.phase === 'prepare' ? prepared() : base('complete', 'compute');
  }
  if (fixture.run && fixture.run.status === 'complete') {
    const result = fullResult();
    return response({...result, windows: result.windows.slice(offset, offset + 120), page: {offset, limit: 120, total: result.windows.length, next_offset: offset + 120 < result.windows.length ? offset + 120 : null}});
  }
  return fixture.run ? response(fixture.run) : response({detail: 'SYNTHETIC_RUN_NOT_FOUND'}, 404);
}
