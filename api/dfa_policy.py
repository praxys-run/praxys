"""Cache validated immutable Science content; every call rehashes bytes and modes.

This caches only the common scientific contract, never origin rights or results.
Any STOP, approval, contract, evidence, file-mode or validator change invalidates
it immediately. Two matching tree observations bracket first validation.
"""
import hashlib
from pathlib import Path
import threading

_lock=threading.Lock()
_cached=None


def fingerprint(root: Path) -> str:
    value=hashlib.sha256()
    count=total=0
    for path in sorted(root.rglob('*')):
        if path.is_symlink(): raise ValueError('Science symlink is unsupported')
        if not path.is_file(): continue
        count+=1
        total+=path.stat().st_size
        if count>4096 or total>32*1024*1024: raise ValueError('Science tree exceeds validation bound')
        value.update(path.relative_to(root).as_posix().encode())
        value.update(str(path.stat().st_mode & 0o777).encode())
        value.update(path.read_bytes())
    return value.hexdigest()


def validated_contract(subject):
    global _cached
    from analysis import science_artifacts as artifacts
    root=Path(artifacts._SCIENCE_DIR).resolve()
    observed=fingerprint(root)
    validator=artifacts.load_policy_contract
    key=(str(root),subject,observed,validator)
    with _lock:
        if _cached and _cached[0]==key:
            return _cached[1]
        contract=validator(subject,require_active=True)
        if fingerprint(root)!=observed: raise ValueError('Science changed during validation')
        _cached=(key,contract)
        return contract
