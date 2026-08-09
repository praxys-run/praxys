#!/usr/bin/env python3
"""Launch isolated local or production-test Praxys MCP profiles."""
from __future__ import annotations

import argparse
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
from typing import NoReturn


LOCAL_USER_ID = "migrated-user-00000001"
LOCAL_USER_EMAIL = "local@praxys.dev"
_BOOTSTRAP_OWNER = "praxys-local-mcp"
_BOOTSTRAP_VERSION = 1
_MARKER_NAME = ".praxys-mcp-sandbox.json"
_LOCK_NAME = ".praxys-mcp-bootstrap.lock"
_KEY_NAME = ".encryption-key"
_PROFILE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_SOURCE_DIRS = ("garmin", "stryd", "oura", "ai")


@dataclass(frozen=True)
class BootstrapResult:
    """Result of preparing the deterministic local MCP sandbox."""

    data_dir: Path
    reset: bool
    fingerprint: str


def project_root() -> Path:
    """Return the checked-out Praxys repository root."""
    return Path(__file__).resolve().parents[1]


def _venv_python(root: Path) -> Path:
    return root / ".venv" / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python"
    )


def _runtime_python(root: Path) -> Path:
    configured = os.environ.get("PRAXYS_MCP_PYTHON", "").strip()
    if configured:
        path = Path(os.path.expandvars(configured)).expanduser()
        if not path.is_absolute():
            path = root / path
        return path.resolve()
    if os.environ.get("PRAXYS_MCP_USE_CURRENT_PYTHON") == "1":
        return Path(sys.executable).resolve()
    return _venv_python(root)


def _plugin_server(root: Path) -> Path:
    return root / "plugins" / "praxys" / "mcp-server" / "server.py"


def _require_mcp_runtime(root: Path) -> None:
    if importlib.util.find_spec("mcp") is not None:
        return
    requirements = root / "plugins" / "praxys" / "mcp-server" / (
        "requirements.txt"
    )
    raise SystemExit(
        "The selected Python environment is missing the MCP SDK. "
        f'Install it with: "{_runtime_python(root)}" -m pip install '
        f'-r "{requirements}"'
    )


def _reexec_in_runtime_python(root: Path) -> None:
    python_path = _runtime_python(root)
    if not python_path.is_file():
        raise SystemExit(
            f"Praxys MCP Python not found at {python_path}. "
            "Create .venv and install requirements.txt first, or set "
            "PRAXYS_MCP_PYTHON to an absolute interpreter path."
        )
    if Path(sys.executable).resolve() == python_path.resolve():
        return
    os.chdir(root)
    os.execv(
        str(python_path),
        [
            str(python_path),
            "-m",
            "scripts.run_praxys_mcp",
            *sys.argv[1:],
        ],
    )


def _resolve_local_data_dir(root: Path) -> Path:
    configured = os.environ.get(
        "PRAXYS_LOCAL_MCP_DATA_DIR",
        "",
    ).strip()
    if not configured:
        return (root / ".praxys-local").resolve()
    path = Path(os.path.expandvars(configured)).expanduser()
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _fixture_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    digest.update(f"bootstrap:{_BOOTSTRAP_VERSION}\0".encode())
    fixture_paths = [root / "data" / "config.json"]
    fixture_paths.extend(
        sorted(
            path
            for path in (root / "data" / "sample").rglob("*")
            if path.is_file()
        )
    )
    for path in fixture_paths:
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _read_marker(data_dir: Path) -> dict | None:
    marker_path = data_dir / _MARKER_NAME
    if not marker_path.exists():
        return None
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Local MCP sandbox marker is invalid: {marker_path}"
        ) from exc
    if not isinstance(marker, dict) or marker.get("owner") != _BOOTSTRAP_OWNER:
        raise RuntimeError(
            f"Refusing to use unrecognized local MCP sandbox: {data_dir}"
        )
    return marker


