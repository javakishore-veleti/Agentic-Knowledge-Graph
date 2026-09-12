"""Find out how this machine can authenticate — without reading any credential.

Everything here reports *availability*: which AWS profiles exist, whether an `az login`
token is present, whether an ambient role is attached. It never reads a key, a token or a
password, and never returns one.

Deliberately does not shell out to `aws` or `az`. A subprocess on every request is slow,
and running a CLI whose arguments derive from stored data is an injection surface for an
answer that can be had by reading the same files those tools write. `probe_cli_login`
exists for the case where you genuinely want the CLI's own view, and the caller has to ask
for it.
"""

from __future__ import annotations

import configparser
import json
import os
from dataclasses import dataclass
from pathlib import Path

AUTH_MODES = (
    "env_vars", "aws_profile", "aws_role", "azure_cli", "azure_managed_identity",
    "azure_client_secret", "gcp_adc", "anonymous",
)


@dataclass(frozen=True)
class AuthProbe:
    mode: str
    available: bool
    detail: str
    #: What was inspected, so a failure is diagnosable. Paths and variable names only.
    evidence: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {"mode": self.mode, "available": self.available, "detail": self.detail,
                "evidence": list(self.evidence)}


def aws_profiles(home: Path | None = None) -> list[str]:
    """Profile names from the AWS shared config files. Names only; no keys are read."""
    home = home or Path.home()
    names: set[str] = set()
    for path, prefix in ((home / ".aws" / "credentials", ""),
                         (home / ".aws" / "config", "profile ")):
        if not path.exists():
            continue
        parser = configparser.RawConfigParser()
        try:
            parser.read(path)
        except Exception:
            continue
        for section in parser.sections():
            names.add(section[len(prefix):] if prefix and section.startswith(prefix) else section)
    return sorted(names)


def azure_cli_subscriptions(home: Path | None = None) -> list[str]:
    """Subscription names `az login` recorded. Reads the profile, never the token cache."""
    home = home or Path.home()
    profile = home / ".azure" / "azureProfile.json"
    if not profile.exists():
        return []
    try:
        # az writes this file with a BOM.
        data = json.loads(profile.read_text(encoding="utf-8-sig") or "{}")
    except Exception:
        return []
    return [s.get("name", "") for s in data.get("subscriptions", []) if s.get("name")]


def probe(mode: str, auth_ref: str | None = None, environ: dict[str, str] | None = None,
          home: Path | None = None) -> AuthProbe:
    env = os.environ if environ is None else environ
    home = home or Path.home()

    if mode == "anonymous":
        return AuthProbe(mode, True, "no credential required")

    if mode == "env_vars":
        # The declared variables are checked by resolve_endpoint; this only reports that
        # the mode itself needs nothing from the machine.
        return AuthProbe(mode, True, "resolved from declared environment variables")

    if mode == "aws_profile":
        found = aws_profiles(home)
        if not found:
            return AuthProbe(mode, False, "no AWS shared config on this machine",
                             ("~/.aws/credentials", "~/.aws/config"))
        if auth_ref and auth_ref not in found:
            return AuthProbe(mode, False,
                             f"profile {auth_ref!r} not among {len(found)} profile(s) here",
                             tuple(found))
        return AuthProbe(mode, True, f"profile {auth_ref!r} present", tuple(found))

    if mode == "aws_role":
        # An attached role announces itself through the environment. IMDS is deliberately
        # not called: a network round trip inside a health check is a hang waiting to
        # happen on a machine that has no metadata service.
        signals = [v for v in ("AWS_ROLE_ARN", "AWS_WEB_IDENTITY_TOKEN_FILE",
                               "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
                               "AWS_CONTAINER_CREDENTIALS_FULL_URI") if env.get(v)]
        if signals:
            return AuthProbe(mode, True, "ambient role detected", tuple(signals))
        return AuthProbe(mode, False,
                         "no role environment present; an EC2 instance profile would still "
                         "work at runtime but cannot be confirmed without calling IMDS",
                         ("AWS_ROLE_ARN", "AWS_WEB_IDENTITY_TOKEN_FILE"))

    if mode == "azure_cli":
        subs = azure_cli_subscriptions(home)
        if subs:
            return AuthProbe(mode, True, f"az login present ({len(subs)} subscription(s))",
                             tuple(subs[:5]))
        return AuthProbe(mode, False, "no az login on this machine; run `az login`",
                         ("~/.azure/azureProfile.json",))

    if mode == "azure_managed_identity":
        signals = [v for v in ("IDENTITY_ENDPOINT", "MSI_ENDPOINT",
                               "AZURE_FEDERATED_TOKEN_FILE") if env.get(v)]
        if signals:
            return AuthProbe(mode, True, "managed identity endpoint present", tuple(signals))
        return AuthProbe(mode, False, "no managed identity endpoint; this mode only works "
                                      "inside Azure", ("IDENTITY_ENDPOINT", "MSI_ENDPOINT"))

    if mode == "azure_client_secret":
        needed = ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET")
        missing = [v for v in needed if not env.get(v)]
        if missing:
            return AuthProbe(mode, False, f"missing {missing}", needed)
        return AuthProbe(mode, True, "service principal variables present", needed)

    if mode == "gcp_adc":
        explicit = env.get("GOOGLE_APPLICATION_CREDENTIALS")
        if explicit and Path(explicit).exists():
            return AuthProbe(mode, True, "GOOGLE_APPLICATION_CREDENTIALS set",
                             ("GOOGLE_APPLICATION_CREDENTIALS",))
        adc = home / ".config" / "gcloud" / "application_default_credentials.json"
        if adc.exists():
            return AuthProbe(mode, True, "application default credentials present",
                             (str(adc.relative_to(home)),))
        return AuthProbe(mode, False, "no application default credentials",
                         ("GOOGLE_APPLICATION_CREDENTIALS",))

    return AuthProbe(mode, False, f"unknown auth mode {mode!r}")


def probe_cli_login(mode: str, timeout: float = 5.0) -> AuthProbe:
    """Ask the vendor CLI directly. Opt-in, because it spawns a process.

    Use when the file-based probe is inconclusive and you want the CLI's own answer —
    an expired `az login` token, for instance, still leaves the profile file behind.
    """
    import subprocess

    cmds = {
        "azure_cli": ["az", "account", "show", "--output", "none"],
        "aws_profile": ["aws", "sts", "get-caller-identity", "--output", "json"],
        "gcp_adc": ["gcloud", "auth", "application-default", "print-access-token"],
    }
    cmd = cmds.get(mode)
    if cmd is None:
        return AuthProbe(mode, False, "no CLI check for this mode")
    try:
        # Fixed argv, never a shell: nothing stored can become a command.
        done = subprocess.run(cmd, capture_output=True, timeout=timeout, check=False)
    except FileNotFoundError:
        return AuthProbe(mode, False, f"{cmd[0]} is not installed")
    except subprocess.TimeoutExpired:
        return AuthProbe(mode, False, f"{cmd[0]} timed out after {timeout}s")
    if done.returncode == 0:
        return AuthProbe(mode, True, f"{cmd[0]} reports an active session")
    # stderr can contain a token in some CLI failure paths, so it is not echoed.
    return AuthProbe(mode, False, f"{cmd[0]} exited {done.returncode}")
