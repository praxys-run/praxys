function actOnDFAFixture(action, value) {
  const page = getCurrentPages().slice(-1)[0];
  if (!page || page.route !== 'pages/analysis/index') throw new Error('expected_existing_analysis_page');
  const component = page.selectComponent('dfa-analysis');
  if (!component || component.properties.activityId !== 'dfa-synthetic-running') throw new Error('synthetic_dfa_component_required');
  if (action === 'comparator') return component.onComparator({detail: {value: String(value)}});
  if (action === 'source-check') return component.onCheck({detail: {value: value ? ['confirmed'] : []}});
  if (action === 'confirm') return component.confirm();
  if (action === 'revoke') return component.deletePrompt({currentTarget: {dataset: {scope: 'proof'}}});
  if (action === 'delete') return component.deletePrompt({currentTarget: {dataset: {scope: 'all'}}});
  if (action === 'erase') return component.erase();
  if (action === 'cancel') return component.action({currentTarget: {dataset: {action: 'cancel'}}});
  if (action === 'refresh') return component.refresh();
  if (action === 'state') return {loading: component.data.loading, checked: component.data.checked, active: component.data.active, hasResult: component.data.hasResult, comparator: component.data.comparator, rowCount: component.data.rows.length, contextLabel: component.data.comparatorSeries[0] && component.data.comparatorSeries[0].label};
  throw new Error('unknown_fixture_action');
}
