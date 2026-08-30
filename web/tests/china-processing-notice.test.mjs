import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  CHINA_PROCESSING_NOTICE_STORAGE_KEY,
  CHINA_PROCESSING_NOTICE_VERSION,
  acknowledgeChinaProcessingNotice,
  canStartPersonalDataRequests,
  hasAcknowledgedChinaProcessingNotice,
  isChinaProcessingPublicPath,
} from "../src/lib/china-processing.ts";
import {
  classifyRestoredSession,
  resolveRestoredSession,
} from "../src/lib/auth-session.ts";

function installChinaMarker() {
  const original = Object.getOwnPropertyDescriptor(globalThis, "document");
  Object.defineProperty(globalThis, "document", {
    configurable: true,
    value: {
      querySelector(selector) {
        assert.equal(selector, 'meta[name="praxys-deployment-region"]');
        return { content: "cn" };
      },
    },
  });
  return () => {
    if (original) Object.defineProperty(globalThis, "document", original);
    else delete globalThis.document;
  };
}

test("China processing notice covers personal routes but leaves legal and public pages open", () => {
  assert.equal(isChinaProcessingPublicPath("/"), true);
  assert.equal(isChinaProcessingPublicPath("/privacy/"), true);
  assert.equal(isChinaProcessingPublicPath("/status"), true);
  assert.equal(isChinaProcessingPublicPath("/login"), false);
  assert.equal(isChinaProcessingPublicPath("/today"), false);
  assert.equal(isChinaProcessingPublicPath("/verify"), false);
});

test("current notice acknowledgement gates China personal-data requests", () => {
  const restoreDocument = installChinaMarker();
  const values = new Map();
  const storage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  };

  try {
    assert.equal(hasAcknowledgedChinaProcessingNotice(storage), false);
    assert.equal(canStartPersonalDataRequests(), false);
    acknowledgeChinaProcessingNotice(storage);
    assert.equal(
      values.get(CHINA_PROCESSING_NOTICE_STORAGE_KEY),
      CHINA_PROCESSING_NOTICE_VERSION,
    );
    assert.equal(hasAcknowledgedChinaProcessingNotice(storage), true);
    assert.equal(canStartPersonalDataRequests(), true);
  } finally {
    restoreDocument();
  }
});

test("auth restoration preserves credentials across retryable failures", () => {
  assert.equal(classifyRestoredSession(401, false), "invalid");
  assert.equal(classifyRestoredSession(0, false), "transient-failure");
  assert.equal(classifyRestoredSession(500, false), "transient-failure");
  assert.equal(classifyRestoredSession(200, false), "transient-failure");
  assert.equal(classifyRestoredSession(200, true), "authenticated");
  assert.deepEqual(resolveRestoredSession("stored-token", 503, false), {
    disposition: "transient-failure",
    token: "stored-token",
  });
  assert.deepEqual(resolveRestoredSession("stored-token", 401, false), {
    disposition: "invalid",
    token: null,
  });
});

