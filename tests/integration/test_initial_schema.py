"""Integration tests against a real Postgres instance for the VHIRE-1
initial schema migration: table existence, I1/I7/I8 constraints, the I3
cross-table trigger, the I4 immutability trigger + amend_scorecard, the
audit_log append-only trigger, and RLS policy presence.

Requires DATABASE_URL to be reachable - see tests/integration/conftest.py
for the skip-if-unreachable behavior.
"""

import json
import uuid

import asyncpg
import pytest

EXPECTED_TABLES = {
    "organizations",
    "hr_users",
    "job_requisitions",
    "candidates",
    "resumes",
    "applications",
    "interviews",
    "scorecards",
    "analysis_outputs",
    "audit_log",
}


async def test_all_tables_exist(conn: asyncpg.Connection):
    rows = await conn.fetch(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
    )
    assert EXPECTED_TABLES <= {row["tablename"] for row in rows}


async def test_rls_enabled_on_every_org_scoped_table(conn: asyncpg.Connection):
    rows = await conn.fetch(
        """
        SELECT relname, relrowsecurity, relforcerowsecurity
        FROM pg_class
        WHERE relname = ANY($1::text[])
        """,
        list(EXPECTED_TABLES - {"organizations"}),
    )
    assert len(rows) == len(EXPECTED_TABLES) - 1
    for row in rows:
        assert row["relrowsecurity"] is True, f"{row['relname']} missing ENABLE ROW LEVEL SECURITY"
        assert row["relforcerowsecurity"] is True, f"{row['relname']} missing FORCE ROW LEVEL SECURITY"


@pytest.fixture
async def seed(conn: asyncpg.Connection) -> dict[str, uuid.UUID]:
    org_id = uuid.uuid4()
    other_org_id = uuid.uuid4()
    hr_user_id = uuid.uuid4()
    requisition_id = uuid.uuid4()
    candidate_id = uuid.uuid4()
    other_org_candidate_id = uuid.uuid4()
    resume_id = uuid.uuid4()

    await conn.execute(
        "INSERT INTO organizations (id, name) VALUES ($1, 'Org A'), ($2, 'Org B')",
        org_id,
        other_org_id,
    )
    await conn.execute(
        """
        INSERT INTO hr_users (id, organization_id, email, full_name, role, status)
        VALUES ($1, $2, 'owner@org-a.test', 'Owner', 'recruiter', 'active')
        """,
        hr_user_id,
        org_id,
    )
    await conn.execute(
        """
        INSERT INTO job_requisitions
            (id, organization_id, title, owner_hr_user_id, status, scorecard_template)
        VALUES ($1, $2, 'Engineer', $3, 'open', $4::jsonb)
        """,
        requisition_id,
        org_id,
        hr_user_id,
        json.dumps({"fields": []}),
    )
    await conn.execute(
        """
        INSERT INTO candidates (id, organization_id, email, full_name, status)
        VALUES ($1, $2, 'candidate@example.test', 'Candidate A', 'active'),
               ($3, $4, 'other@example.test', 'Candidate B', 'active')
        """,
        candidate_id,
        org_id,
        other_org_candidate_id,
        other_org_id,
    )
    await conn.execute(
        """
        INSERT INTO resumes (id, organization_id, candidate_id, file_object_key, status)
        VALUES ($1, $2, $3, 'orgA/resume.pdf', 'uploaded')
        """,
        resume_id,
        org_id,
        candidate_id,
    )
    return {
        "org_id": org_id,
        "other_org_id": other_org_id,
        "hr_user_id": hr_user_id,
        "requisition_id": requisition_id,
        "candidate_id": candidate_id,
        "other_org_candidate_id": other_org_candidate_id,
        "resume_id": resume_id,
    }


