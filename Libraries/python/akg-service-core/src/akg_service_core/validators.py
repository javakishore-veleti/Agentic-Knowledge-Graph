"""Shared validators.

Kept here rather than in a service because the rules they enforce are about what may be
stored at all, and more than one service writes these fields.
"""

from __future__ import annotations

import re

#: scheme://userinfo@host -- a credential embedded in a locator.
_URI_WITH_USERINFO = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://[^/@]*:[^/@]*@")
_URI_WITH_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://.+")


def uri_carries_credentials(uri: str) -> bool:
    return bool(_URI_WITH_USERINFO.match(uri or ""))


def uri_has_scheme(uri: str) -> bool:
    return bool(_URI_WITH_SCHEME.match(uri or ""))


def redact_uri(uri: str) -> str:
    """Replace any userinfo with ***.

    Every message about a rejected URI goes through this. Reporting the offending value
    verbatim is how the credential ends up in the log line written to complain about it.
    """
    return re.sub(r"(^[a-zA-Z][a-zA-Z0-9+.-]*://)[^/@]*:[^/@]*@", r"\1***:***@", uri or "")
