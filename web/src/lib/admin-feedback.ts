import type {
  FeedbackPublicationConsentReceipt,
  FeedbackPublicationStatus,
} from '@/types/api';

type AdminFeedbackConsentContext = {
  publication_status: FeedbackPublicationStatus;
  publication_consent_receipt: FeedbackPublicationConsentReceipt;
  github_issue_number: number | null;
  github_issue_url: string | null;
};

export type AdminFeedbackConsentGuidance = Exclude<
  FeedbackPublicationConsentReceipt,
  'current'
>;

/**
 * Return the receipt reason that may explain a private, unlinked row.
 * Publication state and issue evidence take precedence; unknown values do not
 * produce recovery guidance.
 */
export function adminFeedbackConsentGuidance(
  item: AdminFeedbackConsentContext,
): AdminFeedbackConsentGuidance | null {
  if (item.publication_status !== 'private') return null;
  if (item.github_issue_number !== null || item.github_issue_url !== null) {
    return null;
  }
  if (
    item.publication_consent_receipt === 'legacy'
    || item.publication_consent_receipt === 'not_granted'
    || item.publication_consent_receipt === 'invalid'
  ) {
    return item.publication_consent_receipt;
  }
  return null;
}
