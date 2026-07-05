"""Throwaway test to verify the #361 pre-merge CI gate blocks a red suite.

This file is NOT meant to land on main — it exists only on the
`ci-gate-verify-fail` branch to prove `backend-tests` goes red and the
required status check blocks the merge. The PR is closed without merging.
"""


def test_ci_gate_intentional_failure() -> None:
    assert False, "intentional failure to verify the CI gate blocks merges"