def _write_marker(data_dir: Path, payload: dict) -> None:
    marker_path = data_dir / _MARKER_NAME
    temporary_path = marker_path.with_name(
        f"{marker_path.name}.{os.getpid()}.tmp"
    )
    temporary_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(marker_path)


@contextmanager
def _sandbox_lock(data_dir: Path) -> Iterator[None]:
    lock_path = data_dir / _LOCK_NAME
    handle = lock_path.open("a+b")
    handle.seek(0)
    handle.write(f"pid={os.getpid()}\n".encode("ascii"))
    handle.flush()
    acquired = False
    try:
        if os.name == "nt":
            import msvcrt

            deadline = time.monotonic() + 300
            while True:
                try:
                    handle.seek(0)
                    msvcrt.locking(
                        handle.fileno(),
                        msvcrt.LK_NBLCK,
                        1,
                    )
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise RuntimeError(
                            "Timed out waiting for local MCP bootstrap: "
                            f"{data_dir}"
                        )
                    time.sleep(0.1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        acquired = True
        yield
    finally:
        if acquired and os.name == "nt":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        elif acquired:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _claim_sandbox(data_dir: Path) -> dict:
    data_dir.mkdir(parents=True, exist_ok=True)
    marker = _read_marker(data_dir)
    if marker is not None:
        return marker
    unowned_entries = [
        path
        for path in data_dir.iterdir()
        if path.name != _LOCK_NAME
        and not (
            path.name.startswith(f"{_MARKER_NAME}.")
            and path.name.endswith(".tmp")
        )
    ]
    if unowned_entries:
        raise RuntimeError(
            "Refusing to initialize PRAXYS_LOCAL_MCP_DATA_DIR because it "
            f"is non-empty and not owned by Praxys MCP: {data_dir}"
        )
    marker = {
        "owner": _BOOTSTRAP_OWNER,
        "version": _BOOTSTRAP_VERSION,
        "state": "initializing",
    }
    _write_marker(data_dir, marker)
    return marker


def _local_encryption_key(data_dir: Path) -> str:
    from cryptography.fernet import Fernet

    key_path = data_dir / _KEY_NAME
    if key_path.exists():
        key = key_path.read_text(encoding="utf-8").strip()
        Fernet(key.encode("ascii"))
        return key
    key = Fernet.generate_key().decode("ascii")
    key_path.write_text(key + "\n", encoding="utf-8")
    try:
        key_path.chmod(0o600)
    except OSError:
        pass
    return key


def configure_local_environment(data_dir: Path, encryption_key: str) -> None:
    """Pin local MCP imports to the isolated SQLite sandbox."""
    isolated_values = {
        "DATA_DIR": str(data_dir),
        "PRAXYS_LOCAL": "1",
        "TRAINSIGHT_LOCAL": "0",
        "PRAXYS_ENV": "development",
        "PRAXYS_USER_ID": LOCAL_USER_ID,
        "PRAXYS_PROFILE": "local",
        "PRAXYS_TOKEN_PATH": str(data_dir / ".api-token"),
        "PRAXYS_LOCAL_ENCRYPTION_KEY": encryption_key,
        "PRAXYS_JWT_SECRET": "praxys-local-mcp-development-secret",
        "PRAXYS_SYNC_SCHEDULER": "false",
        "PRAXYS_AUTH_RATE_LIMIT_DISABLED": "true",
        "PRAXYS_GARMIN_PLAN_DELIVERY_ENABLED": "false",
        "PRAXYS_URL": "",
        "TRAINSIGHT_URL": "",
        "PRAXYS_FRONTEND_URL": "",
        "TRAINSIGHT_FRONTEND_URL": "",
        "PRAXYS_DATABASE_URL": "",
        "DATABASE_URL": "",
        "PRAXYS_DB_AUTH": "",
        "KEY_VAULT_URL": "",
        "KEY_VAULT_KEY_NAME": "",
        "PRAXYS_STRYD_ENV_USER_ID": "",
        "STRYD_EMAIL": "",
        "STRYD_PASSWORD": "",
    }
    os.environ.update(isolated_values)


def _assert_isolated_sqlite(data_dir: Path) -> None:
    from sqlalchemy.engine.url import make_url

    from db.session import get_database_url

    url = make_url(get_database_url())
    if url.get_backend_name() != "sqlite":
        raise RuntimeError(
            "Local MCP bootstrap refuses non-SQLite databases"
        )
    database = url.database
    if database is None:
        raise RuntimeError("Local MCP SQLite database path is missing")
    database_path = Path(database).resolve()
    if not database_path.is_relative_to(data_dir.resolve()):
        raise RuntimeError(
            "Local MCP database resolved outside its isolated data directory"
        )


def _dispose_loaded_database() -> None:
    db_session = sys.modules.get("db.session")
    if db_session is not None:
        db_session.dispose_engines()


def _database_is_usable(data_dir: Path) -> bool:
    database_path = data_dir / "trainsight.db"
    if not database_path.is_file():
        return False

    from sqlalchemy.exc import SQLAlchemyError

    from db import session as db_session
    from db.models import Activity, RecoveryData, TrainingPlan, User

    db_session.dispose_engines()
    try:
        db_session.init_db(force=True)
        db = db_session.SessionLocal()
        try:
            user = db.get(User, LOCAL_USER_ID)
            return bool(
                user is not None
                and user.is_active
                and db.query(Activity).filter(
                    Activity.user_id == LOCAL_USER_ID,
                ).count()
                and db.query(RecoveryData).filter(
                    RecoveryData.user_id == LOCAL_USER_ID,
                ).count()
                and db.query(TrainingPlan).filter(
                    TrainingPlan.user_id == LOCAL_USER_ID,
                ).count()
            )
        finally:
            db.close()
    except SQLAlchemyError:
        return False
    finally:
        db_session.dispose_engines()


def _clear_owned_sandbox(data_dir: Path) -> None:
    _dispose_loaded_database()
    for filename in (
        "trainsight.db",
        "trainsight.db-journal",
        "trainsight.db-wal",
        "trainsight.db-shm",
        "config.json",
        ".api-token",
        ".api-token.config.json",
    ):
        path = data_dir / filename
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    for source in _SOURCE_DIRS:
        path = data_dir / source
        if path.exists():
            shutil.rmtree(path)


def _copy_sample_data(root: Path, data_dir: Path) -> None:
    shutil.copy2(root / "data" / "config.json", data_dir / "config.json")
    sample_dir = root / "data" / "sample"
    for source in _SOURCE_DIRS:
        shutil.copytree(
            sample_dir / source,
            data_dir / source,
            dirs_exist_ok=True,
        )


def _migrate_sample_data(data_dir: Path) -> None:
    from scripts.migrate_csv_to_db import migrate

    migrate(
        str(data_dir),
        email=LOCAL_USER_EMAIL,
        password="local-mcp-login-disabled",
    )

    from db import session as db_session
    from db.models import UserConfig

    db = db_session.SessionLocal()
    try:
        config = db.get(UserConfig, LOCAL_USER_ID)
        if config is None:
            raise RuntimeError("Local MCP bootstrap did not create user config")
        config.display_name = "Local MCP Athlete"
        db.commit()
    finally:
        db.close()
        db_session.dispose_engines()


def _ensure_local_sandbox(
    root: Path,
    data_dir: Path,
    *,
    reset: bool = False,
) -> BootstrapResult:
    """Create or verify the repository-owned synthetic local MCP database."""
    marker = _claim_sandbox(data_dir)
    fingerprint = _fixture_fingerprint(root)
    _assert_isolated_sqlite(data_dir)
    should_reset = (
        reset
        or marker.get("state") != "ready"
        or marker.get("version") != _BOOTSTRAP_VERSION
        or marker.get("fingerprint") != fingerprint
        or not _database_is_usable(data_dir)
    )
    if not should_reset:
        return BootstrapResult(
            data_dir=data_dir,
            reset=False,
            fingerprint=fingerprint,
        )

    _write_marker(data_dir, {
        "owner": _BOOTSTRAP_OWNER,
        "version": _BOOTSTRAP_VERSION,
        "state": "initializing",
        "fingerprint": fingerprint,
    })
    _clear_owned_sandbox(data_dir)
    _copy_sample_data(root, data_dir)
    _migrate_sample_data(data_dir)
    if not _database_is_usable(data_dir):
        raise RuntimeError(
            "Local MCP bootstrap completed without usable synthetic data"
        )
    _write_marker(data_dir, {
        "owner": _BOOTSTRAP_OWNER,
        "version": _BOOTSTRAP_VERSION,
        "state": "ready",
        "fingerprint": fingerprint,
        "user_id": LOCAL_USER_ID,
    })
    return BootstrapResult(
        data_dir=data_dir,
        reset=True,
        fingerprint=fingerprint,
    )


def ensure_local_sandbox(
    root: Path,
    data_dir: Path,
    *,
    reset: bool = False,
) -> BootstrapResult:
    """Claim, configure, and prepare the isolated local MCP sandbox."""
    data_dir.mkdir(parents=True, exist_ok=True)
    with _sandbox_lock(data_dir):
        _claim_sandbox(data_dir)
        key = _local_encryption_key(data_dir)
        configure_local_environment(data_dir, key)
        return _ensure_local_sandbox(
            root,
            data_dir,
            reset=reset,
        )


def configure_remote_profile(profile: str) -> None:
    """Configure one isolated production-backed MCP authentication profile."""
    if not _PROFILE_PATTERN.fullmatch(profile):
        raise SystemExit(
            "Profile names must start with a letter or number and contain "
            "only letters, numbers, underscores, or hyphens."
        )
    os.environ.update({
        "PRAXYS_LOCAL": "0",
        "TRAINSIGHT_LOCAL": "0",
        "PRAXYS_PROFILE": profile,
        "PRAXYS_TOKEN_PATH": "",
        "PRAXYS_URL": "https://api.praxys.run",
        "PRAXYS_FRONTEND_URL": "https://www.praxys.run",
    })


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Launch an isolated Praxys MCP profile",
    )
    parser.add_argument(
        "mode",
        nargs="?",
        default="local",
        choices=("local", "remote-profile"),
    )
    parser.add_argument(
        "profile",
        nargs="?",
        help="Named auth profile for remote-profile mode",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset the repository-owned local synthetic sandbox",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Prepare local data and exit without starting the MCP server",
    )
    return parser.parse_args()


