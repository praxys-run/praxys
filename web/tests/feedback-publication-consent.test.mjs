import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  FEEDBACK_PUBLICATION_CONSENT_VERSION as WEB_VERSION,
  feedbackPublicationConsent as webConsent,
} from "../src/lib/feedback.ts";
import {
  FEEDBACK_PUBLICATION_CONSENT_VERSION as MINIAPP_VERSION,
  feedbackPublicationConsent as miniappConsent,
} from "../../miniapp/utils/feedback.ts";

const read = (path) => readFile(new URL(path, import.meta.url), "utf8");

test("feedback publication is private by default on both clients", () => {
  const expected = { external_publication_consent: false };
  assert.deepEqual(webConsent(false), expected);
  assert.deepEqual(miniappConsent(false), expected);
  assert.equal("external_publication_consent_version" in webConsent(false), false);
  assert.equal("external_publication_consent_version" in miniappConsent(false), false);
});

test("checked publication sends the exact backend consent contract", async () => {
  const expected = {
    external_publication_consent: true,
    external_publication_consent_version: "feedback-publication-v1",
  };
  assert.equal(WEB_VERSION, MINIAPP_VERSION);
  assert.deepEqual(webConsent(true), expected);
  assert.deepEqual(miniappConsent(true), expected);

  const backend = await read("../../api/optional_processing.py");
  assert.match(
    backend,
    /FEEDBACK_PUBLICATION_CONSENT_VERSION = "feedback-publication-v1"/,
  );
});

test("web and Miniapp render explicit unchecked publication controls", async () => {
  const [web, miniapp, miniappLogic, webTypes, miniappTypes] = await Promise.all([
    read("../src/components/FeedbackDialog.tsx"),
    read("../../miniapp/pages/settings/index.wxml"),
    read("../../miniapp/pages/settings/index.ts"),
    read("../src/types/api.ts"),
    read("../../miniapp/types/api.ts"),
  ]);
  const label = "Publish a scrubbed text summary to Praxys’s external issue tracker";
  const helper = "Optional. Praxys removes personal details before publication. Screenshots always remain private. You can send feedback without allowing publication.";

  assert.equal(web.includes(label), true);
  assert.equal(web.split(/\s+/).join(' ').includes(helper), true);
  assert.match(web, /useState\(false\)[\s\S]*checked=\{publishExternally\}/);
  assert.match(miniapp, /checked="\{\{feedbackPublicationConsent\}\}"/);
  assert.match(miniappLogic, /feedbackPublicationConsent: false/);
  assert.match(miniappLogic, /feedbackPublish: t\(/);
  assert.match(miniappLogic, /feedbackPublishHelper: t\(/);
  assert.equal(webTypes.includes("external_publication_consent_version: typeof FEEDBACK_PUBLICATION_CONSENT_VERSION;"), true);
  assert.equal(miniappTypes.includes("external_publication_consent_version: typeof FEEDBACK_PUBLICATION_CONSENT_VERSION;"), true);
});
