"""SQLAlchemy models.

The schema is owned by the SQL migrations in CICD/Local/Postgres/init, not generated
from these classes. The constraints that matter -- one CDC instance per MIO, no
credentials in endpoint options, a live MIO must name its pin -- live in the database so
they hold against psql, a migration script, and any future service, not only against
this process (ADR-009).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Domain(Base):
    __tablename__ = "domain"
    __table_args__ = {"schema": "catalog"}

    domain_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    datasets: Mapped[list[Dataset]] = relationship(back_populates="domain", lazy="selectin")


class Dataset(Base):
    __tablename__ = "dataset"
    __table_args__ = {"schema": "catalog"}

    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    domain_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("catalog.domain.domain_id"), nullable=False
    )
    code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    source_version: Mapped[str] = mapped_column(Text, nullable=False)
    adapter: Mapped[str] = mapped_column(Text, default="generic-extraction")
    sub_domain: Mapped[str] = mapped_column(Text, default="")
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    domain: Mapped[Domain] = relationship(back_populates="datasets")


class Mio(Base):
    """Managed Informational Object: the produced, managed artifact. Project-like."""

    __tablename__ = "mio"
    __table_args__ = {"schema": "catalog"}

    mio_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    domain_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("catalog.domain.domain_id"), nullable=False
    )
    code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    tech_stack: Mapped[str] = mapped_column(Text, nullable=False)
    documents_count: Mapped[int] = mapped_column(BigInteger, default=0)
    edges_count: Mapped[int] = mapped_column(BigInteger, default=0)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    validations: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    state: Mapped[str] = mapped_column(Text, default="draft")
    pinned_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    instances: Mapped[list[DataInstance]] = relationship(back_populates="mio", lazy="selectin")


class DataInstance(Base):
    __tablename__ = "data_instance"
    __table_args__ = {"schema": "catalog"}

    data_instance_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    mio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("catalog.mio.mio_id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    state: Mapped[str] = mapped_column(Text, default="pending")
    stream_cursor: Mapped[str | None] = mapped_column(Text, nullable=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    mio: Mapped[Mio] = relationship(back_populates="instances")


class DataInstanceExec(Base):
    __tablename__ = "data_instance_exec"
    __table_args__ = {"schema": "catalog"}

    data_instance_exec_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    data_instance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("catalog.data_instance.data_instance_id"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, default="PENDING")
    input_tech: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_tech: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_data_json: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    output_data_json: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    wf_execs_json: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    produced_mio_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("catalog.mio.mio_id"), nullable=True
    )
    trace_id: Mapped[str] = mapped_column(Text, nullable=False)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False)
    env: Mapped[str] = mapped_column(Text, nullable=False)
    requested_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AppEndpoint(Base):
    """Where a technology lives. Never where its credentials live."""

    __tablename__ = "app_endpoint"
    __table_args__ = {"schema": "catalog"}

    app_endpoint_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    tech_stack: Mapped[str] = mapped_column(Text, nullable=False)
    env: Mapped[str] = mapped_column(Text, nullable=False)
    host: Mapped[str] = mapped_column(Text, nullable=False)
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    database: Mapped[str | None] = mapped_column(String, nullable=True)
    options: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    secret_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
