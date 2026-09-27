from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import time
from urllib.parse import ParseResult, urlparse, urlunparse

import httpx


CURL_MAX_ATTEMPTS = 6
CURL_RETRY_DELAY_SECONDS = 2
LIZHI_RSS_CDN_HOST = "cdn.lizhi.fm"
LIZHI_DOWNLOAD_CDN_HOST = "cdn5.lizhi.fm"


def build_download_record(audio_url: str, destination: str | Path) -> dict[str, str | int]:
    return {
        "audio_url": audio_url,
        "destination": str(destination),
        "status": "queued",
        "bytes_downloaded": 0,
        "bytes_total": 0,
    }


def guess_audio_filename(audio_url: str, fallback_stem: str) -> str:
    parsed = urlparse(audio_url)
    name = Path(parsed.path).name
    if name:
        return name
    return f"{fallback_stem}.bin"


def _download_with_httpx(
    audio_url: str,
    destination: str | Path,
    progress_callback=None,
    chunk_size: int = 1024 * 256,
) -> Path:
    path = Path(destination)
    downloaded = 0
    total = 0
    with httpx.stream("GET", audio_url, follow_redirects=True, timeout=None) as response:
        response.raise_for_status()
        total_header = response.headers.get("content-length")
        total = int(total_header) if total_header and total_header.isdigit() else 0
        if progress_callback:
            progress_callback(downloaded, total)
        with path.open("wb") as file_obj:
            for chunk in response.iter_bytes(chunk_size=chunk_size):
                if not chunk:
                    continue
                file_obj.write(chunk)
                downloaded += len(chunk)
                if progress_callback:
                    progress_callback(downloaded, total)
    return path


def _probe_content_length_with_curl(audio_url: str) -> int:
    curl_path = shutil.which("curl")
    if not curl_path:
        return 0

    result = subprocess.run(
        [
            curl_path,
            "--head",
            "--location",
            "--silent",
            "--show-error",
            "--user-agent",
            "Mozilla/5.0",
            audio_url,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return 0

    total = 0
    for line in result.stdout.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key.strip().lower() != "content-length":
            continue
        value = value.strip()
        if value.isdigit():
            total = int(value)
    return total


def _partial_download_path(destination: Path) -> Path:
    return Path(f"{destination}.part")


def _download_with_curl_once(
    command: list[str],
    observed_path: Path,
    total: int,
    progress_callback=None,
) -> None:
    process = subprocess.Popen(command)
    last_reported = -1

    while True:
        current = observed_path.stat().st_size if observed_path.exists() else 0
        if progress_callback and current != last_reported:
            try:
                progress_callback(current, total)
            except Exception:
                process.terminate()
                process.wait(timeout=5)
                raise
            last_reported = current

        return_code = process.poll()
        if return_code is not None:
            if return_code != 0:
                raise subprocess.CalledProcessError(return_code, command)
            break
        time.sleep(0.25)


def _download_with_curl(audio_url: str, destination: str | Path, progress_callback=None) -> Path:
    path = Path(destination)
    partial_path = _partial_download_path(path)
    curl_path = shutil.which("curl")
    if not curl_path:
        raise RuntimeError("curl is not available")

    if path.exists():
        path.unlink()

    total = _probe_content_length_with_curl(audio_url)
    command = [
        curl_path,
        "--location",
        "--fail",
        "--silent",
        "--show-error",
        "--continue-at",
        "-",
        "--user-agent",
        "Mozilla/5.0",
        "--output",
        str(partial_path),
        audio_url,
    ]

    if total and partial_path.exists() and partial_path.stat().st_size >= total:
        partial_path.replace(path)
        if progress_callback:
            progress_callback(total, total)
        return path

    last_error: subprocess.CalledProcessError | None = None
    for attempt in range(CURL_MAX_ATTEMPTS):
        try:
            _download_with_curl_once(command, partial_path, total, progress_callback=progress_callback)
            break
        except subprocess.CalledProcessError as exc:
            last_error = exc
            if attempt + 1 >= CURL_MAX_ATTEMPTS:
                raise
            time.sleep(CURL_RETRY_DELAY_SECONDS)

    if last_error is not None and not partial_path.exists():
        raise last_error

    partial_path.replace(path)
    final_size = path.stat().st_size if path.exists() else 0
    if progress_callback:
        progress_callback(final_size, total or final_size)
    return path


def download_audio(
    audio_url: str,
    destination: str | Path,
    progress_callback=None,
    chunk_size: int = 1024 * 256,
) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    downloader = _download_with_curl if shutil.which("curl") else _download_with_httpx
    last_error: subprocess.CalledProcessError | httpx.HTTPError | None = None
    for candidate_url in _download_url_candidates(audio_url):
        try:
            if downloader is _download_with_curl:
                return downloader(candidate_url, path, progress_callback=progress_callback)
            return downloader(candidate_url, path, progress_callback=progress_callback, chunk_size=chunk_size)
        except (subprocess.CalledProcessError, httpx.HTTPError) as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise RuntimeError("No audio URL candidates available")


def _download_url_candidates(audio_url: str) -> list[str]:
    parsed = urlparse(audio_url)
    if parsed.scheme in {"http", "https"} and parsed.netloc == LIZHI_RSS_CDN_HOST:
        return _lizhi_download_url_candidates(parsed)
    return [audio_url]


def _lizhi_download_url_candidates(parsed: ParseResult) -> list[str]:
    return _unique_urls(
        [
            urlunparse(parsed),
            urlunparse(parsed._replace(netloc=LIZHI_DOWNLOAD_CDN_HOST)),
            urlunparse(parsed._replace(scheme="http", netloc=LIZHI_DOWNLOAD_CDN_HOST)),
            urlunparse(parsed._replace(scheme="http")),
        ]
    )


def _unique_urls(urls: list[str]) -> list[str]:
    candidates = []
    seen = set()
    for url in urls:
        if url in seen:
            continue
        candidates.append(url)
        seen.add(url)
    return candidates
