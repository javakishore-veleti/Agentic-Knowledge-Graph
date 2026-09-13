"""The transfer itself: source URI in, bytes on disk out.

Kept out of the DAG so it can be tested without Airflow, and so adding a destination is
one function here rather than another branch inside a task.

Deliberately narrow. Only downloads INTO a local filesystem destination are implemented;
S3 and Blob destinations raise UnsupportedDestination rather than silently reporting
success, because an endpoint marked `available` with nothing behind it is worse than one
that stayed `declared`.
"""

from __future__ import annotations

import ftplib
import logging
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

#: A cap, not a preference. The PubMed baseline is 1,334 files and roughly 20GB; a button
#: in an admin UI must not be one click away from filling the disk. Raise it per-run
#: through the workflow's `max_files` parameter when a full corpus is actually wanted.
DEFAULT_MAX_FILES = 5

#: Refuse a single file larger than this unless the run overrides it.
DEFAULT_MAX_BYTES = 2 * 1024 * 1024 * 1024


class UnsupportedDestination(RuntimeError):
    """Raised when a destination kind has no implementation yet."""


class TransferRefused(RuntimeError):
    """Raised when a transfer is possible but should not proceed."""


@dataclass(slots=True)
class TransferResult:
    bytes: int
    object_count: int
    files: list[str]


def resolve_root(connection_details: dict | None) -> Path:
    """Where this machine keeps the local filesystem endpoint.

    The endpoint declares the NAME of an environment variable, not a path, precisely
    because the answer differs per machine: on a laptop it is under the user's home, and
    inside the Airflow container it is wherever the host directory is mounted. Reading
    the name from config and the value from the environment is what lets one catalog row
    describe both.
    """
    details = connection_details or {}
    env_names = details.get("env") or {}
    var = env_names.get("root")
    if var and os.environ.get(var):
        return Path(os.path.expanduser(os.environ[var])).resolve()

    default = (details.get("defaults") or {}).get("root") or details.get("root")
    if default:
        return Path(os.path.expanduser(default)).resolve()

    raise TransferRefused(
        "the destination endpoint declares no filesystem root, so there is nowhere to "
        "write. Set the endpoint's connection_details.env.root or defaults.root."
    )


def local_path(uri: str, connection_details: dict | None = None) -> Path:
    """Turn a landing URI into a real path on THIS machine.

    A relative uri is resolved against the endpoint's root, which is the intended model:
    the catalog records which dataset goes where, the endpoint records where "there" is,
    and they are combined at execution time by whoever is executing.

    An absolute or ~ path is still honoured for endpoints that genuinely name one, but ~
    is a trap worth naming: it expands to the home of whatever process resolves it, so a
    DAG running in a container wrote a real download into the container's own home
    directory, where nobody could see it and a recreate deleted it.
    """
    if uri.startswith("endpoint://"):
        # Explicitly relative to the endpoint's root. The scheme exists so the row says
        # which rule applies instead of leaving it to be guessed from the shape.
        raw = uri[len("endpoint://"):]
    elif uri.startswith("file://"):
        raw = uri[len("file://"):]
    else:
        raw = uri

    if not uri.startswith("endpoint://") and (raw.startswith("~") or os.path.isabs(raw)):
        return Path(os.path.expanduser(raw)).resolve()

    root = resolve_root(connection_details)
    # The relative path comes from the catalog, but a stored "../.." must not be able to
    # write outside the endpoint's root.
    target = (root / raw).resolve()
    if not str(target).startswith(str(root)):
        raise TransferRefused(
            f"refusing a destination outside the endpoint root: {uri!r}")
    return target


def _safe_name(name: str) -> str:
    """One path segment, no traversal.

    The file names come from a remote listing, which is untrusted input: a server that
    answers with '../../.ssh/authorized_keys' must not be able to choose where we write.
    """
    base = os.path.basename(name.strip().replace("\\", "/"))
    if not base or base in {".", ".."} or not re.fullmatch(r"[A-Za-z0-9._-]{1,200}", base):
        raise TransferRefused(f"refusing unsafe remote filename: {name!r}")
    return base


