"""Dataset location rules live here, not in the routers (ADR-010)."""

from __future__ import annotations

import uuid
from typing import Any

from akg_service_core import (
    NotFoundError, ValidationError, redact_uri, uri_carries_credentials, uri_has_scheme,
)

from ..common.object_factory import DAO_FACTORY
from ..dao.i_dataset_endpoint_dao import IAcquisitionDao, IDatasetEndpointDao
from ..dtos.catalog_dtos import AddDatasetEndpointReq, DatasetEndpointDto
from .i_dataset_location_service import IDatasetLocationService

VALID_SYNC_STATUS = {"RUNNING", "COMPLETED", "FAILED", "CANCELLED"}


class DatasetLocationServiceImpl(IDatasetLocationService):
    def list_locations(
        self, tenant_id: str, dataset_id: uuid.UUID, role: str | None, trace_id: str
    ) -> list[DatasetEndpointDto]:
        dao: IDatasetEndpointDao = DAO_FACTORY.get(IDatasetEndpointDao)
        return dao.for_dataset(tenant_id, dataset_id, role)

    def add_location(
        self, tenant_id: str, req: AddDatasetEndpointReq, trace_id: str
    ) -> uuid.UUID:
        """Validate before the database.

        The CHECK constraints catch all of this too, but a constraint violation arrives as
        a driver error quoting the whole failing row -- so a rejected
        `postgres://user:password@host/db` would put that password in the exception text
        and in the log line written to complain about it. These messages name the problem
        and never the value.
        """
        if uri_carries_credentials(req.uri):
            raise ValidationError(
                f"uri carries credentials ({redact_uri(req.uri)}); store the secret in "
                f"the app_endpoint's secret_ref and give a locator only",
                trace_id,
            )
        if not uri_has_scheme(req.uri):
            raise ValidationError(
                "uri must start with a scheme, for example s3://bucket/prefix or "
                "file:///mnt/data/raw",
                trace_id,
            )
        if req.role != "source" and req.app_endpoint_id is None:
            raise ValidationError(
                f"role {req.role!r} is a destination and must name a registered "
                f"app_endpoint: you cannot store into a system with no host or owner",
                trace_id,
            )
        dao: IDatasetEndpointDao = DAO_FACTORY.get(IDatasetEndpointDao)
        return dao.add(tenant_id, req)

    def get_location(self, tenant_id: str, endpoint_id: uuid.UUID) -> dict[str, Any] | None:
        return DAO_FACTORY.get(IAcquisitionDao).get(tenant_id, endpoint_id)

    def claim(
        self, tenant_id: str, endpoint_id: uuid.UUID, exec_id: uuid.UUID, force: bool,
        trace_id: str,
    ) -> tuple[bool, str]:
        return DAO_FACTORY.get(IAcquisitionDao).claim(tenant_id, endpoint_id, exec_id, force)

    def report_sync(
        self, tenant_id: str, endpoint_id: uuid.UUID, status: str,
        bytes_written: int | None, object_count: int | None,
        error: dict[str, Any] | None, wf_ref_id: str | None, trace_id: str,
    ) -> dict[str, Any] | None:
        if status not in VALID_SYNC_STATUS:
            raise ValidationError(
                f"status must be one of {sorted(VALID_SYNC_STATUS)}", trace_id
            )
        dao: IAcquisitionDao = DAO_FACTORY.get(IAcquisitionDao)
        out = dao.complete(
            tenant_id, endpoint_id, status, bytes_written, object_count, error, wf_ref_id
        )
        if out is None:
            raise NotFoundError("dataset_endpoint", str(endpoint_id), trace_id)
        return out

    def stuck(self, tenant_id: str) -> list[dict[str, Any]]:
        return DAO_FACTORY.get(IAcquisitionDao).stuck(tenant_id)
