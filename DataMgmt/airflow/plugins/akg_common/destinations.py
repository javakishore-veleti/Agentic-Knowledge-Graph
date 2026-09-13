"""Writing acquired bytes into a destination.

Every destination downloads FRESH FROM THE SOURCE. A copy in S3 is not derived from the
local copy: each landing endpoint is an independent acquisition with its own run, so one
destination being stale, deleted or never acquired says nothing about the others.

Credentials never appear here. The endpoint's connection_details carries the NAMES of
environment variables and the connection type; the value comes from the environment the
runner executes in. That is what lets one catalog row describe a laptop, a CI runner and
a pod with a managed identity.
"""

from __future__ import annotations

import logging
import os
import urllib.parse
from pathlib import Path
from typing import Any, Callable, Iterator

log = logging.getLogger(__name__)


class DestinationError(RuntimeError):
    """The destination could not be written, and retrying will not help."""


def _env(details: dict[str, Any], key: str, default: str | None = None) -> str | None:
    """Read a value whose NAME the endpoint declares.

    Falls back to the endpoint's own default, then to the caller's. Deliberately never
    reads a literal value from the top level of connection_details: a CHECK constraint
    rejects credential-shaped keys there, and honouring one anyway would make that
    constraint a formality.
    """
    name = (details.get("env") or {}).get(key)
    if name and os.environ.get(name):
        return os.environ[name]
    fallback = (details.get("defaults") or {}).get(key)
    if fallback:
        return str(fallback)
    plain = details.get(key)
    if plain is not None and key not in _SECRET_KEYS:
        return str(plain)
    return default


#: Keys whose value must come from the environment, never from a stored literal.
_SECRET_KEYS = frozenset({
    "password", "secret", "client_secret", "access_key_id", "secret_access_key",
    "account_key", "sas_token", "api_key", "token", "connection_string",
})


# ---------------------------------------------------------------------- S3


def write_s3(dest_uri: str, details: dict[str, Any],
             files: Iterator[tuple[str, Path]]) -> tuple[int, int]:
    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
    except ImportError as exc:  # pragma: no cover - the image installs it
        raise DestinationError(f"the S3 SDK is not installed: {exc}") from exc

    parts = urllib.parse.urlparse(dest_uri)
    bucket = parts.netloc or _env(details, "bucket") or ""
    prefix = parts.path.lstrip("/")
    if not bucket:
        raise DestinationError(
            "no S3 bucket: the destination URI has no host and the endpoint declares no "
            "bucket")

    conn_type = details.get("__connection_type", "")
    session_kwargs: dict[str, Any] = {}
    if conn_type == "profile":
        profile = details.get("profile") or _env(details, "profile")
        if not profile:
            raise DestinationError(
                "the endpoint is profile-based but names no profile")
        session_kwargs["profile_name"] = profile
    elif conn_type == "env_vars":
        key_id = _env(details, "access_key_id")
        secret = _env(details, "secret_access_key")
        if not key_id or not secret:
            raise DestinationError(
                "the endpoint expects credentials from the environment, but the "
                "variables it names are not set where this workflow runs")
        session_kwargs["aws_access_key_id"] = key_id
        session_kwargs["aws_secret_access_key"] = secret
    # 'ambient' falls through to the default credential chain: instance profile, task
    # role or IRSA, which is exactly what having no explicit credentials means.

    region = _env(details, "region")
    if region:
        session_kwargs["region_name"] = region

    try:
        client = boto3.Session(**session_kwargs).client(
            "s3", endpoint_url=_env(details, "endpoint_url"))
        written = total = 0
        for name, path in files:
            key = f"{prefix.rstrip('/')}/{name}" if prefix else name
            client.upload_file(str(path), bucket, key)
            total += path.stat().st_size
            written += 1
            log.info("uploaded s3://%s/%s", bucket, key)
        return total, written
    except NoCredentialsError as exc:
        raise DestinationError(
            "no AWS credentials are available where this workflow runs. The endpoint "
            "describes HOW to authenticate; the credentials themselves must exist in the "
            "runner's environment."
        ) from exc
    except (BotoCoreError, ClientError) as exc:
        raise DestinationError(f"S3 rejected the upload: {exc}") from exc


# ------------------------------------------------------------- Azure Blob


