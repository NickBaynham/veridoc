"""Integration tests: canonical schema objects exist."""

from __future__ import annotations

import pytest

EXPECTED_TABLES = frozenset(
    {
        "users",
        "organizations",
        "organization_members",
        "collections",
        "documents",
        "document_sources",
        "document_tags",
        "pipeline_runs",
        "pipeline_events",
        "document_scores",
    }
)


@pytest.mark.integration
def test_expected_tables_exist(db_conn):
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """
        )
        found = {row[0] for row in cur.fetchall()}
    missing = EXPECTED_TABLES - found
    assert not missing, f"missing tables: {sorted(missing)}; found: {sorted(found)}"


@pytest.mark.integration
def test_documents_analysis_metadata_column_exists(db_conn):
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
              SELECT 1
              FROM information_schema.columns
              WHERE table_schema = 'public'
                AND table_name = 'documents'
                AND column_name = 'analysis_metadata'
            )
            """
        )
        assert cur.fetchone()[0] is True


@pytest.mark.integration
def test_updated_at_trigger_function_exists(db_conn):
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
              SELECT 1
              FROM pg_proc p
              JOIN pg_namespace n ON n.oid = p.pronamespace
              WHERE n.nspname = 'public' AND p.proname = 'verifiedsignal_set_updated_at'
            )
            """
        )
        assert cur.fetchone()[0] is True
