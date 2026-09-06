import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  FEEDBACK_PUBLICATION_CONSENT_VERSION as WEB_VERSION,
  feedbackPublicationConsent as webConsent,
} from "../src/lib/feedback.ts";
import * as webPublication from "../src/lib/feedback.ts";
import {
  FEEDBACK_PUBLICATION_CONSENT_VERSION as MINIAPP_VERSION,
  feedbackPublicationConsent as miniappConsent,
} from "../../miniapp/utils/feedback.ts";
import * as miniappPublication from "../../miniapp/utils/feedback.ts";
import * as webSession from "../src/lib/auth-session.ts";

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
    external_publication_consent_version:
      "feedback-publication-v2-public-github",
  };
  assert.equal(WEB_VERSION, MINIAPP_VERSION);
  assert.deepEqual(webConsent(true), expected);
  assert.deepEqual(miniappConsent(true), expected);

  const backend = await read("../../api/optional_processing.py");
  assert.match(
    backend,
    /FEEDBACK_PUBLICATION_CONSENT_VERSION = \(\s*"feedback-publication-v2-public-github"\s*\)/,
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
  const label = "Allow Praxys to publish a scrubbed text summary of this feedback as a public GitHub issue";
  const helper = "Optional and off by default. If published to praxys-run/praxys, anyone can view the text summary. GitHub is outside mainland China, and public issues may be retained long term. Screenshots are never published. Leave this unchecked to send your feedback privately.";

  assert.equal(web.includes(label), true);
  assert.equal(web.split(/\s+/).join(' ').includes(helper), true);
  assert.match(web, /useState\(false\)[\s\S]*checked=\{publishExternally\}/);
  assert.match(miniapp, /checked="\{\{feedbackPublicationConsent\}\}"/);
  assert.match(miniappLogic, /feedbackPublicationConsent: false/);
  assert.match(miniappLogic, /feedbackPublish: t\(/);
  assert.match(miniappLogic, /feedbackPublishHelper: t\(/);
  assert.match(web, /Feedback sent/);
  assert.match(miniapp, /feedbackResultOpen/);
  assert.match(miniappLogic, /feedbackTransportUnknown/);
  assert.equal(webTypes.includes("external_publication_consent_version: typeof FEEDBACK_PUBLICATION_CONSENT_VERSION;"), true);
  assert.equal(miniappTypes.includes("external_publication_consent_version: typeof FEEDBACK_PUBLICATION_CONSENT_VERSION;"), true);
});

test("web and Miniapp normalize publication transitions and issue URLs", () => {
  for (const client of [webPublication, miniappPublication]) {
    assert.deepEqual(
      client.normalizeFeedbackPublicationResult({
        status: "queued",
        issue_url: "https://attacker.invalid/issues/1",
      }),
      { status: "queued", issue_url: null },
    );
    assert.deepEqual(
      client.normalizeFeedbackPublicationResult({
        status: "unknown",
        issue_url: null,
      }),
      { status: "unknown", issue_url: null },
    );
    assert.deepEqual(
      client.normalizeFeedbackPublicationResult({
        status: "published",
        issue_url: "https://github.com/praxys-run/praxys/issues/812",
      }),
      {
        status: "published",
        issue_url: "https://github.com/praxys-run/praxys/issues/812",
      },
    );
    assert.deepEqual(
      client.normalizeFeedbackPublicationResult({
        status: "published",
        issue_url: "https://github.com/praxys-run/praxys/issues/812?next=evil",
      }),
      { status: "unknown", issue_url: null },
    );
  }
});

test("publication refresh is bounded and stops at terminal states", () => {
  for (const client of [webPublication, miniappPublication]) {
    assert.equal(client.feedbackPublicationShouldRefresh("queued", 0), true);
    assert.equal(client.feedbackPublicationShouldRefresh("unknown", 1), true);
    assert.equal(
      client.feedbackPublicationShouldRefresh(
        "queued",
        client.FEEDBACK_PUBLICATION_REFRESH_LIMIT,
      ),
      false,
    );
    for (const terminal of [
      "private",
      "manual_required",
      "published",
      "unavailable",
    ]) {
      assert.equal(client.feedbackPublicationShouldRefresh(terminal, 0), false);
    }
    for (const checkable of ["queued", "unknown", "manual_required"]) {
      assert.equal(client.feedbackPublicationCanCheck(checkable), true);
    }
    for (const terminal of ["private", "published", "unavailable"]) {
      assert.equal(client.feedbackPublicationCanCheck(terminal), false);
    }
  }
});

test("both clients post owner-status IDs only in fixed-path request bodies", async () => {
  const [web, miniapp, routes] = await Promise.all([
    read("../src/components/FeedbackDialog.tsx"),
    read("../../miniapp/pages/settings/index.ts"),
    read("../../api/routes/feedback.py"),
  ]);

  assert.match(web, /setFeedbackId\(acknowledgedId\)/);
  assert.equal(web.match(/['"]\/api\/me\/feedback\/status['"]/g)?.length, 2);
  assert.match(web, /JSON\.stringify\(\{ feedback_id: feedbackId \}\)/);
  assert.match(web, /JSON\.stringify\(\{ feedback_id: expectedId \}\)/);
  assert.doesNotMatch(web, /\/api\/me\/feedback\/\$\{/);
  assert.match(web, /visibilitychange/);
  assert.match(web, /clearTimeout/);
  assert.match(web, /AbortController/);

  assert.match(miniapp, /feedbackResultId: acknowledgedId/);
  assert.equal(miniapp.match(/['"]\/api\/me\/feedback\/status['"]/g)?.length, 2);
  assert.match(miniapp, /\{ feedback_id: feedbackId \}/);
  assert.match(miniapp, /\{ feedback_id: expectedId \}/);
  assert.doesNotMatch(miniapp, /\/api\/me\/feedback\/\$\{/);
  assert.match(miniapp, /scheduleFeedbackPublicationRefresh/);
  assert.match(miniapp, /stopFeedbackPublicationRefresh/);
  assert.match(miniapp, /onHide\(\)/);
  assert.match(miniapp, /onUnload\(\)/);

  assert.match(routes, /@router\.post\("\/me\/feedback\/status"\)/);
  assert.doesNotMatch(routes, /@router\.get\("\/me\/feedback\/\{feedback_id\}"\)/);
  assert.match(routes, /@router\.get\("\/me\/feedback\/\{feedback_id\}\/image\/\{index\}"\)/);
});

test("both clients accept only canonical positive JS-safe feedback IDs", () => {
  for (const client of [webPublication, miniappPublication]) {
    for (const value of [1, 42, "1", "42", Number.MAX_SAFE_INTEGER]) {
      assert.equal(client.parseRecentFeedbackId(value), Number(value));
    }
    for (const value of [
      null,
      undefined,
      true,
      0,
      -1,
      1.5,
      Number.MAX_SAFE_INTEGER + 1,
      "",
      "0",
      "01",
      "1.0",
      "1e3",
      " 1",
    ]) {
      assert.equal(client.parseRecentFeedbackId(value), null);
    }
  }
});

test("web recent-feedback storage persists only one ID and fails nonblocking", () => {
  const values = new Map();
  const previous = globalThis.localStorage;
  globalThis.localStorage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  };
  try {
    webPublication.setRecentFeedbackId(41);
    assert.equal(webPublication.setRecentFeedbackId("041"), false);
    assert.equal(webPublication.getRecentFeedbackId(), 41);
    webPublication.setRecentFeedbackId(42);
    assert.equal(webPublication.getRecentFeedbackId(), 42);
    assert.deepEqual([...values.entries()], [
      ["praxys-most-recent-feedback-id", "42"],
    ]);
    webPublication.removeRecentFeedbackId();
    assert.equal(webPublication.getRecentFeedbackId(), null);

    values.set("praxys-most-recent-feedback-id", "not-an-id");
    assert.equal(webPublication.getRecentFeedbackId(), null);
    assert.equal(values.has("praxys-most-recent-feedback-id"), false);

    values.set("praxys-most-recent-feedback-id", "42");
    globalThis.localStorage = {
      getItem: (key) => values.get(key) ?? null,
      setItem: () => { throw new Error("write blocked"); },
      removeItem: (key) => values.delete(key),
    };
    assert.equal(webPublication.setRecentFeedbackId(43), false);
    assert.equal(webPublication.getRecentFeedbackId(), 42);

    globalThis.localStorage = {
      getItem: () => { throw new Error("blocked"); },
      setItem: () => { throw new Error("blocked"); },
      removeItem: () => { throw new Error("blocked"); },
    };
    assert.doesNotThrow(() => webPublication.setRecentFeedbackId(7));
    assert.equal(webPublication.getRecentFeedbackId(), null);
    assert.doesNotThrow(() => webPublication.removeRecentFeedbackId());
  } finally {
    if (previous === undefined) delete globalThis.localStorage;
    else globalThis.localStorage = previous;
  }
});

test("Miniapp recent-feedback storage persists only one ID and fails nonblocking", () => {
  const values = new Map();
  const removals = [];
  const previous = globalThis.wx;
  globalThis.wx = {
    getStorageSync: (key) => values.get(key),
    setStorageSync: (key, value) => values.set(key, value),
    removeStorageSync: (key) => {
      removals.push(key);
      values.delete(key);
    },
  };
  try {
    miniappPublication.setRecentFeedbackId(51);
    assert.equal(miniappPublication.setRecentFeedbackId("051"), false);
    assert.equal(miniappPublication.getRecentFeedbackId(), 51);
    miniappPublication.setRecentFeedbackId(52);
    assert.equal(miniappPublication.getRecentFeedbackId(), 52);
    assert.deepEqual([...values.entries()], [
      ["praxys-most-recent-feedback-id", "52"],
    ]);
    miniappPublication.removeRecentFeedbackId();
    assert.equal(miniappPublication.getRecentFeedbackId(), null);

    for (const malformed of ["", "not-an-id", null, undefined, true]) {
      values.set("praxys-most-recent-feedback-id", malformed);
      const priorRemovalCount = removals.length;
      assert.equal(miniappPublication.getRecentFeedbackId(), null);
      assert.equal(values.has("praxys-most-recent-feedback-id"), false);
      assert.equal(removals.length, priorRemovalCount + 1);
    }

    values.set("praxys-most-recent-feedback-id", "52");
    globalThis.wx = {
      getStorageSync: (key) => values.get(key),
      setStorageSync: () => { throw new Error("write blocked"); },
      removeStorageSync: (key) => values.delete(key),
    };
    assert.equal(miniappPublication.setRecentFeedbackId(53), false);
    assert.equal(miniappPublication.getRecentFeedbackId(), 52);

    globalThis.wx = {
      getStorageSync: () => { throw new Error("blocked"); },
      setStorageSync: () => { throw new Error("blocked"); },
      removeStorageSync: () => { throw new Error("blocked"); },
    };
    assert.doesNotThrow(() => miniappPublication.setRecentFeedbackId(7));
    assert.equal(miniappPublication.getRecentFeedbackId(), null);
    assert.doesNotThrow(() => miniappPublication.removeRecentFeedbackId());
  } finally {
    if (previous === undefined) delete globalThis.wx;
    else globalThis.wx = previous;
  }
});

test("status lookup dispositions preserve retryable IDs and reject mismatches", () => {
  for (const client of [webPublication, miniappPublication]) {
    assert.equal(client.feedbackStatusLookupDisposition(200, 42, 42), "success");
    assert.equal(client.feedbackStatusLookupDisposition(200, 42, 41), "gone");
    assert.equal(client.feedbackStatusLookupDisposition(200, 42, "042"), "gone");
    assert.equal(client.feedbackStatusLookupDisposition(403, 42, null), "gone");
    assert.equal(client.feedbackStatusLookupDisposition(404, 42, null), "gone");
    assert.equal(client.feedbackStatusLookupDisposition(401, 42, null), "unauthenticated");
    assert.equal(client.feedbackStatusLookupDisposition(0, 42, null), "retry");
    assert.equal(client.feedbackStatusLookupDisposition(500, 42, null), "retry");
  }
});

function exerciseStatusStorage(client, installStorage) {
  const cases = [
    { status: 200, responseId: 42, expected: "success", retained: true },
    { status: 401, responseId: null, expected: "unauthenticated", retained: false },
    { status: 403, responseId: null, expected: "gone", retained: false },
    { status: 404, responseId: null, expected: "gone", retained: false },
    { status: 200, responseId: 41, expected: "gone", retained: false },
    { status: 500, responseId: null, expected: "retry", retained: true },
    { status: 0, responseId: null, expected: "retry", retained: true },
  ];
  for (const current of cases) {
    const restore = installStorage();
    try {
      assert.equal(client.setRecentFeedbackId(42), true);
      assert.equal(
        client.applyFeedbackStatusLookup(
          current.status,
          42,
          current.responseId,
        ),
        current.expected,
      );
      assert.equal(
        client.getRecentFeedbackId(),
        current.retained ? 42 : null,
      );
    } finally {
      restore();
    }
  }
}

test("status outcomes clear only authoritative or gone recent-feedback IDs", () => {
  exerciseStatusStorage(webPublication, () => {
    const values = new Map();
    const previous = globalThis.localStorage;
    globalThis.localStorage = {
      getItem: (key) => values.get(key) ?? null,
      setItem: (key, value) => values.set(key, value),
      removeItem: (key) => values.delete(key),
    };
    return () => {
      if (previous === undefined) delete globalThis.localStorage;
      else globalThis.localStorage = previous;
    };
  });
  exerciseStatusStorage(miniappPublication, () => {
    const values = new Map();
    const previous = globalThis.wx;
    globalThis.wx = {
      getStorageSync: (key) => values.get(key),
      setStorageSync: (key, value) => values.set(key, value),
      removeStorageSync: (key) => values.delete(key),
    };
    return () => {
      if (previous === undefined) delete globalThis.wx;
      else globalThis.wx = previous;
    };
  });
});

test("miniapp submission treats status-zero transport failures as unknown delivery", () => {
  assert.equal(
    typeof miniappPublication.feedbackSubmissionTransportUnknown,
    "function",
  );
  for (const error of [
    { status: 0, code: "TIMEOUT", detail: "request:fail timeout" },
    { status: 0, code: "NETWORK_ERROR", detail: "request:fail offline" },
    { status: 0, errno: 600001, detail: "request:fail network" },
    { status: undefined, detail: "ambiguous transport exception" },
    { status: 503, detail: "existing ambiguous server failure" },
  ]) {
    assert.equal(
      miniappPublication.feedbackSubmissionTransportUnknown(error),
      true,
      error.detail,
    );
  }
  for (const error of [
    { status: 400, detail: "validation" },
    { status: 422, detail: "unprocessable" },
    { status: 429, detail: "rate limited" },
  ]) {
    assert.equal(
      miniappPublication.feedbackSubmissionTransportUnknown(error),
      false,
      error.detail,
    );
  }
});

test("unauthorized-session seam clears auth token and feedback ID before redirect", () => {
  const values = new Map([
    ["praxys-auth-token", "current-token"],
    ["trainsight-auth-token", "legacy-token"],
    ["praxys-most-recent-feedback-id", "42"],
  ]);
  const previous = globalThis.localStorage;
  globalThis.localStorage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  };
  try {
    assert.equal(typeof webSession.handleUnauthorizedSession, "function");
    let redirects = 0;
    webSession.handleUnauthorizedSession(() => {
      redirects += 1;
      assert.equal(values.has("praxys-auth-token"), false);
      assert.equal(values.has("trainsight-auth-token"), false);
      assert.equal(values.has("praxys-most-recent-feedback-id"), false);
    });
    assert.equal(redirects, 1);
  } finally {
    if (previous === undefined) delete globalThis.localStorage;
    else globalThis.localStorage = previous;
  }
});

test("readiness fences abort superseded work and reject stale results", () => {
  for (const client of [webPublication, miniappPublication]) {
    const fence = new client.FeedbackReadinessRequestFence();
    const first = { aborts: 0, abort() { this.aborts += 1; } };
    const stale = { aborts: 0, abort() { this.aborts += 1; } };
    const current = { aborts: 0, abort() { this.aborts += 1; } };

    const firstGeneration = fence.begin();
    assert.equal(fence.attach(firstGeneration, first), true);
    assert.equal(fence.canApply(firstGeneration, true), true);
    assert.equal(fence.canApply(firstGeneration, false), false);
    assert.equal(fence.canApply(firstGeneration, true, true), false);

    const currentGeneration = fence.begin();
    assert.equal(first.aborts, 1);
    assert.equal(fence.canApply(firstGeneration, true), false);
    assert.equal(fence.attach(firstGeneration, stale), false);
    assert.equal(stale.aborts, 1);
    assert.equal(fence.attach(currentGeneration, current), true);

    fence.cancel(firstGeneration);
    assert.equal(current.aborts, 0);
    assert.equal(fence.canApply(currentGeneration, true), true);
    fence.cancel(currentGeneration);
    assert.equal(current.aborts, 1);
    assert.equal(fence.canApply(currentGeneration, true), false);
  }
});

test("authoritative 401 paths clear restored sessions and block stale UI updates", async () => {
  const [apiTransport, authBootstrap] = await Promise.all([
    read("../src/hooks/useApi.ts"),
    read("../src/hooks/useAuth.tsx"),
  ]);

  assert.match(
    apiTransport,
    /res\.status === 401[\s\S]*handleUnauthorizedSession\(\)[\s\S]*new Promise<Response>\(\(\) => \{\}\)/,
  );
  assert.match(
    authBootstrap,
    /resolveRestoredSession\([\s\S]*disposition === 'invalid'[\s\S]*clearRestoredSession\(\)/,
  );
});

test("feedback status UX and auth cleanup are source-complete on both clients", async () => {
  const [
    webDialog,
    webDialogPrimitive,
    webAuth,
    webApi,
    adminFeedback,
    miniSettings,
    miniMarkup,
    miniAuth,
    miniApi,
  ] = await Promise.all([
    read("../src/components/FeedbackDialog.tsx"),
    read("../src/components/ui/dialog.tsx"),
    read("../src/hooks/useAuth.tsx"),
    read("../src/hooks/useApi.ts"),
    read("../src/pages/admin/AdminFeedback.tsx"),
    read("../../miniapp/pages/settings/index.ts"),
    read("../../miniapp/pages/settings/index.wxml"),
    read("../../miniapp/utils/auth.ts"),
    read("../../miniapp/utils/api-client.ts"),
  ]);

  assert.match(webDialog, /Check most recent feedback status/);
  assert.match(webDialog, /Feedback status/);
  assert.match(webDialog, /Feedback sent/);
  assert.match(webDialog, /Checking status…/);
  assert.match(webDialog, /cache:\s*['"]no-store['"]/);
  assert.match(webDialog, /aria-atomic="true"/);
  assert.match(webDialog, /max-h-\[calc\(100dvh-2rem\)\]/);
  assert.match(webDialog, /overflow-y-auto/);
  assert.match(webDialog, /statusCheckControllerRef/);
  assert.match(webDialog, /feedbackPublicationCanCheck/);
  assert.match(webDialogPrimitive, /closeLabel\?:/);
  assert.match(webDialogPrimitive, /size-11/);

  assert.match(adminFeedback, /role="status"/);
  assert.match(adminFeedback, /aria-live="polite"/);
  assert.match(adminFeedback, /aria-atomic="true"/);
  assert.match(adminFeedback, /review_token:/);
  assert.match(adminFeedback, /publication_review_token/);

  assert.match(miniSettings, /feedbackCanSubmit/);
  assert.match(miniSettings, /onCheckRecentFeedbackStatus/);
  assert.match(miniSettings, /feedbackPublicationCanCheck/);
  assert.match(miniSettings, /feedbackStatusRequestTask/);
  assert.match(miniMarkup, /feedbackCheckRecent/);
  assert.match(miniMarkup, /feedbackCheckingAvailability/);
  assert.doesNotMatch(miniMarkup, /!feedbackMessage\}\}"/);

  assert.match(webAuth, /removeRecentFeedbackId\(\)/);
  assert.match(webApi, /handleUnauthorizedSession\(\)/);
  assert.match(miniAuth, /removeRecentFeedbackId\(\)/);
  assert.match(miniApi, /removeRecentFeedbackId\(\)/);
  assert.ok(
    webDialog.indexOf('const acknowledgedResult')
      < webDialog.indexOf('setRecentFeedbackId(acknowledgedId)'),
  );
  assert.ok(
    miniSettings.indexOf('const result = normalizeFeedbackPublicationResult')
      < miniSettings.indexOf('setRecentFeedbackId(acknowledgedId)'),
  );
  assert.match(webAuth, /removeRecentFeedbackId\(\);[\s\S]*setCompatItem\(KEYS\.authToken/);
  assert.match(miniAuth, /saveToken[\s\S]*removeRecentFeedbackId\(\);[\s\S]*setStorageSync\(TOKEN_KEY/);
  assert.match(miniAuth, /clearToken[\s\S]*removeRecentFeedbackId\(\);[\s\S]*removeStorageSync\(TOKEN_KEY/);
});

test("feedback UI keeps touch targets, semantic links, and reduced motion", async () => {
  const [dialog, primitive, sidebar, layout, appSidebar] = await Promise.all([
    read("../src/components/FeedbackDialog.tsx"),
    read("../src/components/ui/dialog.tsx"),
    read("../src/components/ui/sidebar.tsx"),
    read("../src/components/Layout.tsx"),
    read("../src/components/AppSidebar.tsx"),
  ]);

  assert.match(sidebar, /className=\{cn\("size-11", className\)\}/);
  assert.match(layout, /<SidebarTrigger className="size-11" \/>/);
  assert.match(
    appSidebar,
    /<SidebarMenuButton className="min-h-11" onClick=\{\(\) => setFeedbackOpen\(true\)\}/,
  );
  assert.match(dialog, /<Trans>Feedback Type<\/Trans>/);
  assert.match(dialog, /<SelectTrigger id="feedback-kind" className="min-h-11 w-full">/);
  assert.match(dialog, /buttonVariants\(\{ variant: 'outline' \}\)/);
  assert.match(dialog, /<a[\s\S]*href=\{result\.issue_url\}/);
  assert.doesNotMatch(dialog, /role="button"/);
  assert.doesNotMatch(dialog, /readinessOpenRef/);
  assert.doesNotMatch(dialog, /readinessFenceRef\.current\.cancel\(generation\)/);
  assert.match(dialog, /const readinessFence = readinessFenceRef\.current;/);
  assert.match(dialog, /let readinessActive = true;/);
  assert.match(
    dialog,
    /queueMicrotask\(\(\) => \{[\s\S]*if \(!isCurrent\(\)\) return;[\s\S]*setPublicationAvailable\(null\)/,
  );
  assert.match(
    dialog,
    /return \(\) => \{[\s\S]*readinessActive = false;[\s\S]*readinessFence\.cancel\(generation\)/,
  );
  assert.ok((primitive.match(/motion-reduce:animate-none!/g) ?? []).length >= 2);
  assert.ok((primitive.match(/motion-reduce:transition-none!/g) ?? []).length >= 2);
  assert.ok((primitive.match(/motion-reduce:duration-0!/g) ?? []).length >= 2);
});

test("feedback status copy is localized for web and Miniapp", async () => {
  const [zhCatalog, miniCatalog] = await Promise.all([
    read("../src/locales/zh/messages.po"),
    read("../../miniapp/utils/i18n-catalog.ts"),
  ]);
  const normalizedZhCatalog = zhCatalog.replace(/\r\n?/g, "\n");
  const translations = [
    ['Check most recent feedback status', '查看最近一次反馈状态'],
    ['Check status', '查看状态'],
    ['Checking public publishing availability…', '正在检查公开发布可用性…'],
    ['Checking status…', '正在查看状态…'],
    ["Couldn't check feedback status. Try again.", '无法查看反馈状态，请重试。'],
    ['Feedback status', '反馈状态'],
    ['The most recent feedback status is no longer available.', '最近一次反馈状态已不可用。'],
  ];
  for (const [english, chinese] of translations) {
    assert.equal(
      normalizedZhCatalog.includes(`msgid "${english}"\nmsgstr "${chinese}"`),
      true,
    );
    assert.equal(miniCatalog.includes(JSON.stringify(english)), true);
    assert.equal(miniCatalog.includes(JSON.stringify(chinese)), true);
  }
});
