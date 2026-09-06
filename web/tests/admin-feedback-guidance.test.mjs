import assert from "node:assert/strict";
import test from "node:test";

import { adminFeedbackConsentGuidance } from "../src/lib/admin-feedback.ts";

const privateUnlinked = {
  publication_status: "private",
  publication_consent_receipt: "legacy",
  github_issue_number: null,
  github_issue_url: null,
};

test("private unlinked non-current receipts receive bounded guidance", () => {
  assert.equal(adminFeedbackConsentGuidance(privateUnlinked), "legacy");
  assert.equal(
    adminFeedbackConsentGuidance({
      ...privateUnlinked,
      publication_consent_receipt: "not_granted",
    }),
    "not_granted",
  );
  assert.equal(
    adminFeedbackConsentGuidance({
      ...privateUnlinked,
      publication_consent_receipt: "invalid",
    }),
    "invalid",
  );
  assert.equal(
    adminFeedbackConsentGuidance({
      ...privateUnlinked,
      publication_consent_receipt: "current",
    }),
    null,
  );
});

test("publication state and issue evidence suppress new-submission guidance", () => {
  for (const publicationStatus of [
    "queued",
    "published",
    "manual_required",
    "unknown",
    "unavailable",
  ]) {
    assert.equal(
      adminFeedbackConsentGuidance({
        ...privateUnlinked,
        publication_status: publicationStatus,
      }),
      null,
    );
  }

  assert.equal(
    adminFeedbackConsentGuidance({
      ...privateUnlinked,
      github_issue_number: 801,
    }),
    null,
  );
  assert.equal(
    adminFeedbackConsentGuidance({
      ...privateUnlinked,
      github_issue_url: "https://github.com/praxys-run/praxys/issues/801",
    }),
    null,
  );
});

test("unknown and malformed runtime values fail closed", () => {
  assert.equal(
    adminFeedbackConsentGuidance({
      ...privateUnlinked,
      publication_status: "unknown",
      github_issue_number: 802,
      github_issue_url: null,
    }),
    null,
  );
  assert.equal(
    adminFeedbackConsentGuidance({
      ...privateUnlinked,
      publication_consent_receipt: "future-version",
    }),
    null,
  );
  assert.equal(
    adminFeedbackConsentGuidance({
      ...privateUnlinked,
      publication_status: "future-status",
    }),
    null,
  );
});
