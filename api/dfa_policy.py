"""Cache validated immutable Science content; every call rehashes bytes and modes.

This caches common contract validation, including rejections, never origin rights
or results. A cached rejection never confers execution or publication authority.
Any STOP, approval, contract, evidence, file-mode or validator change invalidates
it immediately. Two matching tree observations bracket first validation.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
import stat
from pathlib import Path
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from analysis.science_artifacts import SciencePolicyContract

_lock=threading.Lock()
_cached=None


@dataclass(frozen=True)
class _ValidationRejection:
    message: str


def _directory_identity(path: Path):
    metadata=path.stat(follow_symlinks=False)
    if stat.S_ISLNK(metadata.st_mode):
        raise ValueError('Science symlink is unsupported')
    if not stat.S_ISDIR(metadata.st_mode):
        raise ValueError('Science directory changed during observation')
    return metadata.st_dev,metadata.st_ino


def _check_directories(directories):
    # Ancestors were inserted before descendants. A no-follow check on only a
    # leaf would still follow a substituted ancestor during path resolution.
    for path,identity in directories.items():
        if _directory_identity(path)!=identity:
            raise ValueError('Science directory changed during observation')


def _observe(root: Path):
    root=Path(os.path.abspath(root))
    directories={path:_directory_identity(path) for path in reversed(root.parents)}
    files=[]
    pending=[root]
    while pending:
        directory=pending.pop()
        identity=_directory_identity(directory)
        if directory in directories and directories[directory]!=identity:
            raise ValueError('Science directory changed during observation')
        directories[directory]=identity
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.is_symlink():
                    raise ValueError('Science symlink is unsupported')
                if entry.is_dir(follow_symlinks=False):
                    pending.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    files.append(Path(entry.path))
    _check_directories(directories)
    value=hashlib.sha256()
    total=0
    for count,path in enumerate(sorted(files),start=1):
        metadata=path.stat(follow_symlinks=False)
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError('Science symlink is unsupported')
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError('Science file changed during observation')
        total+=metadata.st_size
        if count>4096 or total>32*1024*1024:
            raise ValueError('Science tree exceeds validation bound')
        value.update(path.relative_to(root).as_posix().encode())
        value.update(str(metadata.st_mode & 0o777).encode())
        value.update(path.read_bytes())
    _check_directories(directories)
    return value.hexdigest(),directories


def fingerprint(root: Path) -> str:
    return _observe(root)[0]


def validated_contract(subject: str) -> SciencePolicyContract:
    """Reuse validation only while fresh Science bytes, modes and validator match."""
    global _cached
    from analysis import science_artifacts as artifacts
    root=Path(os.path.abspath(artifacts._SCIENCE_DIR))
    observed,directories=_observe(root)
    validator=artifacts.load_policy_contract
    key=(str(root),subject,observed,validator)
    with _lock:
        _check_directories(directories)
        if _cached and _cached[0]==key:
            if isinstance(_cached[1], _ValidationRejection):
                raise ValueError(_cached[1].message)
            return _cached[1]
        try:
            contract=validator(subject,require_active=True)
        except ValueError as exc:
            # Inactive policies are expected denials, not a reason for every
            # concurrent readiness probe to repeat full registry validation.
            contract=_ValidationRejection(str(exc))
        confirmed,confirmed_directories=_observe(root)
        if confirmed!=observed: raise ValueError('Science changed during validation')
        _check_directories(directories)
        _check_directories(confirmed_directories)
        _cached=(key,contract)
        if isinstance(contract, _ValidationRejection):
            raise ValueError(contract.message)
        return contract
