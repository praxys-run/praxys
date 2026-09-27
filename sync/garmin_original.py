"""Garmin ORIGINAL download with bounded streamed consumption."""
import time

from garminconnect import Garmin

from sync.garmin_fit import FitArchiveError, MAX_ORIGINAL_BYTES


class GarminOriginalClient(Garmin):
    def download(self, path, **kwargs):
        """Keep download_activity(ORIGINAL) URL validation and authenticated transport."""
        started = time.monotonic()
        response = self.client.request("GET", "connectapi", path, stream=True,
            timeout=(15, 60), headers={"Accept": "*/*"}, **kwargs)
        try:
            length = response.headers.get("Content-Length")
            if length and int(length) > MAX_ORIGINAL_BYTES:
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
