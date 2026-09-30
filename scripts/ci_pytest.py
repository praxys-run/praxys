"""Run every backend test serially and retain auditable timing/completion evidence."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.ci_shards import DEFAULT_WEIGHTS, load_weights, selected_nodes


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def dependency_identity() -> dict:
    # Do not use pip freeze: direct installation URLs can contain credentials.
    packages = sorted(({'name': dist.metadata['Name'], 'version': dist.version}
                       for dist in metadata.distributions()), key=lambda item: (item['name'], item['version']))
    encoded = json.dumps(packages, sort_keys=True, separators=(',', ':')).encode()
    return dict(packages=packages, sha256=sha256(encoded).hexdigest())


def validate_evidence(data: dict, *, weights: dict | None = None) -> list[str]:
    errors = []
    if type(data.get('schema_version')) is not int or data.get('schema_version') != 1 or data.get('mode') not in {'serial', 'sharded'}:
        errors.append('unsupported evidence format')
    if data.get('session_finished') is not True or data.get('collection_complete') is not True:
        errors.append('collection or session incomplete')
    collected, selected, before = data.get('full_collected'), data.get('selected'), data.get('pre_shard_selected')
    if not all(isinstance(nodes, list) for nodes in (collected, selected, before)):
        return [*errors, 'missing collection lists']
    if not all(isinstance(node, str) for nodes in (collected, selected, before) for node in nodes):
        return [*errors, 'invalid node IDs']
    if not collected or any(len(nodes) != len(set(nodes)) for nodes in (collected, selected, before)):
        errors.append('empty or duplicate collection')
    count, index = data.get('shard_count'), data.get('shard_index')
    if (type(count) is not int or type(index) is not int or count not in (1, 2)
            or index not in range(count) or data.get('mode') != ('serial' if count == 1 else 'sharded')):
        errors.append('invalid shard identity')
    if set(before) != set(collected) or data.get('deselected') != []:
        errors.append('unexpected test deselection before sharding')
    if count == 1 and set(collected) != set(selected):
        errors.append('serial run unexpectedly omitted tests')
    elif count == 2:
        if weights is None or index not in (0, 1) or set(selected) != set(selected_nodes(collected, index, weights)):
            errors.append('shard selection differs from complete file plan')
    phases = data.get('phases')
    if not isinstance(phases, list):
        return [*errors, 'missing phase reports']
    seen: dict[str, set[str]] = {}
    setup_outcomes: dict[str, str] = {}
    selected_set = set(selected)
    for report in phases:
        if not isinstance(report, dict) or report.get('nodeid') not in selected_set:
            errors.append('unexpected phase report')
            continue
        node, phase = report['nodeid'], report.get('phase')
        prior = seen.setdefault(node, set())
        duration = report.get('duration_seconds')
        if (phase not in {'setup', 'call', 'teardown'} or phase in prior
                or report.get('outcome') not in {'passed', 'failed', 'skipped'}
                or type(duration) not in (float, int) or not 0 <= duration < float('inf')):
            errors.append('invalid or duplicate phase report')
        prior.add(phase)
        if phase == 'setup':
            setup_outcomes[node] = report.get('outcome')
        if report.get('outcome') == 'failed':
            errors.append(f'failed {phase}: {node}')
    for node in selected:
        if not {'setup', 'teardown'} <= seen.get(node, set()):
            errors.append(f'incomplete execution: {node}')
        if setup_outcomes.get(node) == 'passed' and 'call' not in seen.get(node, set()):
            errors.append(f'missing call: {node}')
    if not any(isinstance(item, dict) and item.get('phase') == 'call'
               and item.get('outcome') == 'passed' for item in phases):
        errors.append('no passing test calls; all-skipped run is not full validation')
    if any(item.get('outcome') == 'failed' for item in data.get('collection_reports', [])):
        errors.append('collection failed')
    return errors


def run(output: Path, paths: list[str], *, shard_count: int = 1, shard_index: int = 0,
        weights_path: Path = DEFAULT_WEIGHTS) -> int:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifest_path, report_path, junit_path = output / 'result.json', output / 'phases.json', output / 'junit.xml'
    manifest = dict(schema_version=1, mode='serial' if shard_count == 1 else 'sharded',
                    shard_count=shard_count, shard_index=shard_index, requested_paths=paths,
                    started_at=datetime.now(timezone.utc).isoformat(), completed=False,
                    evidence_complete=False, child_exit_code=None, exit_code=None,
                    elapsed_seconds=None, errors=[])
    # Replace old success before any metadata probe or cleanup can fail.
    write_json(manifest_path, manifest)
    # Never admit artifacts from a previous invocation using the same directory.
    try:
        if shard_count not in (1, 2) or shard_index not in range(shard_count):
            raise ValueError('invalid shard index/count')
        weights, weights_digest = load_weights(weights_path)
        manifest['weights_sha256'] = weights_digest
        for path in (report_path, junit_path):
            path.unlink(missing_ok=True)
        revision = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'],
                                  capture_output=True, text=True, check=True).stdout.strip()
        submodules = subprocess.run(['git', '-C', str(ROOT), 'submodule', 'status', '--recursive'],
                                   capture_output=True, text=True, check=True).stdout.splitlines()
        dirty = subprocess.run(['git', '-C', str(ROOT), 'status', '--porcelain', '--untracked-files=no'],
                              capture_output=True, text=True, check=True).stdout
        manifest.update(git_revision=revision, tracked_changes_present=bool(dirty), submodules=submodules,
                        platform=platform.system(), architecture=platform.machine(),
                        python_version=sys.version, dependencies=dependency_identity(),
                        github={name: os.environ.get(name) for name in (
                            'GITHUB_REPOSITORY', 'GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT', 'GITHUB_SHA')})
    except (OSError, ValueError, TypeError, subprocess.CalledProcessError) as error:
        manifest.update(completed=True, exit_code=2, errors=[f'initialization failure: {type(error).__name__}'])
        write_json(manifest_path, manifest)
        print(manifest['errors'][0], file=sys.stderr)
        return 2
    write_json(manifest_path, manifest)
    command = [sys.executable, '-m', 'pytest', '-p', 'scripts.ci_pytest_plugin',
               '--ci-report', str(report_path), '--junitxml', str(junit_path),
               '--ci-shard-count', str(shard_count), '--ci-shard-index', str(shard_index),
               '--ci-weights', str(weights_path.resolve()),
               '-v', '--durations=30', *paths]
    started = time.monotonic()
    child = None
    handlers = {}
    def forward(signum, _frame):
        if child is not None and child.poll() is None:
            try:
                os.killpg(child.pid, signum)
            except ProcessLookupError:
                pass
    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            handlers[signum] = signal.signal(signum, forward)
        child = subprocess.Popen(command, cwd=ROOT, start_new_session=True)
        status = child.wait()
        manifest['child_exit_code'] = status
        exit_code = status if status >= 0 else 128 - status
        try:
            evidence = json.loads(report_path.read_text(encoding='utf-8'))
            if not isinstance(evidence, dict):
                raise ValueError('phase report must be an object')
            errors = validate_evidence(evidence, weights=weights)
            if any(evidence.get(key) != manifest[key] for key in ('mode', 'shard_count', 'shard_index', 'weights_sha256')):
                errors.append('pytest shard identity differs from wrapper')
            if evidence.get('exit_code') != status:
                errors.append('pytest report and process exit disagree')
            tree = ET.parse(junit_path)
            if tree.getroot().tag not in {'testsuites', 'testsuite'}:
                errors.append('invalid JUnit root')
            if len(list(tree.iter('testcase'))) < len(evidence.get('selected', [])):
                errors.append('JUnit omits selected tests')
            manifest['evidence_complete'] = not errors
            manifest['errors'] = errors
        except (OSError, ValueError, TypeError, AttributeError, ET.ParseError) as error:
            manifest['errors'] = [f'evidence unavailable or malformed: {type(error).__name__}']
        if manifest['errors'] and exit_code == 0:
            exit_code = 2
        manifest.update(completed=True, exit_code=exit_code)
    except (OSError, ValueError) as error:
        manifest.update(completed=True, exit_code=2, errors=[f'runner failure: {type(error).__name__}'])
    finally:
        for signum, handler in handlers.items():
            signal.signal(signum, handler)
        manifest['elapsed_seconds'] = time.monotonic() - started
        manifest['finished_at'] = datetime.now(timezone.utc).isoformat()
        write_json(manifest_path, manifest)
    if manifest['errors']:
        print('CI evidence failed: ' + '; '.join(manifest['errors']), file=sys.stderr)
    return manifest['exit_code']


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--shard-count', type=int, choices=(1, 2), default=1)
    parser.add_argument('--shard-index', type=int, choices=(0, 1), default=0)
    parser.add_argument('--weights', type=Path, default=DEFAULT_WEIGHTS)
    parser.add_argument('paths', nargs='*', help='Optional explicit test paths after --; default tests/')
    args = parser.parse_args(argv)
    if any(path.startswith('-') for path in args.paths):
        parser.error('only test paths are accepted, not pytest selection/options')
    try:
        return run(args.output_dir, args.paths or ['tests/'], shard_count=args.shard_count,
                   shard_index=args.shard_index, weights_path=args.weights)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f'Cannot initialize/write CI evidence: {type(error).__name__}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
