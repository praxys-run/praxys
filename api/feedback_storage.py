"""Private storage for user-attached feedback screenshots (issue #337).

The main repo is public, and a dashboard screenshot can expose a user's own
health / training data, email, or name. So attachments are stored **privately**
and admin-only: only a storage *key* (reference) lands on the ``Feedback`` row —
never the raw image — and the vision-triage step publishes only a scrubbed
textual description, never the image itself.

Two pluggable backends, chosen from the environment at call time:

- **Azure Blob** (production) — active when a container plus credentials exist::

      PRAXYS_FEEDBACK_BLOB_CONTAINER          container name (required to enable)
      PRAXYS_FEEDBACK_BLOB_CONNECTION_STRING   OR
      PRAXYS_FEEDBACK_BLOB_ACCOUNT_URL         + DefaultAzureCredential (no key)

- **Local filesystem** (dev / self-host default) — under
  ``${DATA_DIR}/feedback_images``. NOTE: on Azure App Service the local disk is
  ephemeral, so production should configure Blob for durable, restart-safe
  storage. A warning is logged once when the local backend is first used.

Tencent COS (CN audience, post-ICP) is a future third backend — the same
key-in / bytes-out seam mirrors the ``frontend_server`` / COS decoupling noted
in CLAUDE.md.

Screenshot submission and reads remain best-effort: :func:`store_image`
returns ``None`` on failure (the text report is still captured), and
:func:`load_image` returns ``None`` when the key is missing or unreadable. The
caller persists the deterministic key before upload so an ambiguous storage
result can never create an image with no deletion locator.
Every locator is bound to a non-secret write-time namespace fingerprint.
Reads and deletion never cross storage backends, and deletion is intentionally
fail-closed so account deletion cannot discard the database locator while a
stored screenshot may remain. A configured Blob backend never writes new
screenshots to local fallback storage.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import logging
import os
import re
from functools import lru_cache
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

# Accepted image types (issue #337: png / jpg / webp). We map each to a
# canonical content-type and file extension. The declared client type is NOT
# trusted — :func:`sniff` reads magic bytes and is authoritative.
CONTENT_TYPE_TO_EXT = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
}
EXT_TO_CONTENT_TYPE = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}

# Per-image decoded-size cap and per-submission count cap (issue #337).
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_IMAGE_COUNT = 3

# A storage key is server-generated as ``feedback/<id>/<index>.<ext>``. Loads
# validate against this shape so a malformed/tampered key can never escape the
# container/dir (path traversal) or read an arbitrary file.
_KEY_RE = re.compile(
    r"^feedback/(?P<feedback_id>\d+)/\d+\.(png|jpg|jpeg|webp)$"
)
_SCOPE_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_PROVENANCE_VERSION = 1


class FeedbackStorageDeletionError(RuntimeError):
    """Raised when an exact screenshot key cannot be safely deleted."""


# ---------------------------------------------------------------------------
# Pure validation helpers (no I/O) — unit-tested
# ---------------------------------------------------------------------------


def sniff(data: bytes) -> str | None:
    """Return the canonical content-type from magic bytes, or ``None``.

    Authoritative over any client-declared type: we store what the bytes
    actually are and reject anything that isn't a supported raster image.
    """
    if len(data) < 12:
        return None
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def decode_base64_image(value: str) -> bytes | None:
    """Decode a base64 image payload, tolerating an optional data-URL prefix.

    Web sends ``FileReader.readAsDataURL`` output (``data:image/png;base64,...``)
    and the mini program sends raw base64 from ``readFile({encoding:'base64'})``;
    both are accepted. Returns ``None`` on any decode error.
    """
    if not value or not isinstance(value, str):
        return None
    payload = value.strip()
    if payload.startswith("data:"):
        comma = payload.find(",")
        if comma == -1:
            return None
        payload = payload[comma + 1:]
    try:
        return base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        return None


def validate_image(data: bytes) -> str | None:
    """Return the canonical content-type if ``data`` is an accepted, in-size
    image, else ``None`` (unsupported type or over the size cap)."""
    if not data or len(data) > MAX_IMAGE_BYTES:
        return None
    return sniff(data)


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------


def _blob_container() -> str | None:
    return os.environ.get("PRAXYS_FEEDBACK_BLOB_CONTAINER") or None


def _blob_connection_string() -> str | None:
    return os.environ.get("PRAXYS_FEEDBACK_BLOB_CONNECTION_STRING") or None


def _blob_account_url() -> str | None:
    return os.environ.get("PRAXYS_FEEDBACK_BLOB_ACCOUNT_URL") or None


def _use_blob() -> bool:
    """True when a container plus at least one credential path is configured."""
    return bool(_blob_container() and (_blob_connection_string() or _blob_account_url()))


def _local_dir() -> str:
    """Base directory for the local filesystem backend (dev / self-host)."""
    from db.session import get_data_dir

    return os.path.join(get_data_dir(), "feedback_images")


_local_warned = False


def _warn_local_once() -> None:
    global _local_warned
    if not _local_warned:
        _local_warned = True
        logger.warning(
            "feedback screenshots use the local filesystem backend; ephemeral "
            "hosts require configured Blob storage for restart-safe durability"
        )


@lru_cache(maxsize=1)
def _blob_container_client():
    """Return an Azure ``ContainerClient`` or ``None`` when unavailable.

    Prefers a connection string; otherwise uses the account URL with
    ``DefaultAzureCredential`` (same keyless auth as :mod:`api.llm`). Ensures the
    container exists. Memoised at process scope; tests clear the cache.
    """
    try:
        from azure.storage.blob import BlobServiceClient  # type: ignore[import-not-found]
    except ImportError:
        logger.warning(
            "azure-storage-blob not installed; configured Blob storage is "
            "unavailable"
        )
        return None
    container = _blob_container()
    if not container:
        return None
    try:
        conn = _blob_connection_string()
        if conn:
            service = BlobServiceClient.from_connection_string(conn)
        else:
            from azure.identity import DefaultAzureCredential  # type: ignore[import-not-found]

            service = BlobServiceClient(
                account_url=_blob_account_url(), credential=DefaultAzureCredential()
            )
        client = service.get_container_client(container)
        try:
            client.create_container()
        except Exception:
            # Already exists (or no create permission) — fine either way.
            pass
        return client
    except Exception:
        logger.warning("Azure Blob initialization failed")
        return None


def is_blob_configured() -> bool:
    """True iff the Azure Blob backend is active (for docs / health checks)."""
    return _use_blob() and _blob_container_client() is not None


def private_blob_enabled() -> bool:
    """Return whether the shared private Blob backend is configured."""
    return _use_blob()


def private_container_client():
    """Return the shared private container client, or ``None`` if unavailable."""
    return _blob_container_client()


def _canonical_account_endpoint(value: str | None) -> str | None:
    """Normalize a non-secret Blob account endpoint for scope comparison."""
    if not value:
        return None
    parsed = urlsplit(value.strip())
    if (
        parsed.scheme.casefold() not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        return None
    hostname = parsed.hostname.casefold()
    try:
        port = parsed.port
    except ValueError:
        return None
    if port is not None:
        hostname = f"{hostname}:{port}"
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme.casefold()}://{hostname}{path}"


def _connection_string_account_endpoint(value: str | None) -> str | None:
    """Extract only account identity from a connection string, never secrets."""
    if not value:
        return None
    fields: dict[str, str] = {}
    for part in value.split(";"):
        key, separator, field_value = part.partition("=")
        if not separator:
            continue
        fields[key.strip().casefold()] = field_value.strip()
    explicit = _canonical_account_endpoint(fields.get("blobendpoint"))
    if explicit is not None:
        return explicit
    account = fields.get("accountname", "").strip().casefold()
    suffix = fields.get("endpointsuffix", "core.windows.net").strip().casefold()
    protocol = fields.get("defaultendpointsprotocol", "https").strip().casefold()
    if (
        not account
        or not account.isascii()
        or not account.isalnum()
        or not suffix
        or any(char.isspace() for char in suffix)
        or protocol not in {"http", "https"}
    ):
        return None
    return _canonical_account_endpoint(
        f"{protocol}://{account}.blob.{suffix}"
    )


def _scope_digest(payload: dict[str, str | int]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def current_storage_provenance() -> dict[str, str | int] | None:
    """Return a non-secret fingerprint of the current screenshot namespace."""
    if _use_blob():
        container = (_blob_container() or "").strip().casefold()
        endpoint = (
            _connection_string_account_endpoint(_blob_connection_string())
            if _blob_connection_string()
            else _canonical_account_endpoint(_blob_account_url())
        )
        if not container or endpoint is None:
            return None
        scope = {
            "version": _PROVENANCE_VERSION,
            "backend": "blob",
            "endpoint": endpoint,
            "container": container,
        }
        return {
            "version": _PROVENANCE_VERSION,
            "backend": "blob",
            "scope_sha256": _scope_digest(scope),
        }
    scope = {
        "version": _PROVENANCE_VERSION,
        "backend": "local",
        "root": os.path.realpath(_local_dir()),
    }
    return {
        "version": _PROVENANCE_VERSION,
        "backend": "local",
        "scope_sha256": _scope_digest(scope),
    }


def _validated_provenance(
    provenance: object,
) -> dict[str, str | int] | None:
    if not isinstance(provenance, dict) or set(provenance) != {
        "version",
        "backend",
        "scope_sha256",
    }:
        return None
    version = provenance.get("version")
    backend = provenance.get("backend")
    digest = provenance.get("scope_sha256")
    if (
        type(version) is not int
        or version != _PROVENANCE_VERSION
        or backend not in {"blob", "local"}
        or not isinstance(digest, str)
        or _SCOPE_DIGEST_RE.fullmatch(digest) is None
    ):
        return None
    return {
        "version": version,
        "backend": str(backend),
        "scope_sha256": digest,
    }


def _provenance_matches_current(
    provenance: object,
) -> dict[str, str | int] | None:
    expected = _validated_provenance(provenance)
    current = current_storage_provenance()
    if expected is None or current is None:
        return None
    if (
        expected["version"] != current["version"]
        or expected["backend"] != current["backend"]
    ):
        return None
    if not hmac.compare_digest(
        str(expected["scope_sha256"]),
        str(current["scope_sha256"]),
    ):
        return None
    return expected


# ---------------------------------------------------------------------------
# Store / load
# ---------------------------------------------------------------------------


def image_storage_key(data: bytes, *, feedback_id: int, index: int) -> str:
    """Return the deterministic row-bound key for one validated image."""
    content_type = sniff(data)
    ext = CONTENT_TYPE_TO_EXT.get(content_type or "")
    if not ext:
        raise ValueError("feedback image bytes are not a supported image")
    return f"feedback/{feedback_id}/{index}.{ext}"


def store_image(
    data: bytes,
    *,
    feedback_id: int,
    index: int,
    provenance: object,
) -> str | None:
    """Persist one screenshot and return its storage key, or ``None`` on failure.

    The key is ``feedback/<feedback_id>/<index>.<ext>`` where ext derives from
    the sniffed content-type. The caller is expected to have validated ``data``
    already; we re-sniff so a bad ext can never be written.
    """
    content_type = sniff(data)
    try:
        key = image_storage_key(
            data,
            feedback_id=feedback_id,
            index=index,
        )
    except ValueError:
        logger.warning("store_image: refusing to store non-image bytes")
        return None

    storage = _provenance_matches_current(provenance)
    if storage is None:
        logger.warning("store_image: storage provenance is unavailable")
        return None

    if storage["backend"] == "blob":
        client = _blob_container_client()
        if client is None:
            logger.warning("store_image: configured Blob storage is unavailable")
            return None
        try:
            client.upload_blob(
                name=key,
                data=data,
                overwrite=True,
                content_settings=_blob_content_settings(content_type),
            )
            return key
        except Exception:
            logger.warning("store_image: Blob upload failed")
            return None

    _warn_local_once()
    try:
        path = os.path.join(_local_dir(), *key.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)
        return key
    except OSError:
        logger.warning("store_image: local write failed")
        return None


def load_image(
    key: str,
    *,
    provenance: object,
) -> tuple[bytes, str] | None:
    """Return ``(bytes, content_type)`` for a stored key, or ``None`` if absent.

    The key is validated against the server-generated shape so a tampered value
    can never traverse outside the container/dir.
    """
    if not key or not _KEY_RE.fullmatch(key):
        return None
    ext = key.rsplit(".", 1)[-1]
    content_type = EXT_TO_CONTENT_TYPE.get(ext, "application/octet-stream")

    storage = _provenance_matches_current(provenance)
    if storage is None:
        return None

    if storage["backend"] == "blob":
        client = _blob_container_client()
        if client is None:
            return None
        try:
            data = client.download_blob(key).readall()
            return data, content_type
        except Exception:
            logger.info("load_image: Blob object not found or unreadable")
            return None

    try:
        path = os.path.join(_local_dir(), *key.split("/"))
        with open(path, "rb") as fh:
            return fh.read(), content_type
    except OSError:
        return None


def _blob_error_code(exc: Exception) -> str | None:
    """Return the normalized Azure Storage error code, when available."""
    code = getattr(exc, "error_code", None)
    value = getattr(code, "value", code)
    return str(value) if value else None


def _delete_local_image(key: str) -> None:
    """Delete one validated key from local storage."""
    root = os.path.realpath(_local_dir())
    parts = key.split("/")
    parent = os.path.realpath(os.path.join(root, *parts[:-1]))
    try:
        contained = os.path.commonpath((root, parent)) == root
    except ValueError:
        contained = False
    if not contained:
        raise FeedbackStorageDeletionError(
            "Feedback image key resolves outside local storage"
        )
    path = os.path.join(parent, parts[-1])
    try:
        os.unlink(path)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise FeedbackStorageDeletionError(
            "Local feedback image deletion failed"
        ) from exc


def delete_image(
    key: str,
    *,
    feedback_id: int,
    provenance: object,
) -> None:
    """Delete one exact row-bound screenshot key from its recorded backend.

    Missing blobs/files are already deleted and therefore succeed. Other
    backend errors are normalized so callers cannot report account deletion
    success while a screenshot may remain. Missing, malformed, or drifted
    provenance is an error; deletion never guesses another backend.
    """
    match = _KEY_RE.fullmatch(key) if isinstance(key, str) else None
    if match is None or int(match.group("feedback_id")) != feedback_id:
        raise FeedbackStorageDeletionError(
            "Feedback image key is invalid or belongs to another row"
        )

    storage = _provenance_matches_current(provenance)
    if storage is None:
        raise FeedbackStorageDeletionError(
            "Feedback image storage provenance is missing or mismatched"
        )

    if storage["backend"] == "blob":
        client = _blob_container_client()
        if client is None:
            raise FeedbackStorageDeletionError(
                "Configured feedback Blob storage is unavailable"
            )
        from azure.core.exceptions import ResourceNotFoundError

        try:
            client.delete_blob(key)
        except ResourceNotFoundError as exc:
            if _blob_error_code(exc) != "BlobNotFound":
                raise FeedbackStorageDeletionError(
                    "Feedback Blob container or resource is unavailable"
                ) from exc
        except Exception as exc:
            raise FeedbackStorageDeletionError(
                "Feedback Blob deletion failed"
            ) from exc
        return

    _delete_local_image(key)


def _blob_content_settings(content_type: str | None):
    """Best-effort ContentSettings for a blob upload (None when SDK absent)."""
    try:
        from azure.storage.blob import ContentSettings  # type: ignore[import-not-found]
    except ImportError:
        return None
    return ContentSettings(content_type=content_type or "application/octet-stream")
