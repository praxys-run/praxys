"""Static safeguards for the automated translation workflow."""
from pathlib import Path
import json
import os
import subprocess
import sys

import pytest
import yaml


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "i18n.yml"


def _step(name: str) -> str:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    marker = f"      - name: {name}"
    start = workflow.index(marker)
    end = workflow.find("\n      - name:", start + len(marker))
    return workflow[start:] if end == -1 else workflow[start:end]


def test_translator_step_imports_the_shared_llm_factory_after_install():
    """Keep the lean workflow aligned with api.llm top-level imports."""
    step = _step("Install and verify translator deps")

    assert "pip install openai azure-identity pyyaml portalocker" in step
    assert 'python -c "from api.llm import get_automation_client"' in step


def test_generated_translation_pr_is_unique_draft_and_human_reviewed():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    branch = (
        "branch: i18n/refresh-zh-${{ github.sha }}-"
        "${{ github.run_id }}-${{ github.run_attempt }}"
    )
    assert branch in workflow
    assert workflow.count("'scripts/i18n_semantics.py'") == 2
    assert "draft: true" in workflow
    assert "A maintainer must review the full diff" in workflow
    assert "never lower review requirements automatically" in workflow
    assert "--human-review-report /tmp/i18n-human-review.md" in workflow
    assert "--source-root web" in workflow
    manifest = _step("Attach human-review manifest to draft PR")
    assert 'cat /tmp/i18n-human-review.md >> "$body_file"' in manifest
    assert 'gh pr edit "$PR_NUMBER" --body-file "$body_file"' in manifest
    assert "uses: actions/upload-artifact@v7" in workflow
    artifact_name = (
        "i18n-human-review-"
        "${{ steps.create-pr.outputs.pull-request-number }}-"
        "${{ steps.generated-head.outputs.head_sha }}"
    )
    assert artifact_name in workflow
    evidence = _step("Store human-review manifest as reviewer evidence")
    assert "if: steps.create-pr.outputs.pull-request-number != ''" in evidence
    assert "always()" not in evidence


def test_exact_head_status_waits_for_both_dispatched_workflows():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "statuses: write" in workflow
    assert "context=translation-validation" in workflow
    assert "-f state=pending" in workflow
    assert "-f state=\"$state\"" in workflow
    bind = _step("Bind generated translation head and mark pending")
    assert "pulls/${PR_NUMBER}" in bind
    assert '.head.sha' in bind
    assert "current_head" in bind and "ACTION_HEAD_SHA" in bind
    validation = _step("Dispatch required validation on translation head")
    assert "for workflow in ci-premerge.yml; do" in validation
    assert validation.count('gh workflow run ci-premerge.yml --ref "$PR_BRANCH"') == 1
    assert 'gh workflow run miniapp-build.yml' not in validation
    assert 'Unified pre-merge CI (including miniapp checks)' in workflow
    assert "select(.headSha == \\\"$HEAD_SHA\\\")" in validation
    assert 'gh run watch "$dispatched_run_id" --exit-status' in validation
    publish = _step("Publish generated translation validation status")
    assert "continue-on-error: true" in publish
    assert "steps.generated-head.outputs.head_sha != ''" in publish
    success_condition = (
        'if [ "$QUALITY_OUTCOME" = "success" ] '
        '&& [ "$MANIFEST_OUTCOME" = "success" ] '
        '&& [ "$EVIDENCE_OUTCOME" = "success" ] '
        '&& [ "$VALIDATION_OUTCOME" = "success" ]'
    )
    assert success_condition in publish
    assert "human copy review is still required" in publish
    quality = _step("Enforce Chinese terminology, structure, and typography")
    assert "continue-on-error: true" in quality
    assert "QUALITY_OUTCOME: ${{ steps.quality.outcome }}" in publish
    fail = _step("Fail when generated PR needs human repair")
    assert "always()" in fail
    assert "steps.generated-head.outcome == 'failure'" in fail
    assert "steps.quality.outcome == 'failure'" in fail
    condition = fail.split("if:", 1)[1].split("\n", 1)[0]
    assert condition.index("steps.quality.outcome == 'failure'") < condition.index(
        "steps.create-pr.outputs.pull-request-number != ''"
    )
    assert "steps.review-evidence.outcome == 'failure'" in fail
    assert "steps.publish-status.outcome == 'failure'" in fail
    policy = _step("Dispatch and wait for selective-review policy")
    assert "gh workflow run selective-review.yml" in policy
    assert "selective-review-policy" in policy
    assert "steps.publish-status.outputs.state == 'success'" in policy


def test_science_yaml_is_outside_translation_automation():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "Fill missing zh science YAML" not in workflow
    assert "--source-dir data/science" not in workflow
    assert "Science YAML stays" in workflow


@pytest.mark.parametrize('listed,watch_exit,expected', [(True, 0, 0), (False, 0, 1), (True, 1, 1)])
def test_unified_dispatch_waits_for_exact_head_and_propagates_failure(tmp_path, listed, watch_exit, expected):
    workflow = yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)
    command = next(step['run'] for step in workflow['jobs']['translate']['steps']
                   if step.get('name') == 'Dispatch required validation on translation head')
    binary = tmp_path / 'bin'
    binary.mkdir()
    gh = binary / 'gh'
    gh.write_text(f'#!{sys.executable}\n' + '''import json,os,sys
from pathlib import Path
args=sys.argv[1:]
with Path(os.environ['CALL_LOG']).open('a') as stream: stream.write(json.dumps(args)+'\\n')
if args[:2]==['workflow','run']:
    assert args[2:]==['ci-premerge.yml','--ref',os.environ['PR_BRANCH']]
elif args[:2]==['run','list']:
    assert args[args.index('--workflow')+1]=='ci-premerge.yml'
    assert args[args.index('--branch')+1]==os.environ['PR_BRANCH']
    assert args[args.index('--event')+1]=='workflow_dispatch'
    assert 'select(.headSha == "'+os.environ['HEAD_SHA']+'")' in args[args.index('--jq')+1]
    if os.environ['LISTED']=='true': print('42')
elif args[:2]==['run','watch']:
    assert args[2:]==['42','--exit-status']
    raise SystemExit(int(os.environ['WATCH_EXIT']))
else: raise AssertionError(args)
''')
    gh.chmod(0o755)
    sleep = binary / 'sleep'
    sleep.write_text('#!/bin/sh\nexit 0\n')
    sleep.chmod(0o755)
    log = tmp_path / 'calls.jsonl'
    environment = dict(os.environ, PATH=f'{binary}:/usr/bin:/bin', CALL_LOG=str(log),
                       PR_BRANCH='synthetic-i18n-branch', HEAD_SHA='a' * 40,
                       LISTED=str(listed).lower(), WATCH_EXIT=str(watch_exit))
    result = subprocess.run(['bash', '-c', command], cwd=tmp_path, env=environment,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == expected, result.stdout + result.stderr
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert len([call for call in calls if call[:2] == ['workflow', 'run']]) == 1
    assert len([call for call in calls if call[:2] == ['run', 'watch']]) == int(listed)
