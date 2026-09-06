import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import ts from "typescript";

const sourceRoot = new URL("../src/", import.meta.url);

const rawFetchAllowlist = new Map([
  ["hooks/useApi.ts", { expected: 1, argument: /^fullUrl$/ }],
  ["hooks/useAuth.tsx", {
    expected: 4,
    argument: /\/api\/auth\/(?:login|me|register)`$/,
  }],
  ["lib/auth-prefetch.ts", {
    expected: 1,
    argument: /\/api\/auth\/me`$/,
  }],
  ["pages/Login.tsx", {
    expected: 3,
    argument: /\/api\/(?:public\/config|auth\/(?:request-verify-token|waitlist))`$/,
  }],
  ["pages/Verify.tsx", {
    expected: 1,
    argument: /\/api\/auth\/verify`$/,
  }],
  ["components/trail-course-review/owner-export.ts", {
    expected: 1,
    exactOwnerExport: true,
  }],
]);

async function sourceFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const target = new URL(`${entry.name}${entry.isDirectory() ? "/" : ""}`, directory);
    if (entry.isDirectory()) return sourceFiles(target);
    return /\.[jt]sx?$/.test(entry.name) ? [target] : [];
  }));
  return files.flat();
}

function fetchCalls(source, fileName) {
  const scriptKind = fileName.endsWith("x") ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
  const file = ts.createSourceFile(
    fileName,
    source,
    ts.ScriptTarget.Latest,
    true,
    scriptKind,
  );
  const calls = [];
  const visit = (node) => {
    if (
      ts.isCallExpression(node)
      && ts.isIdentifier(node.expression)
      && node.expression.text === "fetch"
    ) {
      calls.push({ node, file });
    }

    ts.forEachChild(node, visit);
  };
  visit(file);
  return calls;
}

function isExactTrailOwnerExportFetch(call) {
  const { node, file } = call;
  if (node.arguments.length !== 2) return false;
  const [target, options] = node.arguments;
  if (!ts.isStringLiteral(target) || target.text !== "/api/me/export") return false;
  if (!ts.isObjectLiteralExpression(options)) return false;
  if (options.properties.length !== 5) return false;
  const expected = new Map([
    ["method", (value) => ts.isStringLiteral(value) && value.text === "GET"],
    ["headers", (value) => (
      ts.isCallExpression(value)
      && ts.isIdentifier(value.expression)
      && value.expression.text === "getAuthHeaders"
      && value.arguments.length === 0
    )],
    ["mode", (value) => ts.isStringLiteral(value) && value.text === "same-origin"],
    ["redirect", (value) => ts.isStringLiteral(value) && value.text === "error"],
    ["signal", (value) => (
      ts.isPropertyAccessExpression(value)
      && ts.isIdentifier(value.expression)
      && value.expression.text === "controller"
      && value.name.text === "signal"
    )],
  ]);
  for (const property of options.properties) {
    if (!ts.isPropertyAssignment(property) || property.name === undefined) return false;
    if (property.name && ts.isComputedPropertyName(property.name)) return false;
    const name = property.name.getText(file).replaceAll(/['"]/g, "");
    const predicate = expected.get(name);
    if (!predicate || !predicate(property.initializer)) return false;
    expected.delete(name);
  }
  return expected.size === 0;
}

function isAllowedRawFetch(relative, call) {
  const rule = rawFetchAllowlist.get(relative);
  if (!rule) return false;
  if (rule.exactOwnerExport) return isExactTrailOwnerExportFetch(call);
  const argument = call.node.arguments[0]?.getText(call.file) ?? "<missing argument>";
  return rule.argument.test(argument);
}

test("raw fetch is limited to low-level transport and exact public/auth bootstrap endpoints", async () => {
  const files = await sourceFiles(sourceRoot);
  const observed = new Map();
  const violations = [];

  for (const fileUrl of files) {
    const relative = path.posix.normalize(
      path.relative(sourceRoot.pathname, fileUrl.pathname),
    );
    const source = await readFile(fileUrl, "utf8");
    for (const call of fetchCalls(source, relative)) {
      const argument = call.node.arguments[0]?.getText(call.file) ?? "<missing argument>";
      if (!isAllowedRawFetch(relative, call)) {
        violations.push(`${relative}: fetch(${argument})`);
        continue;
      }
      observed.set(relative, (observed.get(relative) ?? 0) + 1);
    }
  }

  assert.deepEqual(violations, []);
  assert.deepEqual(
    Object.fromEntries([...rawFetchAllowlist].map(([file, rule]) => [
      file,
      observed.get(file) ?? 0,
    ])),
    Object.fromEntries([...rawFetchAllowlist].map(([file, rule]) => [
      file,
      rule.expected,
    ])),
  );
});

test("Trail owner export raw-fetch recognition is exact and rejects override surfaces", () => {
  const exact = `fetch('/api/me/export', {
    method: 'GET',
    headers: getAuthHeaders(),
    mode: 'same-origin',
    redirect: 'error',
    signal: controller.signal,
  })`;
  const exactCall = fetchCalls(exact, "owner-export.ts")[0];
  assert.equal(isExactTrailOwnerExportFetch(exactCall), true);
  assert.equal(
    isAllowedRawFetch("components/trail-course-review/owner-export.ts", exactCall),
    true,
  );
  assert.equal(
    isAllowedRawFetch("components/trail-course-review/other.ts", exactCall),
    false,
  );
  for (const source of [
    exact.replace("'/api/me/export'", "endpoint"),
    exact.replace("'/api/me/export'", "'https://example.com/api/me/export'"),
    exact.replace("'/api/me/export'", "'/api/me/export?owner=1'"),
    exact.replace("method: 'GET'", "method: 'POST'"),
    exact.replace("headers: getAuthHeaders()", "headers: {}"),
    exact.replace("mode: 'same-origin'", "mode: 'cors'"),
    exact.replace("redirect: 'error'", "redirect: 'follow'"),
    exact.replace("signal: controller.signal", "signal: other.signal"),
    exact.replace("signal: controller.signal,", "signal: controller.signal, body: '{}',"),
    exact.replace("signal: controller.signal,", "signal: controller.signal, ...overrides,"),
    `${exact}; ${exact}`,
  ]) {
    const calls = fetchCalls(source, "owner-export.ts");
    assert.equal(
      calls.length === 1 && isExactTrailOwnerExportFetch(calls[0]),
      false,
      source,
    );
  }
});
