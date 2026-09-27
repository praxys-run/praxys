"""Bounded ORIGINAL transport; provider error bodies are never read or logged.

The pinned garminconnect 0.3.x request wrapper reads error JSON/text before
returning. Use its authenticated session/header/refresh primitives directly,
with the same proactive refresh and single 401 retry, so every response is
closed under our byte/status controls. Revalidate this adapter on client bumps.
"""
import time

from garminconnect import Garmin
from garminconnect.exceptions import (
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectNotFoundError,
)

from sync.garmin_fit import FitArchiveError, MAX_ORIGINAL_BYTES


class GarminOriginalClient(Garmin):
    def download(self, path: str, **kwargs) -> bytes:
        """Read the ORIGINAL endpoint with bounded success and zero error bodies."""
        prefix = self.garmin_connect_fit_download.rstrip("/") + "/"
        identifier = path.removeprefix(prefix)
        if not path.startswith(prefix) or not identifier.isascii() or not identifier.isdecimal() or int(identifier) <= 0 or kwargs:
            raise FitArchiveError("invalid_original_path")
        client = self.client
        started = time.monotonic()
        with client._token_lock:
            if client.is_authenticated and client._token_expires_soon():
                client._refresh_session()
        url = f"{client._connectapi}/{path.lstrip('/')}"
        for attempt in range(2):
            headers = client.get_api_headers()
            headers["Accept"] = "*/*"
            response = client._api_session.request("GET", url, headers=headers,
                stream=True, timeout=(15, 60), allow_redirects=False)
            retry_authentication = False
            try:
                status = response.status_code
                if status == 401 and attempt == 0:
                    retry_authentication = True
                elif status == 401:
                    raise GarminConnectAuthenticationError("HTTP 401")
                elif status in (404, 410):
                    raise GarminConnectNotFoundError(f"HTTP {status}")
                elif status < 200 or status >= 300:
                    # Neither JSON, text, content nor iteration touches an error body.
                    raise GarminConnectConnectionError(f"HTTP {status}")
                elif status == 204:
                    return b""
                else:
                    length = response.headers.get("Content-Length")
                    if length:
                        try:
                            advertised_bytes = int(length)
                        except (TypeError, ValueError) as exc:
                            raise FitArchiveError("invalid_content_length") from exc
                        if advertised_bytes < 0 or advertised_bytes > MAX_ORIGINAL_BYTES:
                            raise FitArchiveError("original_too_large")
                    result = bytearray()
                    for chunk in response.iter_content(chunk_size=64 * 1024):
                        if time.monotonic() - started > 120:
                            raise FitArchiveError("download_time_limit")
                        if len(result) + len(chunk) > MAX_ORIGINAL_BYTES:
                            raise FitArchiveError("original_too_large")
                        result.extend(chunk)
                    return bytes(result)
            finally:
                response.close()
            if retry_authentication:
                # Close the rejected response before refreshing credentials.
                with client._token_lock:
                    client._refresh_session()
        raise GarminConnectAuthenticationError("HTTP 401")
