export const FEEDBACK_PUBLICATION_CONSENT_VERSION =
  "feedback-publication-v1" as const;

export type FeedbackPublicationConsent =
  | {
      external_publication_consent: true;
      external_publication_consent_version:
        typeof FEEDBACK_PUBLICATION_CONSENT_VERSION;
    }
  | {
      external_publication_consent: false;
    };

/** Build the exact per-submission publication contract; false stays private. */
export function feedbackPublicationConsent(
  publishExternally: boolean,
): FeedbackPublicationConsent {
  if (!publishExternally) {
    return { external_publication_consent: false };
  }
  return {
    external_publication_consent: true,
    external_publication_consent_version:
      FEEDBACK_PUBLICATION_CONSENT_VERSION,
  };
}
