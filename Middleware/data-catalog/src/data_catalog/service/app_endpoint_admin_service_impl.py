"""Endpoint definition rules (ADR-015)."""

from __future__ import annotations

import re
import uuid
from typing import Any

from akg_service_core import ValidationError
from akg_service_core.endpoint_env import ENV_NAME, SECRET_KEYS

from ..common.object_factory import DAO_FACTORY
from ..dao.i_app_endpoint_admin_dao import IAppEndpointAdminDao
from .i_app_endpoint_admin_service import IAppEndpointAdminService

CREDENTIAL_KEYS = {
    "password", "pwd", "secret", "api_key", "apikey", "token", "connection_string",
    "sas_token", "access_key",
}


class AppEndpointAdminServiceImpl(IAppEndpointAdminService):
    def _validate_config_env(self, config_env: dict[str, str], trace_id: str) -> None:
        """Every value must be a variable NAME, not a value.

        The common mistake is pasting the secret where the name belongs. A real secret
        almost never matches `AKG_[A-Z0-9_]+`, so this catches it — and the message
        deliberately does not echo what was sent.
        """
        for key, var_name in (config_env or {}).items():
            if not isinstance(var_name, str) or not ENV_NAME.match(var_name):
                hint = (" (this looks like a value, not a variable name)"
                        if key in SECRET_KEYS else "")
                raise ValidationError(
                    f"config_env[{key!r}] must be an environment variable name matching "
                    f"AKG_[A-Z0-9_]+{hint}",
                    trace_id,
                )

    def _validate_options(self, options: dict[str, Any], trace_id: str) -> None:
        leaked = sorted(set(options or {}) & CREDENTIAL_KEYS)
        if leaked:
            raise ValidationError(
                f"options may not contain credential keys {leaked}; declare the "
                f"environment variable in config_env instead",
                trace_id,
            )

    def create(self, tenant_id: str, data: dict[str, Any], trace_id: str) -> uuid.UUID:
        if not re.match(r"^[a-z0-9][a-z0-9_.-]{0,62}$", data.get("code", "")):
            raise ValidationError(
                "code must be lowercase alphanumeric with - . _ separators", trace_id
            )
        self._validate_config_env(data.get("config_env") or {}, trace_id)
        self._validate_options(data.get("options") or {}, trace_id)
        dao: IAppEndpointAdminDao = DAO_FACTORY.get(IAppEndpointAdminDao)
        return dao.create(tenant_id, data)

    def update(
        self, tenant_id: str, endpoint_id: uuid.UUID, changes: dict[str, Any], trace_id: str
    ) -> bool:
        if "config_env" in changes:
            self._validate_config_env(changes["config_env"], trace_id)
        if "options" in changes:
            self._validate_options(changes["options"], trace_id)
        dao: IAppEndpointAdminDao = DAO_FACTORY.get(IAppEndpointAdminDao)
        return dao.update(tenant_id, endpoint_id, changes)

    def get(self, tenant_id: str, endpoint_id: uuid.UUID) -> dict[str, Any] | None:
        return DAO_FACTORY.get(IAppEndpointAdminDao).get(tenant_id, endpoint_id)

    def unconfigured(self, tenant_id: str) -> list[dict[str, Any]]:
        return DAO_FACTORY.get(IAppEndpointAdminDao).unconfigured(tenant_id)
