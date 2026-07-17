"""Python enums backing the Postgres native ENUM columns in docs/05-data-model.md.

VHIRE-1 (E1). Each class name matches the Postgres enum type name created
in the Alembic migration (see alembic/versions/xxxx_initial_schema.py).
"""

import enum


class OrganizationStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"
    deactivated = "deactivated"


class HRUserRole(str, enum.Enum):
    hr_generalist = "hr_generalist"
    recruiter = "recruiter"
    hiring_manager = "hiring_manager"


class HRUserStatus(str, enum.Enum):
    invited = "invited"
    active = "active"
    deactivated = "deactivated"


class JobRequisitionStatus(str, enum.Enum):
    draft = "draft"
    open = "open"
    on_hold = "on_hold"
    filled = "filled"
    cancelled = "cancelled"


class CandidateStatus(str, enum.Enum):
    active = "active"
    archived = "archived"
    deleted = "deleted"


class ResumeStatus(str, enum.Enum):
    uploaded = "uploaded"
    parsing = "parsing"
    parsed = "parsed"
    parse_failed = "parse_failed"


class EmbeddingStatus(str, enum.Enum):
    not_embedded = "not_embedded"
    embedding = "embedding"
    embedded = "embedded"
    embed_failed = "embed_failed"


class ApplicationStatus(str, enum.Enum):
    submitted = "submitted"
    screening = "screening"
    interviewing = "interviewing"
    offer = "offer"
    hired = "hired"
    rejected = "rejected"
    withdrawn = "withdrawn"


class InterviewStatus(str, enum.Enum):
    scheduled = "scheduled"
    completed = "completed"
    cancelled = "cancelled"
    no_show = "no_show"


class ScorecardStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    amended = "amended"