test("auth prefetch and provider mounting honor the pre-transfer boundary", async () => {
  const [
    app,
    landing,
    prefetch,
    apiHook,
    auth,
    clientBoundary,
    termsGate,
    legal,
    gate,
    providerNotice,
    setup,
    settings,
    miniClient,
    miniVersion,
    miniWorkflow,
    miniLogin,
    miniLoginTemplate,
    miniSettings,
    miniDataRights,
    miniEvents,
    apiTypes,
    zhCatalog,
  ] = await Promise.all([
    readFile(new URL("../src/App.tsx", import.meta.url), "utf8"),
    readFile(new URL("../src/pages/Landing.tsx", import.meta.url), "utf8"),
    readFile(new URL("../src/lib/auth-prefetch.ts", import.meta.url), "utf8"),
    readFile(new URL("../src/hooks/useApi.ts", import.meta.url), "utf8"),
    readFile(new URL("../src/hooks/useAuth.tsx", import.meta.url), "utf8"),
    readFile(
      new URL("../src/lib/client-boundary.ts", import.meta.url),
      "utf8",
    ),
    readFile(
      new URL("../src/components/TermsGate.tsx", import.meta.url),
      "utf8",
    ),
    readFile(new URL("../src/lib/legal.ts", import.meta.url), "utf8"),
    readFile(
      new URL("../src/components/ChinaProcessingNoticeGate.tsx", import.meta.url),
      "utf8",
    ),
    readFile(
      new URL("../src/components/PlatformConnectionNotice.tsx", import.meta.url),
      "utf8",
    ),
    readFile(new URL("../src/pages/Setup.tsx", import.meta.url), "utf8"),
    readFile(new URL("../src/pages/Settings.tsx", import.meta.url), "utf8"),
    readFile(
      new URL("../../miniapp/utils/api-client.ts", import.meta.url),
      "utf8",
    ),
    readFile(
      new URL("../../miniapp/utils/version.ts", import.meta.url),
      "utf8",
    ),
    readFile(
      new URL(
        "../../.github/workflows/miniapp-publish.yml",
        import.meta.url,
      ),
      "utf8",
    ),
    readFile(
      new URL("../../miniapp/pages/login/index.ts", import.meta.url),
      "utf8",
    ),
    readFile(
      new URL("../../miniapp/pages/login/index.wxml", import.meta.url),
      "utf8",
    ),
    readFile(
      new URL("../../miniapp/pages/settings/index.ts", import.meta.url),
      "utf8",
    ),
    readFile(
      new URL("../../miniapp/utils/data-rights.ts", import.meta.url),
      "utf8",
    ),
    readFile(
      new URL("../../miniapp/utils/product-events.ts", import.meta.url),
      "utf8",
    ),
    readFile(new URL("../src/types/api.ts", import.meta.url), "utf8"),
    readFile(new URL("../src/locales/zh/messages.po", import.meta.url), "utf8"),
  ]);

  assert.match(
    app.replace(/\s+/g, " "),
    /<BrowserRouter> <ChinaProcessingBoundary> <AuthProvider>/,
  );
  assert.match(
    app,
    /!acknowledged &&\s*!hasAcknowledgedChinaProcessingNotice\(\)/,
  );
  assert.match(
    app,
    /function RequireCurrentTerms[\s\S]*if \(!termsCurrent\) \{[\s\S]*return <TermsGate \/>;[\s\S]*function AuthenticatedApp\(\)[\s\S]*<RequireCurrentTerms>[\s\S]*<SettingsProvider>/,
  );
  assert.match(
    app,
    /path="\/mcp\/authorize"[\s\S]*<RequireAuth>[\s\S]*<RequireCurrentTerms>[\s\S]*<McpAuthorization \/>/,
  );
  assert.match(
    app.replace(/\s+/g, " "),
    /<RequireAuth> <AuthenticatedApp \/> <\/RequireAuth>/,
  );
  assert.match(prefetch, /token &&\s+canStartPersonalDataRequests\(\)/);
  assert.match(
    apiHook,
    /initialDashboardUrl\([\s\S]*canStartPersonalDataRequests\(\)/,
  );
  assert.match(
    apiHook,
    /function getAuthHeaders\(\)[\s\S]*if \(!canStartPersonalDataRequests\(\)\) return \{\}/,
  );
  assert.match(apiHook, /getChinaClientHeaders\(\)/);
  assert.match(apiHook, /TERMS_ACCEPTANCE_REQUIRED/);
  assert.match(auth, /if \(!canStartPersonalDataRequests\(\)\)/);
  assert.match(auth, /extractApiError\(res,/);
  assert.match(auth, /termsCurrent: false/);
  assert.match(
    auth,
    /resolveRestoredSession\([\s\S]*disposition === 'invalid'[\s\S]*clearRestoredSession\(\)/,
  );
  assert.match(
    auth,
    /disposition !== 'authenticated' \|\| !data[\s\S]*setToken\(restoredToken\)[\s\S]*setRestoreStatus\('retryable'\)/,
  );
  assert.match(app, /restoreStatus === 'retryable'[\s\S]*Try again/);
  assert.match(
    auth,
    /if \(!canStartPersonalDataRequests\(\)\) \{[\s\S]*Read the processing notice before continuing/,
  );
  assert.match(
    auth,
    /const meResponse = await fetch\([\s\S]*setTermsCurrent\(me\.terms_current === true\);[\s\S]*setToken\(accessToken\);/,
  );
  assert.match(
    auth,
    /typeof accessToken !== 'string' \|\| accessToken\.length === 0[\s\S]*Sign-in response was incomplete/,
  );
  assert.match(auth, /TERMS_REQUIRED_EVENT/);
  assert.match(auth, /queryClient\.invalidateQueries\(\)/);
  assert.match(clientBoundary, /'X-Praxys-Client': 'cn-web'/);
  assert.match(
    clientBoundary,
    /'X-Praxys-Notice-Version': CHINA_PROCESSING_NOTICE_VERSION/,
  );
  assert.doesNotMatch(clientBoundary, /X-Praxys-Source-Sha/);
  assert.doesNotMatch(clientBoundary, /X-Praxys-Client-Version/);
  assert.match(
    clientBoundary,
    /'X-Praxys-Policy-Digest': TERMS_CONTENT_DIGEST/,
  );
  assert.match(
    clientBoundary,
    /'X-Praxys-Api-Contract': CN_PRIVACY_CONTRACT_VERSION/,
  );
  assert.match(landing, /canStartPersonalDataRequests\(\)/);
  assert.match(landing, /<ChinaProcessingNoticeGate/);
  assert.match(landing, /acknowledgeChinaProcessingNotice\(\)/);
  assert.match(
    landing,
    /noticeTriggerRef\.current === 'hero'[\s\S]*heroDemoButtonRef\.current[\s\S]*button\?\.focus\(\)/,
  );
  assert.match(
    landing,
    /onCancel=\{\(\) => \{[\s\S]*setRestoreDemoFocus\(true\);[\s\S]*setShowChinaNotice\(false\);/,
  );
  assert.match(gate, /onCancel\?: \(\) => void/);
  assert.match(termsGate, /I accept the/);
  assert.match(termsGate, /acknowledge that I have read the/);
  assert.doesNotMatch(termsGate, /I agree to the/);
  assert.match(termsGate, /\/api\/me\/export/);
  assert.match(termsGate, /method: "DELETE"/);
  assert.match(termsGate, /Export my data/);
  assert.match(termsGate, /Delete account/);
  assert.match(termsGate, /Sign out/);
  assert.match(termsGate, /\/api\/settings\/connections/);
  assert.match(termsGate, /handleDisconnect/);
  assert.match(termsGate, /PLATFORM_LABELS\[platform as PlatformName\] \?\? platform/);
  assert.match(termsGate, /encodeURIComponent\(platform\)/);
  assert.match(apiTypes, /schema_version: 6/);
  assert.match(apiTypes, /account: UserDataExportAccount/);
  assert.match(apiTypes, /connections: UserDataExportConnection\[\]/);
  assert.match(apiTypes, /activity_samples: UserDataExportActivitySample\[\]/);
  assert.match(
    apiTypes,
    /terms_acceptance_receipts: UserDataExportTermsAcceptanceReceipt\[\]/,
  );
  assert.match(legal, /processed in Microsoft-managed Azure services outside mainland China/);
  assert.match(legal, /current primary hosting region is Azure East Asia \(Hong Kong SAR\)/);
  assert.match(legal, /change facilities or published subprocessors/);
  assert.match(legal, /configured endpoint in West US 3, United States/);
  assert.match(legal, /Microsoft Corporation/);
  assert.match(legal, /user-event logging and SDK diagnostics are disabled/);
  assert.match(gate, /not based on consent/);
  assert.match(gate, /current primary hosting region/);
  assert.doesNotMatch(gate, /West US 3/);
  assert.match(gate, /Acknowledge and continue/);
  assert.doesNotMatch(gate, /type="checkbox"/);
  assert.doesNotMatch(
    `${app}\n${gate}\n${miniLogin}`,
    /navigator\.geolocation|wx\.getLocation|wx\.getFuzzyLocation|citizenship|nationality/,
  );
  assert.doesNotMatch(providerNotice, /isChinaFrontendDeployment/);
  assert.match(providerNotice, /https:\/\/www\.strava\.com\/legal\/privacy/);
  assert.match(providerNotice, /Disconnecting stops future retrieval/);
  assert.doesNotMatch(providerNotice, /is optional/);
  assert.doesNotMatch(providerNotice, /bg-accent-cobalt|border-accent-cobalt/);
  assert.match(
    zhCatalog,
    /msgid "\{0\} privacy and contact information"\s+msgstr "\{0\} 的隐私与联系信息"/,
  );
  assert.match(
    zhCatalog,
    /msgid "When you continue, Praxys sends[^"]+\{0\}[^"]+\{1\}[^"]+"\s+msgstr "继续后，Praxys 会将[^"]+\{0\}[^"]+\{1\}[^"]+"/,
  );
  assert.match(setup, /<PlatformConnectionNotice platform=\{connectPlatform\} \/>/);
  assert.match(settings, /<PlatformConnectionNotice platform=\{connectPlatform\} \/>/);
  assert.match(
    miniClient.replace(/\s+/g, " "),
    /if \(!hasAcknowledgedChinaProcessingNotice\(\)\) \{ redirectToProcessingNotice\(\); throw/,
  );
  assert.match(miniClient, /'X-Praxys-Client': 'wechat-miniapp'/);
  assert.match(
    miniClient,
    /'X-Praxys-Notice-Version': CHINA_PROCESSING_NOTICE_VERSION/,
  );
  assert.match(
    miniClient,
    /'X-Praxys-Policy-Digest': TERMS_CONTENT_DIGEST/,
  );
  assert.match(
    miniClient,
    /'X-Praxys-Api-Contract': CN_PRIVACY_CONTRACT_VERSION/,
  );
  assert.match(miniClient, /status === 428/);
  assert.match(miniClient, /TERMS_ACCEPTANCE_REQUIRED/);
  const miniNetworkFailure = miniClient.match(
    /catch \(e\) \{([\s\S]*?)\n  \}\n\n  const status/,
  )?.[1] ?? "";
  assert.doesNotMatch(miniNetworkFailure, /removeStorageSync/);
  assert.match(
    miniClient,
    /status === 401[\s\S]*wx\.removeStorageSync\(TOKEN_KEY\)/,
  );
  assert.doesNotMatch(miniVersion, /MINIAPP_SOURCE_SHA/);
  assert.doesNotMatch(miniWorkflow, /X-Praxys-Source-Sha/);
  assert.match(miniLogin, /stage: 'notice'/);
  assert.match(miniLogin, /stage: 'terms'/);
  assert.match(
    miniLogin,
    /async onTermsSubmit\(\)[\s\S]*apiPost\('\/api\/me\/accept-terms', \{[\s\S]*terms_version: TERMS_VERSION,[\s\S]*terms_digest: TERMS_CONTENT_DIGEST,[\s\S]*locale:/,
  );
  assert.match(miniLogin, /locale: this\.data\.locale/);
  assert.match(
    miniLogin,
    /onSwitchLang[\s\S]*globalData\.locale = next/,
  );
  assert.match(
    miniLogin,
    /onTermsDecline\(\)[\s\S]*clearToken\(\)[\s\S]*stage: 'idle'/,
  );
  assert.doesNotMatch(miniLogin, /async function ensureCurrentTerms/);
  assert.match(miniLoginTemplate, /stage === 'terms'/);
  assert.match(miniLoginTemplate, /bindtap="onTermsSubmit"/);
  assert.match(miniLoginTemplate, /bindtap="onTermsDecline"/);
  assert.match(miniLoginTemplate, /bindtap="onTermsExport"/);
  assert.match(miniLoginTemplate, /bindtap="onTermsDelete"/);
  assert.match(miniLoginTemplate, /bindtap="onTermsDisconnect"/);
  assert.match(miniLoginTemplate, /aria-role="checkbox"/);
  assert.match(miniLoginTemplate, /aria-checked="\{\{agreedTerms\}\}"/);
  assert.match(
    miniLoginTemplate,
    /login-notice-link"[\s\S]*aria-role="link"/,
  );
  assert.match(miniLogin, /exportAndShareMyData\(\)/);
  assert.match(miniLogin, /apiDelete\('\/api\/me'\)/);
  assert.match(miniLogin, /apiGet<ConnectionsResponse>\([\s\S]*'\/api\/settings\/connections'/);
  assert.match(miniLogin, /PLATFORM_LABELS\[platform as PlatformName\] \?\? platform/);
  assert.match(
    miniLogin,
    /apiDelete\([\s\S]*encodeURIComponent\(platform\)[\s\S]*\)/,
  );
  assert.match(miniSettings, /const WEB_URL = 'https:\/\/www\.praxys\.run'/);
  assert.match(miniSettings, /async onExportData\(\)/);
  assert.match(miniSettings, /exportAndShareMyData\(\)/);
  assert.match(miniDataRights, /apiGet<unknown>\('\/api\/me\/export'\)/);
  assert.match(miniDataRights, /wx\.shareFileMessage\(/);
  assert.match(miniDataRights, /wx\.getFileSystemManager\(\)\.unlink\(/);
  assert.match(miniDataRights, /removeStoredExports\(\)/);
  assert.match(miniEvents, /const PRODUCT_EVENTS_ENABLED = false/);
});