async def test_i1_resume_requires_candidate(conn: asyncpg.Connection, seed: dict):
    with pytest.raises(asyncpg.NotNullViolationError):
        await conn.execute(
            """
            INSERT INTO resumes (id, organization_id, candidate_id, file_object_key, status)
            VALUES ($1, $2, NULL, 'x.pdf', 'uploaded')
            """,
            uuid.uuid4(),
            seed["org_id"],
        )


async def test_i3_rejects_cross_org_application(conn: asyncpg.Connection, seed: dict):
    with pytest.raises(asyncpg.RaiseError, match="I3"):
        await conn.execute(
            """
            INSERT INTO applications
                (id, organization_id, candidate_id, job_requisition_id, resume_id, status)
            VALUES ($1, $2, $3, $4, $5, 'submitted')
            """,
            uuid.uuid4(),
            seed["org_id"],
            seed["other_org_candidate_id"],
            seed["requisition_id"],
            seed["resume_id"],
        )


async def test_i3_allows_same_org_application(conn: asyncpg.Connection, seed: dict):
    application_id = uuid.uuid4()
    await conn.execute(
        """
        INSERT INTO applications
            (id, organization_id, candidate_id, job_requisition_id, resume_id, status)
        VALUES ($1, $2, $3, $4, $5, 'submitted')
        """,
        application_id,
        seed["org_id"],
        seed["candidate_id"],
        seed["requisition_id"],
        seed["resume_id"],
    )
    row = await conn.fetchrow("SELECT id FROM applications WHERE id = $1", application_id)
    assert row is not None


async def test_active_application_uniqueness_allows_reapplication_after_rejection(
    conn: asyncpg.Connection, seed: dict
):
    first_id = uuid.uuid4()
    await conn.execute(
        """
        INSERT INTO applications
            (id, organization_id, candidate_id, job_requisition_id, resume_id, status)
        VALUES ($1, $2, $3, $4, $5, 'submitted')
        """,
        first_id,
        seed["org_id"],
        seed["candidate_id"],
        seed["requisition_id"],
        seed["resume_id"],
    )

    with pytest.raises(asyncpg.UniqueViolationError):
        await conn.execute(
            """
            INSERT INTO applications
                (id, organization_id, candidate_id, job_requisition_id, resume_id, status)
            VALUES ($1, $2, $3, $4, $5, 'submitted')
            """,
            uuid.uuid4(),
            seed["org_id"],
            seed["candidate_id"],
            seed["requisition_id"],
            seed["resume_id"],
        )

    await conn.execute("UPDATE applications SET status = 'rejected' WHERE id = $1", first_id)

    second_id = uuid.uuid4()
    await conn.execute(
        """
        INSERT INTO applications
            (id, organization_id, candidate_id, job_requisition_id, resume_id, status)
        VALUES ($1, $2, $3, $4, $5, 'submitted')
        """,
        second_id,
        seed["org_id"],
        seed["candidate_id"],
        seed["requisition_id"],
        seed["resume_id"],
    )
    row = await conn.fetchrow("SELECT id FROM applications WHERE id = $1", second_id)
    assert row is not None


@pytest.fixture
async def interview(conn: asyncpg.Connection, seed: dict) -> uuid.UUID:
    application_id = uuid.uuid4()
    await conn.execute(
        """
        INSERT INTO applications
            (id, organization_id, candidate_id, job_requisition_id, resume_id, status)
        VALUES ($1, $2, $3, $4, $5, 'submitted')
        """,
        application_id,
        seed["org_id"],
        seed["candidate_id"],
        seed["requisition_id"],
        seed["resume_id"],
    )
    interview_id = uuid.uuid4()
    await conn.execute(
        """
        INSERT INTO interviews
            (id, organization_id, application_id, interviewer_hr_user_id, scheduled_at, status)
        VALUES ($1, $2, $3, $4, now(), 'completed')
        """,
        interview_id,
        seed["org_id"],
        application_id,
        seed["hr_user_id"],
    )
    return interview_id


