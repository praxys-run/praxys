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

Nothing here raises to the caller: a storage outage must not turn a feedback
submit into a 500. :func:`store_image` returns ``None`` on failure (the text
report is still captured); :func:`load_image` returns ``None`` when the key is
missing or unreadable. All validation helpers are pure and unit-tested.
"""
from __future__ import annotations

import base64
import binascii
import logging
import os
import re
from functools import lru_cache

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
_KEY_RE = re.compile(r"^feedback/\d+/\d+\.(png|jpg|jpeg|webp)$")


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
            "feedback screenshots use the LOCAL filesystem backend (%s). On "
            "ephemeral hosts (Azure App Service) set PRAXYS_FEEDBACK_BLOB_* for "
            "durable, restart-safe storage.",
            _local_dir(),
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
            "azure-storage-blob not installed — feedback screenshots fall back "
            "to local filesystem storage"
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
        logger.warning("Azure Blob init failed — falling back to local storage", exc_info=True)
        return None


def is_blob_configured() -> bool:
    """True iff the Azure Blob backend is active (for docs / health checks)."""
    return _use_blob() and _blob_container_client() is not None


# ---------------------------------------------------------------------------
# Store / load
# ---------------------------------------------------------------------------


def store_image(data: bytes, *, feedback_id: int, index: int) -> str | None:
    """Persist one screenshot and return its storage key, or ``None`` on failure.

    The key is ``feedback/<feedback_id>/<index>.<ext>`` where ext derives from
    the sniffed content-type. The caller is expected to have validated ``data``
    already; we re-sniff so a bad ext can never be written.
    """
    content_type = sniff(data)
    ext = CONTENT_TYPE_TO_EXT.get(content_type or "")
    if not ext:
        logger.warning("store_image: refusing to store non-image bytes")
        return None
    key = f"feedback/{feedback_id}/{index}.{ext}"

    if _use_blob():
        client = _blob_container_client()
        if client is not None:
            try:
                client.upload_blob(
                    name=key,
                    data=data,
                    overwrite=True,
                    content_settings=_blob_content_settings(content_type),
                )
                return key
            except Exception:
                logger.warning("store_image: blob upload failed for %s", key, exc_info=True)
                return None
        # blob configured but client unavailable → fall through to local

    _warn_local_once()
    try:
        path = os.path.join(_local_dir(), *key.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)
        return key
    except OSError:
        logger.warning("store_image: local write failed for %s", key, exc_info=True)
        return None


def load_image(key: str) -> tuple[bytes, str] | None:
    """Return ``(bytes, content_type)`` for a stored key, or ``None`` if absent.

    The key is validated against the server-generated shape so a tampered value
    can never traverse outside the container/dir.
    """
    if not key or not _KEY_RE.match(key):
        return None
    ext = key.rsplit(".", 1)[-1]
    content_type = EXT_TO_CONTENT_TYPE.get(ext, "application/octet-stream")

    if _use_blob():
        client = _blob_container_client()
        if client is not None:
            try:
                data = client.download_blob(key).readall()
                return data, content_type
            except Exception:
                logger.info("load_image: blob %s not found or unreadable", key)
                # fall through to local in case it predates blob config

    try:
        path = os.path.join(_local_dir(), *key.split("/"))
        with open(path, "rb") as fh:
            return fh.read(), content_type
    except OSError:
        return None


def _blob_content_settings(content_type: str | None):
    """Best-effort ContentSettings for a blob upload (None when SDK absent)."""
    try:
        from azure.storage.blob import ContentSettings  # type: ignore[import-not-found]
    except ImportError:
        return None
    return ContentSettings(content_type=content_type or "application/octet-stream")