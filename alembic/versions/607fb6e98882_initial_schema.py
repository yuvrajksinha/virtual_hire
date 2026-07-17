"""initial schema

Creates every Postgres table in docs/05-data-model.md (VHIRE-1 / E1), the
I3 cross-table consistency trigger on `applications`, the I4 scorecard
immutability trigger + `amend_scorecard` stored procedure, the audit_log
append-only trigger, and row-level security policies on every org-scoped
table (I2). No vector/embedding schema — that lives in Qdrant (E7), not
Postgres, per the 2026-07-15 pgvector->Qdrant revision.

Revision ID: 607fb6e98882
Revises:
Create Date: 2026-07-16 00:03:30.219652

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "607fb6e98882"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (enum type name, member values) - member order matches app/models/enums.py
ENUMS: list[tuple[str, list[str]]] = [
    ("organization_status", ["active", "suspended", "deactivated"]),
    ("hr_user_role", ["hr_generalist", "recruiter", "hiring_manager"]),
    ("hr_user_status", ["invited", "active", "deactivated"]),
    ("job_requisition_status", ["draft", "open", "on_hold", "filled", "cancelled"]),
    ("candidate_status", ["active", "archived", "deleted"]),
    ("resume_status", ["uploaded", "parsing", "parsed", "parse_failed"]),
    ("embedding_status", ["not_embedded", "embedding", "embedded", "embed_failed"]),
    (
        "application_status",
        ["submitted", "screening", "interviewing", "offer", "hired", "rejected", "withdrawn"],
    ),
    ("interview_status", ["scheduled", "completed", "cancelled", "no_show"]),
    ("scorecard_status", ["draft", "submitted", "amended"]),
]

# Every table carrying organization_id gets an RLS policy scoping reads/writes
# to current_setting('app.current_org_id') - the DB-layer half of I2.
ORG_SCOPED_TABLES = [
    "hr_users",
    "job_requisitions",
    "candidates",
    "resumes",
    "applications",
    "interviews",
    "scorecards",
    "analysis_outputs",
    "audit_log",
]

TIMESTAMP_COLS = (
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
)


def _uuid_pk() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )


def _org_fk() -> sa.Column:
    return sa.Column(
        "organization_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("organizations.id"),
        nullable=False,
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    bind = op.get_bind()
    for name, values in ENUMS:
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)

    op.create_table(
        "organizations",
        _uuid_pk(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(name="organization_status", create_type=False),
            nullable=False,
            server_default="active",
        ),
        *TIMESTAMP_COLS,
    )

    op.create_table(
        "hr_users",
        _uuid_pk(),
        _org_fk(),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("role", postgresql.ENUM(name="hr_user_role", create_type=False), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(name="hr_user_status", create_type=False),
            nullable=False,
            server_default="invited",
        ),
        *TIMESTAMP_COLS,
        sa.UniqueConstraint("organization_id", "email", name="uq_hr_users_org_email"),
    )

    op.create_table(
        "job_requisitions",
        _uuid_pk(),
        _org_fk(),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("department", sa.Text(), nullable=True),
        sa.Column(
            "owner_hr_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("hr_users.id"), nullable=False
        ),
        sa.Column(
            "status",
            postgresql.ENUM(name="job_requisition_status", create_type=False),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("scorecard_template", postgresql.JSONB(), nullable=False),
        *TIMESTAMP_COLS,
    )

    op.create_table(
        "candidates",
        _uuid_pk(),
        _org_fk(),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(name="candidate_status", create_type=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column("pii_deleted_at", sa.DateTime(timezone=True), nullable=True),
        *TIMESTAMP_COLS,
        sa.UniqueConstraint("organization_id", "email", name="uq_candidates_org_email"),
    )

    op.create_table(
        "resumes",
        _uuid_pk(),
        _org_fk(),
        sa.Column(
            "candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidates.id"), nullable=False
        ),
        sa.Column("file_object_key", sa.Text(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(name="resume_status", create_type=False),
            nullable=False,
            server_default="uploaded",
        ),
        sa.Column("parsed_data", postgresql.JSONB(), nullable=True),
        sa.Column("parse_error", sa.Text(), nullable=True),
        sa.Column(
            "embedding_status",
            postgresql.ENUM(name="embedding_status", create_type=False),
            nullable=False,
            server_default="not_embedded",
        ),
        sa.Column("embedding_error", sa.Text(), nullable=True),
        *TIMESTAMP_COLS,
    )

    op.create_table(
        "applications",
        _uuid_pk(),
        _org_fk(),
        sa.Column(
            "candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidates.id"), nullable=False
        ),
        sa.Column(
            "job_requisition_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("job_requisitions.id"),
            nullable=False,
        ),
        sa.Column(
            "resume_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("resumes.id"), nullable=False
        ),
        sa.Column(
            "status",
            postgresql.ENUM(name="application_status", create_type=False),
            nullable=False,
            server_default="submitted",
        ),
        *TIMESTAMP_COLS,
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_applications_active_candidate_requisition
        ON applications (candidate_id, job_requisition_id)
        WHERE status NOT IN ('rejected', 'withdrawn')
        """
    )

    op.create_table(
        "interviews",
        _uuid_pk(),
        _org_fk(),
        sa.Column(
            "application_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("applications.id"),
            nullable=False,
        ),
        sa.Column(
            "interviewer_hr_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hr_users.id"),
            nullable=False,
        ),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(name="interview_status", create_type=False),
            nullable=False,
            server_default="scheduled",
        ),
        *TIMESTAMP_COLS,
    )

    op.create_table(
        "scorecards",
        _uuid_pk(),
        _org_fk(),
        sa.Column(
            "interview_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("interviews.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("ratings", postgresql.JSONB(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(name="scorecard_status", create_type=False),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        *TIMESTAMP_COLS,
    )

    op.create_table(
        "analysis_outputs",
        _uuid_pk(),
        _org_fk(),
        sa.Column(
            "application_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("match_rationale", sa.Text(), nullable=True),
        sa.Column(
            "source_scorecard_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False
        ),
        sa.Column("crew_run", postgresql.JSONB(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stale", sa.Boolean(), nullable=False, server_default=sa.false()),
        *TIMESTAMP_COLS,
    )

    op.create_table(
        "audit_log",
        _uuid_pk(),
        _org_fk(),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column(
            "actor_hr_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("hr_users.id"), nullable=False
        ),
        sa.Column("diff", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # I2: row-level security, keyed on the SET LOCAL app.current_org_id session
    # variable app/api/deps.py (E2) sets at the start of every org-scoped
    # request/task transaction. FORCE is needed so the policy also applies to
    # the table-owning role the app connects as (RLS is otherwise bypassed by
    # the owner) - see docs/tech-docs for the note on why the dev docker-compose
    # role still bypasses this until a dedicated non-superuser app role exists.
    for table in ORG_SCOPED_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_org_isolation ON {table}
            USING (organization_id = current_setting('app.current_org_id', true)::uuid)
            WITH CHECK (organization_id = current_setting('app.current_org_id', true)::uuid)
            """
        )

    # I3: applications.organization_id must match its candidate's and
    # job_requisition's organization_id. Primary enforcement is
    # application-layer at creation time; this is the DB-layer backstop.
    op.execute(
        """
        CREATE FUNCTION enforce_application_org_consistency() RETURNS TRIGGER AS $$
        DECLARE
            v_candidate_org UUID;
            v_requisition_org UUID;
        BEGIN
            SELECT organization_id INTO v_candidate_org FROM candidates WHERE id = NEW.candidate_id;
            SELECT organization_id INTO v_requisition_org
                FROM job_requisitions WHERE id = NEW.job_requisition_id;
            IF NEW.organization_id IS DISTINCT FROM v_candidate_org
                OR NEW.organization_id IS DISTINCT FROM v_requisition_org THEN
                RAISE EXCEPTION
                    'applications.organization_id must match candidate and job_requisition organization_id (I3)';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_application_org_consistency
        BEFORE INSERT OR UPDATE ON applications
        FOR EACH ROW EXECUTE FUNCTION enforce_application_org_consistency()
        """
    )

    # I4: once a scorecard is submitted, direct UPDATEs are rejected unless
    # issued through amend_scorecard(), which sets a transaction-local flag
    # and writes the audit_log row in the same transaction.
    op.execute(
        """
        CREATE FUNCTION enforce_scorecard_immutability() RETURNS TRIGGER AS $$
        BEGIN
            IF OLD.status = 'submitted'
                AND current_setting('app.allow_scorecard_amend', true) IS DISTINCT FROM 'true' THEN
                RAISE EXCEPTION
                    'scorecards.status=submitted rows are immutable outside amend_scorecard() (I4)';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_scorecard_immutability
        BEFORE UPDATE ON scorecards
        FOR EACH ROW EXECUTE FUNCTION enforce_scorecard_immutability()
        """
    )
    op.execute(
        """
        CREATE FUNCTION amend_scorecard(
            p_scorecard_id UUID, p_ratings JSONB, p_notes TEXT, p_actor_hr_user_id UUID
        ) RETURNS scorecards AS $$
        DECLARE
            v_old scorecards;
            v_new scorecards;
        BEGIN
            SELECT * INTO v_old FROM scorecards WHERE id = p_scorecard_id FOR UPDATE;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'scorecard % not found', p_scorecard_id;
            END IF;

            PERFORM set_config('app.allow_scorecard_amend', 'true', true);
            UPDATE scorecards
                SET ratings = p_ratings, notes = p_notes, status = 'amended', updated_at = now()
                WHERE id = p_scorecard_id
                RETURNING * INTO v_new;
            PERFORM set_config('app.allow_scorecard_amend', 'false', true);

            INSERT INTO audit_log
                (organization_id, entity_type, entity_id, action, actor_hr_user_id, diff, created_at)
            VALUES (
                v_old.organization_id, 'scorecard', p_scorecard_id, 'amended', p_actor_hr_user_id,
                jsonb_build_object('before', to_jsonb(v_old), 'after', to_jsonb(v_new)), now()
            );

            RETURN v_new;
        END;
        $$ LANGUAGE plpgsql
        """
    )

    # audit_log is append-only: no UPDATE/DELETE is ever legitimate, including
    # via a stored procedure - this is the enforcement mechanism itself, not a
    # backstop for one.
    op.execute(
        """
        CREATE FUNCTION reject_audit_log_mutation() RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is append-only; % is not permitted (I4)', TG_OP;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_log_append_only
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION reject_audit_log_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_log_append_only ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS reject_audit_log_mutation()")
    op.execute("DROP FUNCTION IF EXISTS amend_scorecard(UUID, JSONB, TEXT, UUID)")
    op.execute("DROP TRIGGER IF EXISTS trg_scorecard_immutability ON scorecards")
    op.execute("DROP FUNCTION IF EXISTS enforce_scorecard_immutability()")
    op.execute("DROP TRIGGER IF EXISTS trg_application_org_consistency ON applications")
    op.execute("DROP FUNCTION IF EXISTS enforce_application_org_consistency()")

    for table in ORG_SCOPED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_org_isolation ON {table}")

    op.drop_table("audit_log")
    op.drop_table("analysis_outputs")
    op.drop_table("scorecards")
    op.drop_table("interviews")
    op.execute("DROP INDEX IF EXISTS uq_applications_active_candidate_requisition")
    op.drop_table("applications")
    op.drop_table("resumes")
    op.drop_table("candidates")
    op.drop_table("job_requisitions")
    op.drop_table("hr_users")
    op.drop_table("organizations")

    bind = op.get_bind()
    for name, values in reversed(ENUMS):
        postgresql.ENUM(*values, name=name).drop(bind, checkfirst=True)
