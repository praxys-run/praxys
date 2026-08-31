"""Static safeguards for the automated translation workflow."""
from pathlib import Path


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
    assert "for workflow in ci-premerge.yml miniapp-build.yml" in validation
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
