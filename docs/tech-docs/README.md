# Tech Docs

**Purpose:** Implementation-level reference for the backend code actually
in the repo — what exists, where it lives, how it maps to the product
docs (`docs/00`–`09`) and [EPIC.md](../../EPIC.md), and what a future
contributor (human or Claude) needs to know before touching it. This is
distinct from `docs/00`–`09`, which describe the *product/architecture
design* independent of implementation, and stays close to the code: when
an epic's implementation changes materially, its tech-doc should be
updated in the same change, not left to drift.

**Depends on:** [EPIC.md](../../EPIC.md) (epic scope/DoD each doc reports
against) and the numbered docs each epic implements.
**Feeds into:** Nothing upstream — this is the leaf of the doc chain,
written for whoever is extending the code next.

One doc per epic (or tightly-related epic pair, when they shipped in the
same chunk), added as each chunk of [EPIC.md](../../EPIC.md) is
implemented.

| Doc | Epics | Summary |
|---|---|---|
| [e1-e2-data-layer-and-auth.md](e1-e2-data-layer-and-auth.md) | E1, E2 | Postgres schema, Alembic migration, DB-layer invariant enforcement (RLS/triggers), JWT auth, org-scoped request context, Qdrant collection naming, candidate magic-link auth. |

## Conventions

- Each doc states, up front: what was built, the file map, which
  invariants it enforces and how, how to run/verify it locally, and any
  known gaps or follow-up work carried into a later epic.
- Diagrams use Mermaid where they clarify a flow the prose alone
  wouldn't (matches the convention in `docs/00`–`09`).
- These docs assume the reader has already skimmed the relevant
  `docs/0X-*.md` files and [EPIC.md](../../EPIC.md) — they don't restate
  product rationale, only implementation detail.
