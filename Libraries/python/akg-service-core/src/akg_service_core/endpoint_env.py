"""Resolve an endpoint's connection details from the environment (ADR-015).

The catalog stores which environment variable supplies each value. This reads them where
the code happens to be running, so one endpoint row works in local, Azure and AWS.

Nothing here ever logs or returns a resolved secret. `describe` reports which variables
are present and which are missing, by name only — that is what makes a misconfigured
deployment diagnosable without putting credentials in a response body.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

ENV_NAME = re.compile(r"^AKG_[A-Z0-9_]{2,62}$")

#: Keys whose resolved values must never be logged, echoed or returned.
SECRET_KEYS = frozenset({
    "secret_access_key", "access_key_id", "session_token", "password", "connection_string",
    "sas_token", "account_key", "api_key", "token", "client_secret", "private_key",
})


@dataclass(frozen=True)
class ResolvedEndpoint:
    code: str
    values: dict[str, str] = field(default_factory=dict, repr=False)
    missing: tuple[str, ...] = ()
    invalid: tuple[str, ...] = ()
    #: Keys that fell back to a declared default because no variable was set. Reported
    #: separately from `resolved` so "it worked" and "it worked by default" are
    #: distinguishable -- they behave the same until the day the default is wrong.
    defaulted: tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        return not self.missing and not self.invalid

    def require(self, key: str) -> str:
        if key not in self.values:
            raise KeyError(
                f"endpoint {self.code!r} has no value for {key!r}; "
                f"missing environment variables: {list(self.missing)}"
            )
        return self.values[key]

    def describe(self) -> dict[str, object]:
        """Presence, never values. Safe to return from an API and to log."""
        return {
            "code": self.code,
            "complete": self.complete,
            "resolved": sorted(self.values),
            "defaulted": list(self.defaulted),
            "missing": list(self.missing),
            "invalid": list(self.invalid),
        }

    def __repr__(self) -> str:  # pragma: no cover - defensive
        return (f"ResolvedEndpoint(code={self.code!r}, resolved={sorted(self.values)}, "
                f"missing={list(self.missing)})")


def resolve_endpoint(
    code: str,
    config_env: dict[str, str],
    environ: dict[str, str] | None = None,
    defaults: dict[str, str] | None = None,
) -> ResolvedEndpoint:
    """Read each declared variable from the environment, falling back to a declared default.

    Defaults exist so a fresh checkout works with nothing configured: a filesystem root
    under the user's home is a sensible guess, and making someone set a variable before
    anything runs is friction for no safety.

    A default is refused for anything secret-shaped. Substituting a default credential
    would connect as the wrong identity, or with a blank one, and succeed quietly enough
    that the mistake surfaces somewhere else entirely. Missing secrets stay missing.
    """
    env = os.environ if environ is None else environ
    defaults = defaults or {}
    values: dict[str, str] = {}
    missing: list[str] = []
    invalid: list[str] = []
    defaulted: list[str] = []

    for key, var_name in (config_env or {}).items():
        if not isinstance(var_name, str) or not ENV_NAME.match(var_name):
            # A value that is not a well-formed variable name is usually the secret
            # itself, pasted where the name belongs.
            invalid.append(key)
            continue
        value = env.get(var_name)
        if value:
            values[key] = value
            continue
        fallback = defaults.get(key)
        if fallback and key not in SECRET_KEYS:
            values[key] = expand_path(fallback)
            defaulted.append(key)
        else:
            missing.append(var_name)

    return ResolvedEndpoint(code=code, values=values, missing=tuple(missing),
                            invalid=tuple(invalid), defaulted=tuple(defaulted))


def expand_path(value: str) -> str:
    """Expand ~ and $VARS in a filesystem default.

    A default of "~/runtime_data/AKG/Local/FileSystem" has to become a real path on the
    machine reading it; leaving the tilde produces a directory literally named "~".
    """
    if value.startswith("~") or "$" in value:
        return os.path.expanduser(os.path.expandvars(value))
    return value


def redact(values: dict[str, str]) -> dict[str, str]:
    """Mask anything secret-shaped before it reaches a log line."""
    return {k: ("***" if k in SECRET_KEYS else v) for k, v in values.items()}
