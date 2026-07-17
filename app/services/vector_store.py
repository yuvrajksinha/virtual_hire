"""Qdrant collection-naming convention. See the "Vector store (Qdrant)"
section of docs/05-data-model.md: one collection per Organization, named
deterministically from the org's UUID and resolved server-side from the
authenticated session's org context — never a client-supplied parameter
(I11).

VHIRE-2 (E2) adds only the naming helper, since app.api.deps needs it to
build the second half of the request-scoped context (Postgres RLS +
Qdrant collection). E7 owns the actual Qdrant client wrapper (collection
provisioning, point upsert/search) — centralizing both here is what lets
a future embedding-model/dimension migration stay a one-file change, per
EPIC.md's cross-cutting risks.
"""

import uuid

_COLLECTION_PREFIX = "resumechunks_"


def collection_name_for_org(organization_id: uuid.UUID) -> str:
    """Return the deterministic Qdrant collection name for `organization_id`."""
    return f"{_COLLECTION_PREFIX}{organization_id}"
