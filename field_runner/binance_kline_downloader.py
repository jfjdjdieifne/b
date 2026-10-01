"""Official Binance public-data klines downloader (data.binance.vision ONLY).

Downloads one monthly Spot klines artifact (ZIP + official .CHECKSUM), verifies
the official checksum BEFORE any use, then extracts the CSV locally. This is a
pure input-acquisition tool: no market data is ever written into MANIFEST, and
no downloaded value is interpreted here.

If the network is unavailable the downloader raises ``LocalFileRequired`` with
the exact expected artifact name so the owner can supply a local file path
instead of facing a vague failure.
"""

from __future__ import annotations

import hashlib
import os
import urllib.error
import urllib.request
import zipfile

BASE_URL = "https://data.binance.vision/data/spot/monthly/klines"
CONTRACT = "BINANCE_SPOT_PUBLIC_DATA_KLINES_MONTHLY_1M_ZIP"


class DownloaderError(Exception):
    """Input acquisition failed before any data was used."""


class ChecksumMismatch(DownloaderError):
    """Official .CHECKSUM does not match the downloaded artifact."""


class LocalFileRequired(DownloaderError):
    """Network unavailable: the owner must supply a local artifact path."""

    def __init__(self, message: str, *, expected_names: tuple) -> None:
        super().__init__(message)
        self.expected_names = expected_names


def artifact_names(symbol: str, year_month: str) -> tuple:
    stem = f"{symbol}-1m-{year_month}"
    return (f"{stem}.zip", f"{stem}.zip.CHECKSUM", f"{stem}.csv")


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_checksum_file(text: str) -> str:
    """Parse the official .CHECKSUM text (``<sha256>  <name>``)."""
    tokens = text.strip().split()
    if not tokens:
        raise ChecksumMismatch("CHECKSUM_FILE_EMPTY")
    candidate = tokens[0].strip().lower()
    if len(candidate) != 64 or any(c not in "0123456789abcdef" for c in candidate):
        raise ChecksumMismatch("CHECKSUM_FILE_FORMAT_INVALID")
    return candidate


def verify_zip_checksum(zip_path: str, checksum_path: str) -> str:
    """Fail-closed official checksum verification; returns verified sha256."""
    expected = parse_checksum_file(open(checksum_path, "r", encoding="utf-8").read())
    actual = _sha256_file(zip_path)
    if actual != expected:
        raise ChecksumMismatch(
            f"OFFICIAL_CHECKSUM_MISMATCH expected={expected} actual={actual} file={zip_path}"
        )
    return actual


def _download(url: str, dest: str, timeout: float, deadline: float | None = None) -> None:
    import time as _t

    request = urllib.request.Request(url, headers={"User-Agent": "btc-may2026-field-runner/1"})
    with urllib.request.urlopen(request, timeout=timeout) as response, open(dest, "wb") as out:
        total = 0
        while True:
            if deadline is not None and _t.time() > deadline:
                raise TimeoutError("DOWNLOAD_TOO_SLOW_FOR_DEADLINE")
            chunk = response.read(1 << 20)
            if not chunk:
                break
            total += len(chunk)
            out.write(chunk)
        return total


def extract_klines_csv(zip_path: str, dest_dir: str) -> str:
    """Extract the single klines CSV from a verified monthly ZIP."""
    os.makedirs(dest_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        names = [n for n in archive.namelist() if n.lower().endswith(".csv")]
        if len(names) != 1:
            raise DownloaderError(f"ZIP_CSV_ENTRY_COUNT_INVALID:{len(names)}")
        member = names[0]
        target = os.path.join(dest_dir, os.path.basename(member))
        with archive.open(member) as src, open(target, "wb") as out:
            while True:
                chunk = src.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
    return target


def ensure_monthly_klines(
    *,
    symbol: str,
    year_month: str,
    download_dir: str,
    timeout: float = 120.0,
    download_deadline_seconds: float = 600.0,
) -> dict:
    """Acquire the official monthly 1m klines artifact (download or local cache).

    Returns a dict: zip_path, checksum_path, csv_path, zip_sha256 (verified).
    Raises LocalFileRequired with exact names when the network is unavailable
    OR the download is too slow (deadline), so the owner can supply a local
    file instead of waiting indefinitely.
    """
    import time as _t

    if not symbol or not year_month or len(year_month) != 7 or year_month[4] != "-":
        raise DownloaderError("SYMBOL_OR_PERIOD_INVALID")
    zip_name, checksum_name, csv_name = artifact_names(symbol, year_month)
    os.makedirs(download_dir, exist_ok=True)
    zip_path = os.path.join(download_dir, zip_name)
    checksum_path = os.path.join(download_dir, checksum_name)
    csv_path = os.path.join(download_dir, csv_name)
    stem_url = f"{BASE_URL}/{symbol}/1m/{zip_name}"

    have_zip = os.path.isfile(zip_path)
    have_checksum = os.path.isfile(checksum_path)
    if not (have_zip and have_checksum):
        deadline = _t.time() + float(download_deadline_seconds)
        for url, dest in ((stem_url, zip_path), (stem_url + ".CHECKSUM", checksum_path)):
            try:
                print(f"  downloading official artifact: {url}", flush=True)
                t0 = _t.time()
                _download(url, dest, timeout, deadline=deadline)
                size = os.path.getsize(dest)
                print(f"  downloaded {os.path.basename(dest)}: {size} bytes in {_t.time()-t0:.1f}s", flush=True)
            except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError) as exc:
                raise LocalFileRequired(
                    "NETWORK_UNAVAILABLE_OR_DOWNLOAD_TOO_SLOW: provide the official artifact "
                    f"locally via --klines-zip/--klines-checksum (expected names: {zip_name}, "
                    f"{checksum_name}) or a plain headerless CSV via --klines-csv ({csv_name}). "
                    f"last_error={type(exc).__name__}",
                    expected_names=(zip_name, checksum_name, csv_name),
                ) from exc

    verified_sha = verify_zip_checksum(zip_path, checksum_path)
    if not os.path.isfile(csv_path):
        csv_path = extract_klines_csv(zip_path, download_dir)
    return {
        "contract": CONTRACT,
        "symbol": symbol,
        "year_month": year_month,
        "zip_path": zip_path,
        "checksum_path": checksum_path,
        "csv_path": csv_path,
        "zip_sha256": verified_sha,
        "source_url": stem_url,
    }