def main() -> NoReturn:
    """Replace this bootstrap process with the selected MCP server."""
    root = project_root()
    _reexec_in_runtime_python(root)
    args = _parse_args()
    os.chdir(root)

    if args.mode == "local":
        if args.profile is not None:
            raise SystemExit("local mode does not accept a profile name")
        data_dir = _resolve_local_data_dir(root)
        result = ensure_local_sandbox(
            root,
            data_dir,
            reset=args.reset,
        )
        action = "reset" if result.reset else "reused"
        print(
            f"Praxys local MCP sandbox {action}: {result.data_dir}",
            file=sys.stderr,
        )
        if args.prepare_only:
            raise SystemExit(0)
    else:
        if args.reset or args.prepare_only:
            raise SystemExit(
                "--reset and --prepare-only are only valid in local mode"
            )
        if not args.profile:
            raise SystemExit("remote-profile mode requires a profile name")
        configure_remote_profile(args.profile)

    server_path = _plugin_server(root)
    if not server_path.is_file():
        raise SystemExit(
            "Praxys plugin submodule is missing. Run "
            "'git submodule update --init plugins/praxys'."
        )
    _require_mcp_runtime(root)
    python_path = _runtime_python(root)
    os.execv(str(python_path), [str(python_path), str(server_path)])


if __name__ == "__main__":
    main()
