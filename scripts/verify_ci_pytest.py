"""Fail closed on missing, mismatched or incomplete same-run pytest artifacts."""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.ci_pytest import validate_evidence, write_json
from scripts.ci_shards import DEFAULT_WEIGHTS, load_weights


def identity(result: dict) -> dict:
    fields = ('git_revision', 'python_version', 'platform', 'architecture', 'dependencies',
              'submodules', 'requested_paths', 'weights_sha256')
    if any(key not in result for key in fields):
        raise ValueError('Missing runtime identity')
    if any(not isinstance(result[key], str) or not result[key]
           for key in ('git_revision', 'python_version', 'platform', 'architecture', 'weights_sha256')):
        raise ValueError('Invalid runtime identity')
    dependencies = result['dependencies']
    packages = dependencies['packages']
    if (not isinstance(packages, list) or not packages or any(not isinstance(item, dict)
            or set(item) != {'name', 'version'} or not all(isinstance(value, str) and value for value in item.values())
            for item in packages)):
        raise ValueError('Invalid dependency identity')
    encoded = json.dumps(packages, sort_keys=True, separators=(',', ':')).encode()
    if dependencies.get('sha256') != sha256(encoded).hexdigest():
        raise ValueError('Dependency fingerprint does not match package identity')
    if (result.get('tracked_changes_present') is not False or not isinstance(result['submodules'], list)
            or any(not isinstance(line, str) or not line.startswith(' ') for line in result['submodules'])):
        raise ValueError('Checkout or submodule state is not immutable and initialized')
    if result['requested_paths'] != ['tests/']:
        raise ValueError('Required CI must request the complete tests/ suite')
    return {key: result[key] for key in fields}


def outcomes(data: dict) -> Counter:
    # Ignore timings, retain both expected skips and unexpected passes. Module
    # collection skips are compared separately because both shards observe them.
    return Counter((item['nodeid'], item['phase'], item['outcome'], item.get('reason'),
                    item.get('wasxfail'), item.get('strict_xpass')) for item in data['phases'])


def collection_outcomes(data: dict) -> Counter:
    return Counter((item['nodeid'], item['outcome'], item.get('reason'))
                   for item in data['collection_reports'])


def verify(artifacts: Path, *, mode: str, expected_sha: str, repository: str,
           run_id: str, run_attempt: str, weights_path: Path = DEFAULT_WEIGHTS) -> dict:
    expected = {'serial': {(1, 0)}, 'sharded': {(2, 0), (2, 1)},
                'compare': {(1, 0), (2, 0), (2, 1)}}[mode]
    weights, digest = load_weights(weights_path)
    manifests = sorted(artifacts.rglob('result.json'))
    if len(manifests) != len(expected):
        raise ValueError('Missing or extra execution artifacts')
    records, reference = {}, None
    for path in manifests:
        result = json.loads(path.read_text())
        key = result.get('shard_count'), result.get('shard_index')
        if (type(result.get('schema_version')) is not int or result.get('schema_version') != 1
                or any(type(value) is not int for value in key)
                or key not in expected or key in records):
            raise ValueError('Duplicate or unexpected execution identity')
        if (result.get('completed') is not True or result.get('evidence_complete') is not True
                or type(result.get('exit_code')) is not int or result['exit_code'] != 0
                or type(result.get('child_exit_code')) is not int or result['child_exit_code'] != 0
                or result.get('errors') != []):
            raise ValueError('Execution failed, cancelled, or incomplete')
        if result.get('git_revision') != expected_sha or result.get('weights_sha256') != digest:
            raise ValueError('Artifacts differ from verifier checkout or weights')
        github = result.get('github')
        if github != dict(GITHUB_REPOSITORY=repository, GITHUB_RUN_ID=run_id,
                          GITHUB_RUN_ATTEMPT=run_attempt, GITHUB_SHA=expected_sha):
            raise ValueError('Artifact is not from this repository/run/attempt/head')
        current = identity(result)
        if reference is None:
            reference = current
        elif current != reference:
            raise ValueError('Runtime identity differs between executions')
        data = json.loads((path.parent / 'phases.json').read_text())
        errors = validate_evidence(data, weights=weights)
        if any(data.get(name) != result.get(name) for name in ('mode', 'shard_count', 'shard_index', 'weights_sha256')):
            errors.append('Phase/report identity differs')
        if type(data.get('exit_code')) is not int or data['exit_code'] != 0:
            errors.append('Phase report did not finish successfully')
        junit = ET.parse(path.parent / 'junit.xml')
        if junit.getroot().tag not in {'testsuites', 'testsuite'} or len(list(junit.iter('testcase'))) < len(data['selected']):
            errors.append('JUnit evidence missing selected tests')
        if errors:
            raise ValueError('; '.join(errors))
        records[key] = data
    if set(records) != expected:
        raise ValueError('Incomplete execution set')
    full = next(iter(records.values()))['full_collected']
    common_collection = collection_outcomes(next(iter(records.values())))
    if any(set(data['full_collected']) != set(full) or collection_outcomes(data) != common_collection for data in records.values()):
        raise ValueError('Full collection or collection skips disagree')
    if mode in {'sharded', 'compare'}:
        first, second = records[2, 0], records[2, 1]
        left, right = set(first['selected']), set(second['selected'])
        if left & right or left | right != set(full):
            raise ValueError('Shards are not a disjoint complete union')
        if mode == 'compare' and outcomes(records[1, 0]) != outcomes(first) + outcomes(second):
            raise ValueError('Serial and sharded outcomes, skips or xfails differ')
    return dict(schema_version=1, verified=True, mode=mode, git_revision=expected_sha,
                repository=repository, run_id=run_id, run_attempt=run_attempt,
                collected_count=len(full), executions=len(records),
                activation_authorized=False,
                note='Coverage evidence only; completed job timing and explicit review govern activation.')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--mode', choices=('serial', 'sharded', 'compare'), required=True)
    parser.add_argument('--expected-sha', required=True)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--run-attempt', required=True)
    parser.add_argument('--weights', type=Path, default=DEFAULT_WEIGHTS)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = verify(args.artifacts, mode=args.mode, expected_sha=args.expected_sha,
                        repository=args.repository, run_id=args.run_id, run_attempt=args.run_attempt,
                        weights_path=args.weights)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ET.ParseError) as error:
        result = dict(schema_version=1, verified=False, error=str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, result)
    print(json.dumps(result))
    return 0 if result['verified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
