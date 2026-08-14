import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8');

test('web declares the shared outdoor 5K endpoint contracts', async () => {
  const [webTypes, miniTypes] = await Promise.all([
    read('../src/types/api.ts'),
    read('../../miniapp/types/api.ts'),
  ]);
  const required = [
    'interface PlanGenerationActions',
    'interface PlanGenerationCapability',
    'interface PlanGenerationCapabilitiesResponse',
    "unsupported_reason: 'no_accepted_policy' | null",
    'type Outdoor5KWeekday = 0 | 1 | 2 | 3 | 4 | 5 | 6',
    'interface Outdoor5KConstraintsRequest',
    'interface Outdoor5KReadinessRequest',
    'interface Outdoor5KGenerateRequest',
    'interface Outdoor5KRegenerateRequest',
    'interface Outdoor5KOutcomeResponse',
    'interface Outdoor5KReadinessResponse',
    'interface Outdoor5KAlternativesResponse',
    'interface Outdoor5KProposalResponse',
    'source_revision: string',
    'result: Outdoor5KOutcomeResponse',
    'proposal: AdaptivePlanProposal | null',
    'replayed: boolean',
    'reassessment_dates: string[]',
  ];

  for (const marker of required) {
    const expression = new RegExp(marker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
    assert.match(webTypes, expression);
    assert.match(miniTypes, expression);
  }
});
