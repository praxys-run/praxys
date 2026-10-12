"""Every-call Science observation, equivalent digest and fail-closed invalidation."""
import hashlib
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import threading

import pytest
from api import dfa_policy
from analysis import science_artifacts as artifacts


def test_digest_preserves_path_order_modes_and_all_bytes(tmp_path):
    # Path ordering differs from a flat string sort at directory boundaries.
    values = {'a/z': b'first', 'a.txt': b'second', '.hidden/value': b'\x00last'}
    expected = hashlib.sha256()
    for name in sorted(values, key=lambda name: Path(name)):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(values[name]);path.chmod(0o640)
        expected.update(name.encode());expected.update(b'416');expected.update(values[name])
    (tmp_path / 'empty').mkdir()
    assert dfa_policy.fingerprint(tmp_path) == expected.hexdigest()


@pytest.mark.parametrize('target', ['file', 'directory', 'missing'])
def test_symlinks_fail_closed_including_directories(tmp_path, target):
    destination = tmp_path / 'target'
    if target == 'file': destination.write_bytes(b'content')
    elif target == 'directory': destination.mkdir()
    (tmp_path / 'link').symlink_to(destination, target_is_directory=target == 'directory')
    with pytest.raises(ValueError, match='symlink'): dfa_policy.fingerprint(tmp_path)


@pytest.mark.parametrize('mutation', ['bytes_same_size_mtime', 'mode', 'add', 'remove'])
def test_warm_validation_always_observes_fresh_tree(tmp_path, monkeypatch, mutation):
    file = tmp_path / 'STOP';file.write_bytes(b'no!')
    monkeypatch.setattr(artifacts, '_SCIENCE_DIR', tmp_path)
    monkeypatch.setattr(dfa_policy, '_cached', None)
    calls = []
    def validator(subject, require_active):
        calls.append(subject)
        return object()
    monkeypatch.setattr(artifacts, 'load_policy_contract', validator)
    first = dfa_policy.validated_contract('synthetic')
    assert dfa_policy.validated_contract('synthetic') is first
    before = file.stat()
    if mutation == 'bytes_same_size_mtime':
        file.write_bytes(b'yes');os.utime(file, ns=(before.st_atime_ns, before.st_mtime_ns))
    elif mutation == 'mode': file.chmod((before.st_mode & 0o777) ^ 0o100)
    elif mutation == 'add': (tmp_path / 'new').write_bytes(b'new')
    else: file.unlink()
    assert dfa_policy.validated_contract('synthetic') is not first
    assert len(calls) == 2


def test_validator_identity_and_subject_are_fresh_cache_keys(tmp_path, monkeypatch):
    monkeypatch.setattr(artifacts, '_SCIENCE_DIR', tmp_path)
    monkeypatch.setattr(dfa_policy, '_cached', None)
    first, second = object(), object()
    monkeypatch.setattr(artifacts, 'load_policy_contract', lambda *a, **kw: first)
    assert dfa_policy.validated_contract('one') is first
    calls = []
    def replacement(subject, **kwargs): calls.append(subject);return second
    monkeypatch.setattr(artifacts, 'load_policy_contract', replacement)
    assert dfa_policy.validated_contract('one') is second
    assert dfa_policy.validated_contract('two') is second
    assert calls == ['one', 'two']


def test_change_during_real_validation_bracket_does_not_publish_cache(tmp_path, monkeypatch):
    file = tmp_path / 'STOP';file.write_bytes(b'no')
    monkeypatch.setattr(artifacts, '_SCIENCE_DIR', tmp_path)
    monkeypatch.setattr(dfa_policy, '_cached', None)
    entered, release = threading.Event(), threading.Event()
    def validator(*args, **kwargs):
        entered.set();assert release.wait(5)
        return object()
    monkeypatch.setattr(artifacts, 'load_policy_contract', validator)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(dfa_policy.validated_contract, 'synthetic')
        try:
            assert entered.wait(5)
            file.write_bytes(b'yes')
        finally: release.set()
        with pytest.raises(ValueError, match='changed during validation'): future.result(timeout=5)
    assert dfa_policy._cached is None


@pytest.mark.parametrize('bound', ['count', 'bytes'])
def test_tree_validation_bounds_remain_enforced(tmp_path, bound):
    if bound == 'count':
        for index in range(4097): (tmp_path / str(index)).touch()
    else:
        with (tmp_path / 'oversized').open('wb') as stream: stream.truncate(32 * 1024 * 1024 + 1)
    with pytest.raises(ValueError, match='validation bound'): dfa_policy.fingerprint(tmp_path)


@pytest.mark.parametrize('replacement', ['symlink', 'directory'])
def test_entry_replacement_before_metadata_is_denied(tmp_path, monkeypatch, replacement):
    file = tmp_path / 'file';file.write_bytes(b'content')
    original = Path.stat
    changed = False
    def replace_then_stat(path, *args, **kwargs):
        nonlocal changed
        if path == file and not changed:
            changed = True;file.unlink()
            if replacement == 'directory': file.mkdir()
            else: file.symlink_to(tmp_path / 'missing')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'stat', replace_then_stat)
    with pytest.raises(ValueError): dfa_policy.fingerprint(tmp_path)


