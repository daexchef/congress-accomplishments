"""Shared HTTP helpers with retries and a polite User-Agent."""

from __future__ import annotations

import time
from pathlib import Path

import requests

from .config import MAX_RETRIES, REQUEST_TIMEOUT, RETRY_BACKOFF, USER_AGENT


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})
    return s


def download_file(url: str, dest: Path, *, force: bool = False) -> Path:
    """Stream a file to disk. Skip if dest already exists unless force=True."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0 and not force:
        return dest

    tmp = dest.with_suffix(dest.suffix + ".part")
    s = session()
    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with s.get(url, stream=True, timeout=REQUEST_TIMEOUT) as resp:
                resp.raise_for_status()
                with tmp.open("wb") as fh:
                    for chunk in resp.iter_content(chunk_size=1024 * 256):
                        if chunk:
                            fh.write(chunk)
            tmp.replace(dest)
            return dest
        except Exception as exc:  # noqa: BLE001 — retry network/HTTP failures
            last_err = exc
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            wait = RETRY_BACKOFF**attempt
            print(f"  retry {attempt}/{MAX_RETRIES} after {exc} (sleep {wait:.1f}s)")
            time.sleep(wait)
    raise RuntimeError(f"Failed to download {url}") from last_err


def get_json(url: str) -> object:
    s = session()
    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = s.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(RETRY_BACKOFF**attempt)
    raise RuntimeError(f"Failed to GET JSON {url}") from last_err