def download(
    source_uri: str,
    dest_uri: str,
    dest_kind: str,
    *,
    connection_details: dict | None = None,
    max_files: int = DEFAULT_MAX_FILES,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> TransferResult:
    """Copy from `source_uri` into `dest_uri`, returning what was actually written."""
    if dest_kind != "local_fs":
        raise UnsupportedDestination(
            f"destination kind {dest_kind!r} is not implemented yet; only local_fs is. "
            f"The endpoint stays unavailable rather than being marked available with "
            f"nothing behind it."
        )

    dest = local_path(dest_uri, connection_details)
    dest.mkdir(parents=True, exist_ok=True)
    log.info("writing into %s", dest)

    scheme = urllib.parse.urlparse(source_uri).scheme.lower()
    if scheme == "ftp":
        return _from_ftp(source_uri, dest, max_files, max_bytes)
    if scheme in {"http", "https"}:
        return _from_http(source_uri, dest, max_bytes)
    raise UnsupportedDestination(f"source scheme {scheme!r} is not implemented yet")


def _from_ftp(source_uri: str, dest: Path, max_files: int, max_bytes: int) -> TransferResult:
    parts = urllib.parse.urlparse(source_uri)
    directory = parts.path or "/"

    written: list[str] = []
    total = 0
    # Anonymous: every FTP source registered so far is a public archive. A source that
    # needs credentials belongs behind an app_endpoint, not in a URI.
    with ftplib.FTP(parts.hostname or "", timeout=60) as ftp:
        ftp.login()
        ftp.cwd(directory)
        names = sorted(n for n in ftp.nlst() if not n.startswith("."))
        # Checksums and manifests travel with the data and are tiny; taking them first
        # would spend the file budget on metadata.
        payload = [n for n in names if not n.endswith((".md5", ".txt", ".html"))]
        for name in payload[:max_files]:
            safe = _safe_name(name)
            try:
                size = ftp.size(name) or 0
            except ftplib.error_perm:
                size = 0
            if size > max_bytes:
                log.warning("skipping %s: %d bytes exceeds the per-file cap", name, size)
                continue
            target = dest / safe
            # .part then rename: a crashed run must not leave a truncated file that looks
            # complete to whatever reads this directory next.
            tmp = target.with_suffix(target.suffix + ".part")
            with tmp.open("wb") as fh:
                ftp.retrbinary(f"RETR {name}", fh.write)
            tmp.replace(target)
            total += target.stat().st_size
            written.append(safe)
            log.info("downloaded %s (%d bytes)", safe, target.stat().st_size)

    return TransferResult(bytes=total, object_count=len(written), files=written)


def _from_http(source_uri: str, dest: Path, max_bytes: int) -> TransferResult:
    parts = urllib.parse.urlparse(source_uri)
    if parts.scheme != "https":
        raise TransferRefused(f"refusing a plaintext http source: {source_uri!r}")

    name = _safe_name(os.path.basename(parts.path) or "response.json")
    target = dest / name
    tmp = target.with_suffix(target.suffix + ".part")

    req = urllib.request.Request(source_uri, headers={"User-Agent": "akg-data-mgmt/1.0"})
    total = 0
    with urllib.request.urlopen(req, timeout=120) as resp, tmp.open("wb") as fh:
        while chunk := resp.read(1024 * 256):
            total += len(chunk)
            if total > max_bytes:
                tmp.unlink(missing_ok=True)
                raise TransferRefused(f"response exceeded the {max_bytes} byte cap")
            fh.write(chunk)
    tmp.replace(target)
    log.info("downloaded %s (%d bytes)", name, total)
    return TransferResult(bytes=total, object_count=1, files=[name])
