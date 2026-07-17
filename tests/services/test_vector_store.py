"""Tests for app.services.vector_store's collection-naming convention
(VHIRE-2 / E2). See docs/05-data-model.md's "Vector store (Qdrant)" section.
"""

import uuid

from app.services.vector_store import collection_name_for_org


def test_collection_name_is_deterministic_from_org_id():
    org_id = uuid.uuid4()

    assert collection_name_for_org(org_id) == f"resumechunks_{org_id}"


def test_collection_name_differs_per_organization():
    assert collection_name_for_org(uuid.uuid4()) != collection_name_for_org(uuid.uuid4())
