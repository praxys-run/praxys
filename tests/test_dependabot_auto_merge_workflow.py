"""Static safeguards for Dependabot patch auto-merge."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "dependabot-auto-merge.yml"


def test_dependabot_auto_merge_is_narrow_and_fail_closed() -> None:
    """Only verified, ungrouped pip/web npm patch PRs may queue auto-merge."""
    workflow = WORKFLOW.read_text(encoding="utf-8").replace("\r\n", "\n")

    assert "pull_request_target:" in workflow
    assert (
        "types: [opened, reopened, synchronize, ready_for_review, "
        "converted_to_draft, edited]"
    ) in workflow
    permissions = workflow.split("permissions:\n", maxsplit=1)[1].split(
        "\n\n", maxsplit=1
    )[0]
    assert permissions == (
        "  actions: read\n"
        "  contents: write\n"
        "  pull-requests: write"
    )
    assert "github.repository == 'praxys-run/praxys'" in workflow
    assert "github.event.pull_request.user.login == 'dependabot[bot]'" in workflow
    assert "github.event.pull_request.base.ref == 'main'" in workflow
    assert "github.event.pull_request.head.repo.full_name == github.repository" in workflow
    assert "github.event.pull_request.draft == false" in workflow
    assert "group: dependabot-auto-merge-${{" in workflow
    assert "cancel-in-progress: true" in workflow

    assert (
        "dependabot/fetch-metadata@25dd0e34f4fe68f24cc83900b1fe3fe149efef98"
        in workflow
    )
    assert "# v3.1.0" in workflow
    assert "skip-verification" not in workflow
    assert "skip-commit-verification" not in workflow
    assert "actions/checkout" not in workflow

    assert "version-update:semver-patch" in workflow
    assert "version-update:semver-minor" not in workflow
    assert "version-update:semver-major" not in workflow
    assert "steps.dependabot.outputs.dependency-group == ''" in workflow
    assert "steps.dependabot.outputs.maintainer-changes == 'false'" in workflow
    assert "steps.dependabot.outputs.package-ecosystem == 'pip'" in workflow
    assert "steps.dependabot.outputs.directory == '/'" in workflow
    assert "steps.dependabot.outputs.package-ecosystem == 'npm_and_yarn'" in workflow
    assert "steps.dependabot.outputs.package-ecosystem == 'npm'" not in workflow
    assert "steps.dependabot.outputs.directory == '/web'" in workflow
    assert "'/miniapp'" not in workflow
    assert "'github-actions'" not in workflow

    assert workflow.index("Disable stale workflow-owned auto-merge") < workflow.index(
        "Verify Dependabot metadata"
    )
    assert ".auto_merge.enabled_by.login // \"\"" in workflow
    assert ".autoMergeRequest" not in workflow
    assert 'owner" == "github-actions[bot]"' in workflow
    assert "--disable-auto" in workflow
    assert "current_author" in workflow
    assert "current_state" in workflow
    assert "current_draft" in workflow
    assert "current_head_repo" in workflow
    assert 'current_head" != "$HEAD_SHA' in workflow
    assert 'current_base" != "main"' in workflow
    assert "/commits?per_page=100" in workflow
    assert "/files?per_page=100" in workflow
    assert workflow.count("--paginate --slurp") == 2
    assert '(.author.login // "") == "dependabot[bot]"' in workflow
    assert "(.commit.verification.verified // false) == true" in workflow
    assert "requirements.txt" in workflow
    assert "web/package.json" in workflow
    assert "web/package-lock.json" in workflow
    assert "current_commit_count" in workflow
    assert "current_file_count" in workflow
    assert "dependabot-auto-merge.yml" in workflow
    assert 'workflow_state" != "active"' in workflow
    assert "--auto --squash --delete-branch" in workflow
    assert '--match-head-commit "$HEAD_SHA"' in workflow
    assert "--admin" not in workflow


def test_dependabot_auto_merge_permissions_are_documented() -> None:
    """The operations handbook must describe activation and rollback."""
    docs = (
        ROOT / "docs" / "ops" / "config-and-secrets.md"
    ).read_text(encoding="utf-8")

    assert "#### Dependabot patch auto-merge" in docs
    assert "dependabot-auto-merge.yml" in docs
    assert "No repository secret or variable is required" in docs
    assert 'gh workflow disable "$workflow_id"' in docs
    assert "gh run cancel" in docs
    assert "--all --limit 1000" in docs
    assert docs.count("disable_pending_dependabot_auto_merges") == 3
    assert "gh pr merge --disable-auto" in docs
