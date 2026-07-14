# CLAUDE.md

This file logs every prompt given to Claude in this project, along with a summary of the response generated. It is appended to, not rewritten, as the project progresses.

---

## 2026-07-13 — Initial documentation set

**Prompt:**
> You are setting up foundational documentation for a new project: a Resume Collector & Interview Analyzer platform for HR teams across organizations. Before any code is written, generate a complete documentation set in a /docs directory at the project root. [Full spec requested 10 numbered docs (00-ideation through 09-roadmap) plus a docs/README.md index, each with a "Depends on / Feeds into" note, Mermaid diagrams where useful, tables over prose lists, and an "Open Questions" section — covering ideation, scope, assumptions, ontology, invariants, data model, architecture, technical stack, privacy/compliance, and roadmap. Also requested this CLAUDE.md prompt log.]

**Response summary:**
Created `/docs` with 10 numbered documents plus `docs/README.md`, forming a connected documentation chain (each doc's "Depends on / Feeds into" note links to its neighbors):

- **00-ideation.md** — problem framing (HR teams' fragmented resume/interview-feedback workflow), five distinct user JTBDs, non-goals, and six-month success metrics.
- **01-problem-space-and-scope.md** — precise problem statement, in/out-of-scope table, a Scope Creep Watchlist (AI ranking, full ATS replacement, video analysis, sourcing, etc., each with a reactivation condition), and a bounded-context Mermaid diagram.
- **02-assumptions.md** — 15 numbered assumptions across org structure, resume formats, interview data shape, and volume, each with a confidence level and break condition, plus an explicit unvalidated-unknowns list.
- **03-ontology.md** — core entities (Organization, HRUser, JobRequisition, Candidate, Resume, Application, Interview, Scorecard), identity/lifecycle for each, an ER diagram, and what's deliberately not first-class (Offer, Employee, Interviewer-as-entity, etc.).
- **04-invariants.md** — 9 system invariants (cross-org PII isolation, scorecard immutability post-submission, resume-to-candidate ownership, etc.) each with enforcement mechanism and test approach, plus the Application status state diagram.
- **05-data-model.md** — full Postgres schema (9 tables) translating the ontology, with an invariant-enforcement-layer summary table and schema-level ER diagram.
- **06-architecture.md** — component flowchart, an end-to-end sequence diagram (resume submission → lazy on-demand analysis), a sync/async boundary table, and a defense-in-depth multi-tenancy design (app layer + Postgres RLS + namespaced object storage).
- **07-technical-stack.md** — concrete stack (TypeScript/NestJS/Next.js, PostgreSQL, Redis+BullMQ, S3, hosted Claude API for parsing/analysis, managed auth, AWS Fargate/RDS) with a rationale and rejected alternative per layer.
- **08-privacy-and-compliance.md** — PII inventory, retention table, a deletion/anonymization flow diagram implementing the scorecard-immutability-compatible right-to-be-forgotten approach, org-scoped consent flow, and a regimes table (GDPR, India DPDP, US state laws, EEOC recordkeeping) with explicit **[NEEDS LEGAL REVIEW]** flags.
- **09-roadmap.md** — v1/v2/v3 phase table mapped to the scope doc, exit criteria between phases, and a Gantt timeline.
- **docs/README.md** — reading-order index with one-line summaries and a Mermaid dependency graph of all 10 docs.

All Mermaid diagrams (flowchart, sequence, ER, state, Gantt) were written and are syntactically valid. Every document ends with an Open Questions section flagging genuinely unresolved decisions rather than restating settled content.

No code was written in this session — documentation only, as requested.

---

## 2026-07-13 — Push initial documentation set to GitHub

**Prompt:**
> push this local repo to the remote - https://github.com/bc0de0/virtual_hire.git. This is a first time push and will require a git init action. Also, ensure meaningful commit messages and manage a changelog.

**Response summary:**
Initialized git (no identity was configured on the machine, so set it locally to `Kunal Gupte <kunal@revorion.ai>` for this repo only), added a Node/TypeScript-oriented `.gitignore` and a `CHANGELOG.md` (Keep a Changelog format), committed all 14 existing files with a descriptive message, renamed the default branch to `main`, added the `origin` remote, and pushed with `-u` to establish tracking. Confirmed with the user before the push since it was the first write to a shared remote.

---

## 2026-07-14 — Redo architecture and tech stack for RAG + multi-model LLM crew (Python backend)

**Prompt:**
> rethink the architecture and techstack keeping in mind the following parameters - we need a seperate backend, a RAG based vector DB and querying support for resume search and retrival and matching also we will need a multi model LLM crew for tasks like summarizer and reasoning. Python is a natural candidate for this tasks. Redo all revelant documents with this parameters in mind

**Response summary:**
Re-read all 10 docs plus the README, then revised every document the new requirements actually touch rather than only the two stack docs, since a backend-language and architecture change ripples through scope, assumptions, ontology, invariants, and the schema:

- **06-architecture.md** — full rewrite: frontend and backend are now separate deployables (Next.js talking only to a Python backend's API); added an Ingestion → Extraction Agent → Embedding Worker pipeline; added a dedicated RAG search sequence diagram (embed query → org-scoped vector search → Reasoning Agent rationale — deliberately retrieval-first so cross-org data can never reach the LLM call); extended the multi-tenancy section to cover the vector index and explicitly explained why pgvector-in-Postgres was chosen over a dedicated vector database (avoids a second tenant-isolation surface).
- **07-technical-stack.md** — full rewrite: Python 3.12 + FastAPI backend, PostgreSQL + `pgvector`, Voyage AI embeddings, CrewAI for multi-agent orchestration, and a fixed per-task model assignment (Claude Haiku 4.5 for extraction, Sonnet 5 for summarization, Opus 4.8 for reasoning/matching) — each choice with a rejected alternative (LangGraph, dedicated vector DB, self-hosted embeddings, Django).
- **01-problem-space-and-scope.md** — added RAG search/retrieval as an in-scope row; sharpened the "AI-based candidate ranking" Scope Creep Watchlist entry to draw an explicit line between the now-in-scope HR-initiated, query-scoped, advisory search feature and the still-out-of-scope autonomous/background ranking that gates decisions; updated the bounded-context diagram to show the LLM crew and vector index inside the boundary with the hosted AI providers as external.
- **02-assumptions.md** — added assumptions A16–A20 on embedding quality, multi-step crew latency, search query volume, fixed shared-model sufficiency, and third-party PII exposure to the AI providers.
- **03-ontology.md** — added `ResumeChunk/Embedding` and `AnalysisOutput` to the "not first-class" list as derived/regenerable artifacts (same treatment as `parsed_data`), consistent with the doc's existing anti-over-modeling stance.
- **04-invariants.md** — extended I2's description to explicitly cover the vector table, and added I10 (AnalysisOutput may only be generated from submitted, not draft, Scorecards) and I11 (RAG search/match results are always org-scoped, retrieval-filtered before any LLM reasoning call).
- **05-data-model.md** — added `resume_chunks` (pgvector column, HNSW index, org-scoped RLS) and `analysis_outputs` (summary, match rationale, `source_scorecard_ids` for I10 auditability, `crew_run` recording which model handled each agent role) tables; updated the ER diagram and the invariant-enforcement summary table.
- **08-privacy-and-compliance.md** — added embeddings and LLM crew output to the PII inventory; added a new subprocessors section naming Anthropic and Voyage AI with a **[NEEDS LEGAL REVIEW]** flag for DPAs; updated the deletion flow to hard-delete `resume_chunks`/`analysis_outputs` (rather than anonymize, since they exist only to serve search/summarization); updated the candidate consent notice text to disclose AI processing.
- **09-roadmap.md** — moved RAG search and the LLM crew into v1's ship list (no longer deferred); updated the v1→v2 exit criteria to require the I11 test suite and AI-subprocessor DPAs; updated the Gantt chart with embedding-pipeline and crew-build phases.
- **00-ideation.md** and **docs/README.md** — smaller consistency edits (non-goal boundary clarification, a new search-adoption success metric, updated doc summaries).
- **.gitignore** — extended to cover Python backend artifacts (`.venv/`, `__pycache__/`, Celery) alongside the existing Node/Next.js entries.
- **CHANGELOG.md** — added a `### Changed` entry under `[Unreleased]` documenting the pivot and every file it touched.

Every changed document's Open Questions section was updated to reflect genuinely new unresolved decisions introduced by this pivot (e.g., whether RAG should ship as a v1 fast-follow instead of a pilot-blocking dependency, embedding-dimension migration risk, cross-border transfer questions for the new AI subprocessors) rather than being left stale.
