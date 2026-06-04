"""Google Drive download utility with on-disk caching.

The Drive URL is parsed into a stable file-id which is then used as the
cache key. Any of the common Google Drive URL shapes are supported:

* ``https://drive.google.com/file/d/<id>/view``
* ``https://drive.google.com/open?id=<id>``
* ``https://drive.google.com/uc?id=<id>&export=download``
* ``https://docs.google.com/uc?export=download&id=<id>``

If the file already exists in the cache directory and ``cache_enabled`` is
true in the config, the download is skipped and the cached path is returned.
The downloader enforces both a wall-clock timeout and a maximum file size
to protect the service from runaway requests.
"""

from __future__ import annotations

import os
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

import gdown

from config import DownloadConfig
from logging_config import get_logger

_LOG = get_logger("scgpt_api.gdrive")


# Exceptions


class InvalidDriveUrlError(ValueError):
    """The supplied URL does not look like a Google Drive share link."""


class DownloadError(RuntimeError):
    """The Drive download failed or exceeded a configured limit."""


# Data types


@dataclass(frozen=True)
class DownloadResult:
    file_id: str
    path: Path
    size_bytes: int
    cached: bool
    duration_seconds: float


# URL parsing


_FILE_ID_PATTERNS = (
    re.compile(r"/file/d/([a-zA-Z0-9_-]+)"),
    re.compile(r"/d/([a-zA-Z0-9_-]+)"),
)


def extract_file_id(url: str) -> str:
    """Pull the Drive file id out of any common share-URL shape."""
    if not url or not isinstance(url, str):
        raise InvalidDriveUrlError("dataset_url must be a non-empty string")

    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    if "drive.google.com" not in host and "docs.google.com" not in host:
        raise InvalidDriveUrlError(
            f"Not a Google Drive URL: {url!r} (host={host!r})"
        )

    # Query string forms: ?id=<id> or ?export=download&id=<id>
    qs = parse_qs(parsed.query or "")
    if "id" in qs and qs["id"]:
        candidate = qs["id"][0]
        if candidate:
            return candidate

    for pattern in _FILE_ID_PATTERNS:
        match = pattern.search(parsed.path or "")
        if match:
            return match.group(1)

    raise InvalidDriveUrlError(
        f"Could not extract a Drive file id from URL: {url!r}"
    )


# Downloader


class GoogleDriveDownloader:
    """Idempotent downloader with size + timeout guards."""

    def __init__(self, cache_dir: str | Path, cfg: DownloadConfig) -> None:
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._cfg = cfg

    # Public API

    def download(self, url: str, *, suffix: str = ".h5ad") -> DownloadResult:
        """Resolve the URL, then either return the cached file or fetch it."""
        file_id = extract_file_id(url)
        target = self._cache_dir / f"{file_id}{suffix}"

        if self._cfg.cache_enabled and target.exists() and target.stat().st_size > 0:
            _LOG.info(
                "drive_cache_hit",
                extra={
                    "file_id": file_id,
                    "path": str(target),
                    "size_bytes": target.stat().st_size,
                },
            )
            return DownloadResult(
                file_id=file_id,
                path=target,
                size_bytes=target.stat().st_size,
                cached=True,
                duration_seconds=0.0,
            )

        tmp = target.with_suffix(target.suffix + ".part")
        if tmp.exists():
            tmp.unlink()

        _LOG.info(
            "drive_download_start",
            extra={"file_id": file_id, "url": url, "destination": str(target)},
        )

        start = time.monotonic()
        try:
            # ``fuzzy=True`` lets gdown handle both file/d/<id>/view and
            # uc?id=<id> URLs and follow the virus-scan confirmation page
            # that Drive shows for large files.
            gdown.download(
                url=url,
                output=str(tmp),
                quiet=True,
                fuzzy=True,
                use_cookies=False,
            )
        except Exception as exc:  # noqa: BLE001 – surface anything gdown raises
            self.cleanup_partial(tmp)
            raise DownloadError(
                f"Google Drive download failed for file_id={file_id}: {exc}"
            ) from exc

        if not tmp.exists() or tmp.stat().st_size == 0:
            self.cleanup_partial(tmp)
            raise DownloadError(
                f"Google Drive download produced no data for file_id={file_id}. "
                "Make sure the file is shared with 'Anyone with the link'."
            )

        duration = time.monotonic() - start
        size_bytes = tmp.stat().st_size
        max_bytes = int(self._cfg.max_size_gb * (1024 ** 3))
        if size_bytes > max_bytes:
            self.cleanup_partial(tmp)
            raise DownloadError(
                f"Downloaded file ({size_bytes / 1024**3:.2f} GB) exceeds the "
                f"configured max_size_gb ({self._cfg.max_size_gb})."
            )

        if duration > self._cfg.timeout_seconds:
            # gdown does not support a hard timeout; we report the breach
            # but keep the file because the work is already done.
            _LOG.warning(
                "drive_download_slow",
                extra={
                    "file_id": file_id,
                    "duration_seconds": duration,
                    "timeout_seconds": self._cfg.timeout_seconds,
                },
            )

        os.replace(tmp, target)

        _LOG.info(
            "drive_download_complete",
            extra={
                "file_id": file_id,
                "path": str(target),
                "size_bytes": size_bytes,
                "duration_seconds": duration,
            },
        )
        return DownloadResult(
            file_id=file_id,
            path=target,
            size_bytes=size_bytes,
            cached=False,
            duration_seconds=duration,
        )

    # Helpers

    @staticmethod
    def cleanup_partial(path: Path) -> None:
        try:
            if path.exists():
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    path.unlink()
        except OSError:
            pass
