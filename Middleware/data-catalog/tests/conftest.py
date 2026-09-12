"""Test fixtures.

The suite seeds everything it needs. An earlier version relied on rows created outside it,
so it passed or failed depending on which container it happened to run against — which is
not a test result, it is a coincidence.
"""

from __future__ import annotations

import os

import pytest

DB = os.environ.get("AKG_DATABASE_URL")


@pytest.fixture(scope="session", autouse=True)
def seed_reference_data() -> None:
    """Ensure the domain the tests build MIOs in exists.

    There is no create-domain API yet, so this goes in through SQL. Idempotent, so running
    the suite twice against one database is fine.
    """
    if not DB:
        return
    import sqlalchemy

    engine = sqlalchemy.create_engine(DB)
    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.text(
                "INSERT INTO catalog.domain (domain_id, code, name, description, tenant_id) "
                "VALUES (:id, 'biomedical', 'Biomedical', 'Literature and trials', 'reference') "
                "ON CONFLICT (tenant_id, code) DO NOTHING"
            ),
            {"id": "11111111-1111-1111-1111-111111111111"},
        )
    engine.dispose()