async def test_i7_interview_requires_application(conn: asyncpg.Connection, seed: dict):
    with pytest.raises(asyncpg.NotNullViolationError):
        await conn.execute(
            """
            INSERT INTO interviews
                (id, organization_id, application_id, interviewer_hr_user_id, scheduled_at, status)
            VALUES ($1, $2, NULL, $3, now(), 'scheduled')
            """,
            uuid.uuid4(),
            seed["org_id"],
            seed["hr_user_id"],
        )


async def test_i8_scorecard_unique_per_interview(
    conn: asyncpg.Connection, seed: dict, interview: uuid.UUID
):
    await conn.execute(
        """
        INSERT INTO scorecards (id, organization_id, interview_id, ratings, status)
        VALUES ($1, $2, $3, '{}'::jsonb, 'draft')
        """,
        uuid.uuid4(),
        seed["org_id"],
        interview,
    )
    with pytest.raises(asyncpg.UniqueViolationError):
        await conn.execute(
            """
            INSERT INTO scorecards (id, organization_id, interview_id, ratings, status)
            VALUES ($1, $2, $3, '{}'::jsonb, 'draft')
            """,
            uuid.uuid4(),
            seed["org_id"],
            interview,
        )


@pytest.fixture
async def submitted_scorecard(conn: asyncpg.Connection, seed: dict, interview: uuid.UUID) -> uuid.UUID:
    scorecard_id = uuid.uuid4()
    await conn.execute(
        """
        INSERT INTO scorecards (id, organization_id, interview_id, ratings, status, submitted_at)
        VALUES ($1, $2, $3, $4::jsonb, 'submitted', now())
        """,
        scorecard_id,
        seed["org_id"],
        interview,
        json.dumps({"communication": 4}),
    )
    return scorecard_id


async def test_i4_direct_update_on_submitted_scorecard_rejected(
    conn: asyncpg.Connection, submitted_scorecard: uuid.UUID
):
    with pytest.raises(asyncpg.RaiseError, match="I4"):
        await conn.execute(
            "UPDATE scorecards SET notes = 'sneaky edit' WHERE id = $1", submitted_scorecard
        )


async def test_i4_amend_scorecard_writes_audit_log_and_preserves_via_new_status(
    conn: asyncpg.Connection, seed: dict, submitted_scorecard: uuid.UUID
):
    new_ratings = json.dumps({"communication": 5})
    result = await conn.fetchrow(
        "SELECT * FROM amend_scorecard($1, $2::jsonb, $3, $4)",
        submitted_scorecard,
        new_ratings,
        "corrected after review",
        seed["hr_user_id"],
    )
    assert result["status"] == "amended"
    assert result["notes"] == "corrected after review"

    audit_rows = await conn.fetch(
        "SELECT * FROM audit_log WHERE entity_id = $1 AND action = 'amended'", submitted_scorecard
    )
    assert len(audit_rows) == 1
    diff = json.loads(audit_rows[0]["diff"])
    assert diff["before"]["status"] == "submitted"
    assert diff["after"]["status"] == "amended"


async def test_audit_log_is_append_only(conn: asyncpg.Connection, seed: dict):
    audit_id = uuid.uuid4()
    await conn.execute(
        """
        INSERT INTO audit_log (id, organization_id, entity_type, entity_id, action, actor_hr_user_id, diff)
        VALUES ($1, $2, 'scorecard', $3, 'amended', $4, '{}'::jsonb)
        """,
        audit_id,
        seed["org_id"],
        uuid.uuid4(),
        seed["hr_user_id"],
    )
    with pytest.raises(asyncpg.RaiseError, match="append-only"):
        await conn.execute("UPDATE audit_log SET action = 'tampered' WHERE id = $1", audit_id)
    with pytest.raises(asyncpg.RaiseError, match="append-only"):
        await conn.execute("DELETE FROM audit_log WHERE id = $1", audit_id)
