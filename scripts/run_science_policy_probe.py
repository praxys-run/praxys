"""Trusted completion controller; candidate code runs only in a bounded child.

A validated child observation is test evidence, not semantic isolation against
arbitrary candidate code forging stdout. Independent source review is required.
"""
from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import tempfile
import time

TRUSTED_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRUSTED_ROOT))
from analysis.evidence_registry import load_science_registry
from analysis.science_activation import project_active_registry, strict_json
from analysis.science_artifacts import build_policy_contract
from analysis.science_implementation_stop import load_implementation_stops
from analysis.science_approval_workflow import _reject_symlinks

SUBJECT = 'sdr-activity-dfa-alpha1-v1'
MODULE_PATHS = {
    'api.activity_dfa': 'api/activity_dfa.py',
    'analysis.activity_dfa': 'analysis/activity_dfa.py',
    'analysis.science_artifacts': 'analysis/science_artifacts.py',
    'analysis.evidence_registry': 'analysis/evidence_registry.py',
    'analysis.science_implementation_stop': 'analysis/science_implementation_stop.py',
}
# Deliberately do not inherit credentials, Python loader overrides, HOME, or
# GitHub environment/output/path command files. Interpreter and script are absolute.
CHILD_ENV = {'PATH': os.defpath, 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8'}


@contextmanager
def prepared_probe(candidate: Path, purpose: str, subject: str, contract_digest: str):
    """Read candidate data with trusted code; never add candidate to sys.path."""
    if subject != SUBJECT or purpose not in {'activation', 'stopped-maintenance'}:
        raise ValueError('Unsupported bounded policy probe')
    candidate = candidate.resolve()
    science = candidate / 'data/science'
    _reject_symlinks(science)
    registry = load_science_registry(science)
    expected = dict(schema_version=1, purpose=purpose, subject_id=subject,
                    contract_digest=contract_digest,
                    module_paths={name: str(candidate / path) for name, path in MODULE_PATHS.items()})
    if purpose == 'activation':
        # Reject an actual stopped proposal before creating a hypothetical fixture.
        contract = build_policy_contract(project_active_registry(registry, subject), subject)
        if contract.contract_digest != contract_digest:
            raise ValueError('Projected contract mismatch')
        parameters = sha256(json.dumps(contract.parameter_values, sort_keys=True,
                            separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        expected['observation'] = dict(returned_contract=contract_digest,
                                       method_version=contract.model_version, parameter_digest=parameters)
        from scripts.check_projected_dfa_policy import synthetic_active_registry
        with synthetic_active_registry(candidate, subject, contract_digest) as (synthetic, _):
            yield synthetic, expected
    else:
        contract = build_policy_contract(registry, subject)
        stops = [stop for stop in load_implementation_stops(science) if stop.subject_id == subject]
        if len(stops) != 1 or contract.contract_digest != contract_digest or stops[0].active_contract_digest != contract_digest:
            raise ValueError('Stopped candidate target mismatch')
        expected['stop_digest'] = stops[0].stop_digest
        expected['observation'] = dict(http_status=503, detail='DFA_SCIENCE_POLICY_INACTIVE')
        yield science, expected


def _same_typed_value(actual, expected) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(_same_typed_value(actual[key], value) for key, value in expected.items())
    return actual == expected


def validate_observation(stdout: bytes, returncode: int, expected: dict) -> dict:
    if returncode != 0:
        raise ValueError('Policy observer did not complete successfully')
    try:
        observed = strict_json(stdout.decode('utf-8'))
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError('Policy observer must emit exactly one complete strict observation') from error
    if not _same_typed_value(observed, expected):
        raise ValueError('Policy observation schema, types, provenance or expected tuple mismatch')
    return observed


def bounded_child(command: list[str], *, cwd: Path, timeout: float = 60, output_limit: int = 16384):
    """Bound aggregate stdout/stderr during capture and terminate child descendants."""
    if not 0 < timeout <= 60 or not 0 < output_limit <= 65536:
        raise ValueError('Invalid policy observer resource bound')
    process = subprocess.Popen(command, cwd=cwd, env=CHILD_ENV, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    stdout = bytearray()
    total = 0
    deadline = time.monotonic() + timeout
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, True)
            selector.register(process.stderr, selectors.EVENT_READ, False)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ValueError('Policy observer exceeded timeout')
                for key, _ in selector.select(remaining):
                    chunk = os.read(key.fileobj.fileno(), min(4096, output_limit - total + 1))
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    total += len(chunk)
                    if total > output_limit:
                        raise ValueError('Policy observer exceeded output limit')
                    if key.data:
                        stdout.extend(chunk)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ValueError('Policy observer exceeded timeout')
            try:
                returncode = process.wait(timeout=remaining)
            except subprocess.TimeoutExpired as error:
                raise ValueError('Policy observer exceeded timeout') from error
            return bytes(stdout), returncode
    finally:
        # Also terminate descendants that retained a pipe or survived their parent.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=2)
        process.stdout.close()
        process.stderr.close()


def observe(candidate: Path, purpose: str, subject: str, contract_digest: str, *, timeout: float = 60, output_limit: int = 16384):
    candidate = candidate.resolve()
    with prepared_probe(candidate, purpose, subject, contract_digest) as (science, expected):
        # The observer starts with stdlib imports only and then imports candidate
        # modules in a fresh interpreter, never this controller's cached modules.
        command = [sys.executable, '-E', '-B', '-P', str(TRUSTED_ROOT / 'scripts/observe_science_policy.py'),
                   str(candidate), str(science), purpose]
        with tempfile.TemporaryDirectory(prefix='policy-observer-cwd-') as temporary:
            stdout, returncode = bounded_child(command, cwd=Path(temporary), timeout=timeout, output_limit=output_limit)
        return validate_observation(stdout, returncode, expected)


def main(purpose: str | None = None):
    observed = observe(Path(os.environ['CANDIDATE_ROOT']), purpose or os.environ['PROBE_PURPOSE'],
                       os.environ['ACTIVATION_SUBJECT'], os.environ['ACTIVATION_CONTRACT'])
    # Only the trusted controller declares completion. No child artifact is
    # uploaded or used by the separately authenticated metadata collector.
    print(json.dumps({**observed, 'controller_completed': True}, sort_keys=True))


if __name__ == '__main__':
    main()
