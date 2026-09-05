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
      calls.push(node.arguments[0]?.getText(file) ?? "<missing argument>");
    }
    ts.forEachChild(node, visit);
  };
  visit(file);
  return calls;
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
    for (const argument of fetchCalls(source, relative)) {
      const rule = rawFetchAllowlist.get(relative);
      if (!rule || !rule.argument.test(argument)) {
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