@pytest.mark.parametrize('boundary', ['queued_directory', 'nested_ancestor', 'root_read', 'cache_return', 'directory_identity'])
def test_warmed_cache_rejects_directory_substitution(tmp_path, monkeypatch, boundary):
    import shutil
    science = tmp_path / 'science'
    nested = science / 'outer' / 'inner'
    nested.mkdir(parents=True)
    file = nested / 'content';file.write_bytes(b'identical');file.chmod(0o640)
    monkeypatch.setattr(artifacts, '_SCIENCE_DIR', science)
    monkeypatch.setattr(dfa_policy, '_cached', None)
    contract = object()
    monkeypatch.setattr(artifacts, 'load_policy_contract', lambda *args, **kwargs: contract)
    assert dfa_policy.validated_contract('synthetic') is contract
    subject = science if boundary == 'root_read' else science / 'outer'
    target = tmp_path / 'identical-target'
    shutil.copytree(subject, target)
    replaced = False
    def replace():
        nonlocal replaced
        if replaced: return
        replaced = True
        subject.rename(tmp_path / 'detached')
        if boundary == 'directory_identity': shutil.copytree(target, subject)
        else: subject.symlink_to(target, target_is_directory=True)
    real_scan = os.scandir
    def scan(path):
        # Replacement occurs after classification/queueing, immediately before
        # a queued scan, or after its ancestor was already traversed.
        trigger = science / 'outer' if boundary in ('queued_directory', 'directory_identity') else nested
        if boundary in ('queued_directory', 'nested_ancestor', 'directory_identity') and Path(path) == trigger:
            replace()
        return real_scan(path)
    if boundary in ('queued_directory', 'nested_ancestor', 'directory_identity'):
        monkeypatch.setattr(os, 'scandir', scan)
    elif boundary == 'root_read':
        original = Path.read_bytes
        def read(path):
            if path == file: replace()
            return original(path)
        monkeypatch.setattr(Path, 'read_bytes', read)
    else:
        lock = dfa_policy._lock
        class ReplaceAtCacheBoundary:
            def __enter__(self): lock.acquire();replace()
            def __exit__(self, *args): lock.release()
        monkeypatch.setattr(dfa_policy, '_lock', ReplaceAtCacheBoundary())
    with pytest.raises(ValueError): dfa_policy.validated_contract('synthetic')
    assert replaced


def test_configured_root_symlink_is_denied_before_cache_use(tmp_path, monkeypatch):
    root = tmp_path / 'real';root.mkdir();(root / 'content').write_bytes(b'value')
    alias = tmp_path / 'alias';alias.symlink_to(root, target_is_directory=True)
    monkeypatch.setattr(artifacts, '_SCIENCE_DIR', root)
    monkeypatch.setattr(dfa_policy, '_cached', None)
    calls = []
    def validator(*args, **kwargs): calls.append(True);return object()
    monkeypatch.setattr(artifacts, 'load_policy_contract', validator)
    dfa_policy.validated_contract('synthetic')
    monkeypatch.setattr(artifacts, '_SCIENCE_DIR', alias)
    with pytest.raises(ValueError, match='symlink'): dfa_policy.validated_contract('synthetic')
    assert len(calls) == 1


def test_outer_root_ancestor_substitution_is_denied(tmp_path, monkeypatch):
    import shutil
    outer = tmp_path / 'container';root = outer / 'science';root.mkdir(parents=True)
    file = root / 'content';file.write_bytes(b'identical')
    target = tmp_path / 'identical-container';shutil.copytree(outer, target)
    monkeypatch.setattr(artifacts, '_SCIENCE_DIR', root)
    monkeypatch.setattr(dfa_policy, '_cached', None)
    contract = object()
    monkeypatch.setattr(artifacts, 'load_policy_contract', lambda *args, **kwargs: contract)
    dfa_policy.validated_contract('synthetic')
    original = Path.read_bytes
    def read(path):
        if path == file:
            outer.rename(tmp_path / 'detached-container')
            outer.symlink_to(target, target_is_directory=True)
        return original(path)
    monkeypatch.setattr(Path, 'read_bytes', read)
    with pytest.raises(ValueError, match='symlink'): dfa_policy.validated_contract('synthetic')


def test_scandir_handle_is_closed_when_traversal_rejects(tmp_path, monkeypatch):
    (tmp_path / 'link').symlink_to(tmp_path / 'missing')
    original = os.scandir
    closed = []
    class TrackedScan:
        def __init__(self, path): self.scan = original(path)
        def __enter__(self): return self.scan.__enter__()
        def __exit__(self, *args):
            try: return self.scan.__exit__(*args)
            finally: closed.append(True)
    monkeypatch.setattr(os, 'scandir', TrackedScan)
    with pytest.raises(ValueError, match='symlink'): dfa_policy.fingerprint(tmp_path)
    assert closed == [True]
