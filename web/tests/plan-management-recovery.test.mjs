import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8');

function finalView(source, name) {
  const file = ts.createSourceFile(`${name}.tsx`, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const component = file.statements.find(
    (node) => ts.isFunctionDeclaration(node) && node.name?.text === name,
  );
  const statement = component?.body?.statements.findLast(ts.isReturnStatement);
  assert.ok(statement?.expression && ts.isParenthesizedExpression(statement.expression));
  return statement.expression.expression;
}

function directElements(view, name) {
  return view.children.filter(
    (node) => ts.isJsxElement(node) && node.openingElement.tagName.getText() === name,
  );
}

test('Training retains the same management owner when leaving a legacy plan', async () => {
  const source = await read('../src/components/PlanStart.tsx');
  const view = finalView(source, 'PlanStart');
  assert.ok(ts.isJsxElement(view));
  const owners = directElements(view, 'ManagedPlanSettingsCard');
  assert.equal(owners.length, 1, 'the cleanup owner must not depend on hasManagedPlan');
  assert.match(owners[0].openingElement.getText(), /showSummary=\{hasManagedPlan\}/);
});

test('hiding management chrome does not hide or discard its recovery dialogs', async () => {
  const source = await read('../src/components/ManagedPlanSettingsCard.tsx');
  const view = finalView(source, 'ManagedPlanSettingsCard');
  assert.ok(ts.isJsxFragment(view));
  const summary = view.children.find((node) => (
    ts.isJsxExpression(node)
    && node.expression
    && ts.isBinaryExpression(node.expression)
    && node.expression.left.getText() === 'showSummary'
    && node.expression.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken
  ));
  assert.ok(summary, 'visibility must apply only to the summary/card, not the dialog owner');
  assert.equal(directElements(view, 'Dialog').length, 4, 'all dialogs stay outside the visibility condition');
  assert.match(source, /showSummary = true/);
  assert.match(source, /useApi<PlanResponse>\(planUrl,\s*\{ enabled: showSummary \}\)/);
  assert.match(source, /enabled: showSummary && plan\?\.adjustments !== undefined/);
});
