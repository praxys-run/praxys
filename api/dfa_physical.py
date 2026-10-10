"""Linux physical exclusion and retirement. No database or physiological logging.

An actor journal is private to an already authorized execution incarnation.
Recovery never authorizes a launch. The inherited guard remains held after parent
loss; recovery serializes independently and retires before acquiring that guard.
"""
from __future__ import annotations

from contextlib import contextmanager
import ctypes
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from uuid import uuid4

MAX_OUTPUT = 8 * 1024 * 1024
WORKER_ENV = {"PATH", "LANG", "LC_ALL", "TZ"}
PROFILE = {"poll_seconds": .25, "permission_seconds": .75, "term_seconds": .5}


class PhysicalUnavailable(RuntimeError):
    pass


def worker_environment() -> dict[str, str]:
    env = {name: os.environ[name] for name in WORKER_ENV if name in os.environ}
    env.update(OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
    return env


def process_identity(pid: int) -> dict | None:
    try:
        value = Path(f"/proc/{pid}/stat").read_text()
        fields = value[value.rindex(")") + 2:].split()
        return {"pid": pid, "pgid": int(fields[2]), "start": fields[19], "state": fields[0]}
    except FileNotFoundError:
        return None
    except (OSError, ValueError, IndexError) as exc:
        raise PhysicalUnavailable("process_identity_unavailable") from exc


def group_members(pgid: int) -> list[dict]:
    members = []
    for path in Path("/proc").iterdir():
        if path.name.isdigit():
            identity = process_identity(int(path.name))
            if identity and identity["pgid"] == pgid:
                members.append(identity)
    return members


class Lane:
    def __init__(self, directory: Path, incarnation: dict):
        self.directory, self.incarnation = directory, incarnation
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if directory.stat().st_uid != os.getuid() or directory.stat().st_mode & 0o077:
            raise PhysicalUnavailable("runtime_directory_not_private")
        self.journal = directory / "actor.json"
        self.guard = None
        self.supervisor_guard = None
        self.child = None
        # Adopt controlled grandchildren for exit observation after leader exit.
        if ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) != 0:
            raise PhysicalUnavailable("subreaper_unavailable")

    def authorize_recovery(self):
        """Called only after durable host validation; never grants launch authority."""
        path=self.directory/'recovery-authority.json'
        temporary=self.directory/('recovery-'+uuid4().hex+'.tmp')
        fd=os.open(temporary,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'w') as stream:
            json.dump({'incarnation':self.incarnation,'purpose':'retirement-only'},stream)
            stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
        fd=os.open(self.directory,os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)

    def has_recovery_authority(self):
        path=self.directory/'recovery-authority.json'
        if not path.exists():return False
        if path.is_symlink() or path.stat().st_uid!=os.getuid() or path.stat().st_mode & 0o077 or path.stat().st_size>16384:
            raise PhysicalUnavailable('recovery_authority_invalid')
        value=json.loads(path.read_text())
        return value=={'incarnation':self.incarnation,'purpose':'retirement-only'}

    @contextmanager
    def recovery_mutex(self):
        fd = os.open(self.directory / "recovery.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        except BlockingIOError as exc:
            raise PhysicalUnavailable("recovery_busy") from exc
        finally:
            os.close(fd)

    def record(self, value: dict):
        temporary = self.directory / f"actor-{uuid4().hex}.tmp"
        fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump(value, stream, sort_keys=True, separators=(",", ":"))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.journal)
            parent = os.open(self.directory, os.O_DIRECTORY)
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
        finally:
            temporary.unlink(missing_ok=True)

    def actor(self):
        if not self.journal.exists():
            return None
        if self.journal.stat().st_size > 16_384:
            raise PhysicalUnavailable("actor_journal_invalid")
        value = json.loads(self.journal.read_text())
        if value.get("incarnation") != self.incarnation:
            raise PhysicalUnavailable("incarnation_changed")
        return value

    def acquire_supervisor(self):
        if self.supervisor_guard is not None:
            return
        fd = os.open(self.directory / "supervisor.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            os.close(fd)
            raise PhysicalUnavailable("supervisor_lane_occupied") from exc
        self.supervisor_guard = fd

    def acquire(self):
        if self.guard is not None:
            return
        fd = os.open(self.directory / "physical.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            os.close(fd)
            raise PhysicalUnavailable("physical_guard_occupied") from exc
        self.guard = fd

    def recover(self, authorized: bool):
        if not authorized:
            raise PhysicalUnavailable("recovery_not_authorized")
        self.acquire_supervisor()
        with self.recovery_mutex():
            value = self.actor()
            if value and value["state"] != "idle":
                if value["state"] == "launching" or not value.get("identity"):
                    raise PhysicalUnavailable("unacknowledged_launch")
                self.retire(value)
            # The old inherited lock is acquired only AFTER verified retirement.
            self.acquire()

    def launch(self, binding: dict, *, authorized: bool):
        if not authorized:
            raise PhysicalUnavailable("launch_not_authorized")
        self.acquire_supervisor()
        self.acquire()
        previous = self.actor()
        if previous and previous["state"] != "idle":
            raise PhysicalUnavailable("actor_not_retired")
        value = {"incarnation": self.incarnation, "state": "launching", "actor_token": str(uuid4()),
                 "binding": binding, "identity": None, "launch_at": time.monotonic()}
        self.record(value)
        try:
            self.child = subprocess.Popen([sys.executable, "-E", "-B", "-m", "api.dfa_worker"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                close_fds=True, pass_fds=(self.guard,), start_new_session=True,
                cwd=Path(__file__).resolve().parents[1], env=worker_environment())
            identity = process_identity(self.child.pid)
            if identity is None or identity["pgid"] != self.child.pid:
                raise PhysicalUnavailable("launch_identity_unknown")
            value.update(state="occupied", identity=identity, process_start_observed_at=time.monotonic())
            self.record(value)
            return value, self.child
        except Exception:
            # A spawn without acknowledged identity is ambiguous. Never clear it.
            raise PhysicalUnavailable("launch_requires_recovery")

    def retire(self, value: dict | None = None, *, deadline: float = 3.5):
        value = value or self.actor()
        if value is None or value["state"] == "idle":
            return
        if value.get("incarnation") != self.incarnation or not value.get("identity"):
            raise PhysicalUnavailable("actor_identity_unknown")
        expected = value["identity"]
        leader = process_identity(expected["pid"])
        if leader and (leader["start"] != expected["start"] or leader["pgid"] != expected["pgid"]):
            raise PhysicalUnavailable("actor_identity_reused")
        members = group_members(expected["pgid"])
        # Workers do not spawn. An unexpected descendant is retained as an
        # unresolved actor, rather than signalling a possibly unrelated group.
        if any(member["pid"] != expected["pid"] for member in members):
            value["state"] = "recovery_required"
            self.record(value)
            raise PhysicalUnavailable("unexpected_group_members")
        value.update(state="retiring", term_at=time.monotonic())
        self.record(value)
        if members:
            os.killpg(expected["pgid"], signal.SIGTERM)
        grace, end = time.monotonic() + PROFILE["term_seconds"], time.monotonic() + deadline
        while group_members(expected["pgid"]):
            if self.child is not None:
                self.child.poll()
            else:
                try:
                    os.waitpid(expected["pid"], os.WNOHANG)
                except ChildProcessError:
                    pass
            remaining = group_members(expected["pgid"])
            if not remaining:
                break
            if time.monotonic() >= grace:
                os.killpg(expected["pgid"], signal.SIGKILL)
            if time.monotonic() >= end:
                value["state"] = "recovery_required"
                self.record(value)
                raise PhysicalUnavailable("group_exit_unproved")
            time.sleep(.01)
        value.update(state="idle", exit_observed_at=time.monotonic())
        self.record(value)
        self.child = None

    def close(self):
        if self.supervisor_guard is not None:
            os.close(self.supervisor_guard)
            self.supervisor_guard = None
        if self.guard is not None:
            os.close(self.guard)
            self.guard = None
