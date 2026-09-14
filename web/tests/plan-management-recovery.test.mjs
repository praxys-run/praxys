import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import vm from 'node:vm';
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

function initializer(source, name) {
  const file = ts.createSourceFile('card.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  let value;
  const visit = (node) => {
    if (ts.isVariableDeclaration(node) && node.name.getText(file) === name) {
      value = node.initializer?.getText(file);
    }
    ts.forEachChild(node, visit);
  };
  visit(file);
  assert.ok(value, `${name} exists in the actual component`);
  return value;
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

test('cleanup restores focus to the surviving Training region when its trigger disappears', async () => {
  const planSource = await read('../src/components/PlanStart.tsx');
  const planView = finalView(planSource, 'PlanStart');
  assert.match(planView.openingElement.getText(), /ref=\{planStartRegion\}/);
  assert.match(planView.openingElement.getText(), /tabIndex=\{-1\}/);
  assert.match(directElements(planView, 'ManagedPlanSettingsCard')[0].openingElement.getText(),
    /cleanupReturnFocusRef=\{planStartRegion\}/);

  const cardSource = await read('../src/components/ManagedPlanSettingsCard.tsx');
  const leaveDialog = directElements(finalView(cardSource, 'ManagedPlanSettingsCard'), 'Dialog')
    .find((node) => /open=\{leaveOpen\}/.test(node.openingElement.getText()));
  assert.ok(leaveDialog);
  const popup = directElements(leaveDialog, 'DialogContent')[0];
  assert.match(popup.openingElement.getText(), /ref=\{cleanupDialogRef\}/);
  assert.match(popup.openingElement.getText(),
    /finalFocus=\{!showSummary \? cleanupReturnFocusRef : undefined\}/);
});

for (const handler of ['leaveManagedMode', 'retryCleanup']) {
  for (const outcome of ['partial', 'complete', 'error']) {
    test(`${handler} keeps focus inside the dialog before disabling actions (${outcome})`, async () => {
      const source = await read('../src/components/ManagedPlanSettingsCard.tsx');
      let focused = 'action-button';
      let action;
      let actionError = null;
      let cleanupResult = null;
      let cleanupCalls = 0;
      let closed = false;
      const run = vm.runInNewContext(`(${initializer(source, handler)})`, {
        Error,
        cleanupDialogRef: { current: { focus: (options) => {
          assert.equal(options.preventScroll, true);
          focused = 'cleanup-dialog';
        } } },
        setAction: (value) => {
          if (value != null) {
            assert.equal(focused, 'cleanup-dialog', 'focus must move before disabling the active button');
          }
          action = value;
        },
        setActionError: (value) => { actionError = value; },
        setCleanupResult: (value) => { cleanupResult = value; },
        updateSettings: async () => {},
        leaveChoice: 'remove',
        cleanupFutureDeliveries: async () => {
          cleanupCalls += 1;
          if (outcome === 'error') throw new Error('Synthetic cleanup failure');
          return { status: outcome };
        },
        refetchPlan: async () => {},
        resetLeaveDialog: (open) => { closed = !open; },
        t: (parts) => parts.join(''),
      });
      await run();
      assert.equal(cleanupCalls, 1);
      assert.equal(action, null);
      assert.equal(focused, 'cleanup-dialog');
      assert.equal(closed, outcome === 'complete');
      assert.equal(actionError, outcome === 'error' ? 'Synthetic cleanup failure' : null);
      assert.equal(cleanupResult?.status ?? null, outcome === 'error' ? null : outcome);
    });
  }
}
