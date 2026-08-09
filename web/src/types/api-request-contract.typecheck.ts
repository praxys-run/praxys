import type {
  ContextPilotRunRequest,
  PersonalContextAiConsentRequest,
  PersonalContextDraftRequest,
} from './api';

const payload = {
  category: 'less_time',
  fields: {},
} as const;

const unlinkedDraft: PersonalContextDraftRequest = {
  kind: 'temporary_constraint',
  purpose: 'plan_adjustment',
  payload,
};
const linkedDraft: PersonalContextDraftRequest = {
  kind: 'execution_explanation',
  purpose: 'execution_interpretation',
  payload,
  linked_subject_type: 'workout',
  linked_subject_id: 'workout-id',
};
// @ts-expect-error Linked subject type and id must be supplied together.
const incompleteLinkedDraft: PersonalContextDraftRequest = {
  kind: 'execution_explanation',
  purpose: 'execution_interpretation',
  payload,
  linked_subject_type: 'workout',
};

const syntheticPilot: ContextPilotRunRequest = {
  source: 'synthetic',
  scenario_id: 'availability-suggestion',
};
const optedInPilot: ContextPilotRunRequest = {
  source: 'opt_in',
  purpose: 'plan_adjustment',
  confirmed_opt_in: true,
  allow_ai: false,
};
// @ts-expect-error Synthetic runs cannot accept opted-in context fields.
const invalidSyntheticPilot: ContextPilotRunRequest = {
  source: 'synthetic',
  scenario_id: 'availability-suggestion',
  allow_ai: true,
};
const unconfirmedPilot: ContextPilotRunRequest = {
  source: 'opt_in',
  purpose: 'plan_adjustment',
  // @ts-expect-error Opted-in runs require an explicit true confirmation.
  confirmed_opt_in: false,
};

const grantedAiConsent: PersonalContextAiConsentRequest = {
  expected_version: 1,
  decision: 'granted',
  provider: 'azure_openai',
  consent_text_version: 'ai-v1',
  client: 'web',
};
const deniedAiConsent: PersonalContextAiConsentRequest = {
  expected_version: 1,
  decision: 'denied',
  consent_text_version: 'ai-v1',
  client: 'web',
};
const withdrawnAiConsent: PersonalContextAiConsentRequest = {
  expected_version: 1,
  decision: 'withdrawn',
  provider: null,
  consent_text_version: 'ai-v1',
  client: 'miniapp',
};
// @ts-expect-error Granted consent requires the Azure OpenAI provider.
const invalidGrantedAiConsent: PersonalContextAiConsentRequest = {
  expected_version: 1,
  decision: 'granted',
  consent_text_version: 'ai-v1',
  client: 'web',
};

void [
  unlinkedDraft,
  linkedDraft,
  incompleteLinkedDraft,
  syntheticPilot,
  optedInPilot,
  invalidSyntheticPilot,
  unconfirmedPilot,
  grantedAiConsent,
  deniedAiConsent,
  withdrawnAiConsent,
  invalidGrantedAiConsent,
];