def write_azure_blob(dest_uri: str, details: dict[str, Any],
                     files: Iterator[tuple[str, Path]]) -> tuple[int, int]:
    try:
        from azure.core.exceptions import AzureError
        from azure.storage.blob import BlobServiceClient
    except ImportError as exc:  # pragma: no cover
        raise DestinationError(f"the Azure SDK is not installed: {exc}") from exc

    parts = urllib.parse.urlparse(dest_uri)
    container = parts.netloc or _env(details, "container") or ""
    prefix = parts.path.lstrip("/")
    if not container:
        raise DestinationError("no Blob container in the destination URI or endpoint")

    account = _env(details, "account")
    conn_type = details.get("__connection_type", "")

    # An explicit service URL is what makes a local emulator reachable; without it the
    # account name alone implies the public cloud.
    service_url = _env(details, "service_url")
    account_key = _env(details, "account_key")

    try:
        if account_key:
            # The account name is passed explicitly rather than left to the SDK. It infers
            # it from the host label of a standard account URL, which a path-style URL --
            # every emulator, and some private endpoints -- does not have, and the failure
            # is "Unable to determine account name" rather than anything about the URL.
            shared_key = {"account_name": account or "", "account_key": account_key}
            client = BlobServiceClient(
                account_url=service_url or f"https://{account}.blob.core.windows.net",
                credential=shared_key)
        else:
            credential = _azure_credential(conn_type, details)
            client = BlobServiceClient(
                account_url=service_url or f"https://{account}.blob.core.windows.net",
                credential=credential)

        container_client = client.get_container_client(container)
        try:
            container_client.create_container()
        except AzureError:
            # Already there. Creating it is a convenience, not the point of the run.
            pass

        written = total = 0
        for name, path in files:
            blob = f"{prefix.rstrip('/')}/{name}" if prefix else name
            with path.open("rb") as fh:
                container_client.upload_blob(name=blob, data=fh, overwrite=True)
            total += path.stat().st_size
            written += 1
            log.info("uploaded blob %s/%s", container, blob)
        return total, written
    except AzureError as exc:
        raise DestinationError(f"Azure rejected the upload: {exc}") from exc


def _azure_credential(conn_type: str, details: dict[str, Any]) -> Any:
    from azure.identity import (
        AzureCliCredential, ClientSecretCredential, DefaultAzureCredential,
        ManagedIdentityCredential,
    )

    if conn_type == "command":
        # The endpoint's allowlisted command is az_cli_token; this is the SDK's
        # equivalent, which reads the token `az login` already left on this machine.
        return AzureCliCredential()
    if conn_type == "client_credentials":
        tenant = _env(details, "tenant_id")
        client_id = _env(details, "client_id")
        secret = _env(details, "client_secret")
        if not (tenant and client_id and secret):
            raise DestinationError(
                "the endpoint expects a service principal, but the variables it names "
                "are not set where this workflow runs")
        return ClientSecretCredential(tenant, client_id, secret)
    if conn_type == "ambient":
        client_id = _env(details, "client_id")
        return ManagedIdentityCredential(client_id=client_id) if client_id \
            else ManagedIdentityCredential()
    return DefaultAzureCredential()


# --------------------------------------------------------------------- GCS


def write_gcs(dest_uri: str, details: dict[str, Any],
              files: Iterator[tuple[str, Path]]) -> tuple[int, int]:
    try:
        from google.api_core.exceptions import GoogleAPIError
        from google.auth.exceptions import DefaultCredentialsError
        from google.cloud import storage
    except ImportError as exc:  # pragma: no cover
        raise DestinationError(f"the GCS SDK is not installed: {exc}") from exc

    parts = urllib.parse.urlparse(dest_uri)
    bucket_name = parts.netloc or _env(details, "bucket") or ""
    prefix = parts.path.lstrip("/")
    if not bucket_name:
        raise DestinationError("no GCS bucket in the destination URI or endpoint")

    try:
        # Application Default Credentials only: a key file on disk is the thing every
        # GCP hardening guide tells you to stop doing.
        client = storage.Client(project=_env(details, "project"))
        bucket = client.bucket(bucket_name)
        written = total = 0
        for name, path in files:
            blob_name = f"{prefix.rstrip('/')}/{name}" if prefix else name
            bucket.blob(blob_name).upload_from_filename(str(path))
            total += path.stat().st_size
            written += 1
            log.info("uploaded gs://%s/%s", bucket_name, blob_name)
        return total, written
    except DefaultCredentialsError as exc:
        raise DestinationError(
            "no Google application default credentials where this workflow runs"
        ) from exc
    except GoogleAPIError as exc:
        raise DestinationError(f"GCS rejected the upload: {exc}") from exc


WRITERS: dict[str, Callable[..., tuple[int, int]]] = {
    "s3": write_s3,
    "azure_blob": write_azure_blob,
    "gcs": write_gcs,
}
