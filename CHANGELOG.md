# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Changed
- **Backend stack pivoted from TypeScript/NestJS to Python/FastAPI**, and the architecture was redrawn around a RAG-based vector search pipeline (PostgreSQL + `pgvector`, Voyage AI embeddings) and a multi-model LLM crew (CrewAI: Claude Haiku for extraction, Sonnet for summarization, Opus for candidate-requisition matching/reasoning). Affects [docs/06-architecture.md](docs/06-architecture.md) and [docs/07-technical-stack.md](docs/07-technical-stack.md) (full rewrites), with ripple updates to [docs/01-problem-space-and-scope.md](docs/01-problem-space-and-scope.md) (in-scope table, Scope Creep Watchlist boundary, bounded context diagram), [docs/02-assumptions.md](docs/02-assumptions.md) (new RAG/crew assumptions A16–A20), [docs/03-ontology.md](docs/03-ontology.md) (derived AnalysisOutput/ResumeChunk artifacts), [docs/04-invariants.md](docs/04-invariants.md) (new I10/I11 extending tenant isolation to the vector index), [docs/05-data-model.md](docs/05-data-model.md) (new `resume_chunks` and `analysis_outputs` tables), [docs/08-privacy-and-compliance.md](docs/08-privacy-and-compliance.md) (embeddings as PII, third-party AI subprocessors, updated deletion flow), [docs/09-roadmap.md](docs/09-roadmap.md) (v1 now ships RAG search, updated Gantt), and [docs/README.md](docs/README.md).
- `.gitignore` extended to cover the Python backend (`__pycache__/`, `.venv/`, Celery artifacts) alongside the existing Node/Next.js frontend entries.

### Added
- Initial foundational documentation set in `/docs` (10 numbered documents + index), covering ideation, problem scope, assumptions, ontology, invariants, data model, architecture, technical stack, privacy/compliance, and roadmap for the Resume Collector & Interview Analyzer platform.
- `CLAUDE.md` prompt log recording prompts given to Claude and summaries of the resulting work.
- `.gitignore` for the Node/TypeScript stack chosen in [docs/07-technical-stack.md](docs/07-technical-stack.md).
