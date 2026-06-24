# SDD Progress Ledger — AI Media Watch Backend

Plan: `docs/superpowers/plans/2026-06-24-ai-media-watch-backend.md`
Execution order: 1 → 6, then **17 (dedup)**, then 7 → 13, then **15 → 14** (Task 14 imports Task 15's factory + Task 17 dedup), then 16.
No git (per user). "Checkpoint" = task's tests green. Briefs/reports in scratchpad `sdd/`.

## Status

- [x] Task 1: Project setup + config
- [x] Task 2: Core domain types
- [x] Task 3: JobQueue + InMemoryQueue
- [x] Task 4: BlobStorage + LocalStorage
- [x] Task 5: DB models + session (+ content_hash)
- [ ] Task 4: BlobStorage + LocalStorage
- [ ] Task 5: DB models + session
- [x] Task 6: JobRepository (+ get_job_by_hash, content_hash)
- [x] Task 17: Dedup module (SHA-256 + near-dup seam)
- [x] Task 7: PipelineRegistry
- [x] Task 8: Domain stub pipelines
- [x] Task 9: Extractor
- [ ] Task 10: RiskAggregator
- [ ] Task 11: Orchestrator
- [ ] Task 12: Workers
- [ ] Task 13: Source interface + stub
- [ ] Task 15: Redis queue backend + factory
- [ ] Task 14: API layer + integration test
- [ ] Task 16: Docker, compose, README
- [ ] Final whole-branch review

## Log

- Task 1: complete (config + pyproject; review clean; +`asyncio_default_fixture_loop_scope` to silence pytest-asyncio warning). Minor deferred: `get_settings` lru_cache test isolation (verbatim plan code, acceptable).
- Scope change (user): exact SHA-256 dedup added to intake + near-dup `NearDupIndex` seam. Spec + plan updated; Tasks 4/5/6/14 amended, Task 17 added (runs after Task 6). Briefs regenerated.
- Task 2: complete (domain types base.py/explain.py; haiku impl, sonnet review clean; no Critical/Important).
- Task 3: complete (queue base+memory; review clean). Noted design constraint: each lane is single-mode (intake=FIFO, analysis=priority); don't mix priorities on one lane.
- Task 4: complete (storage base+local incl. delete; review clean). Removed unused `import os` from local.py + plan.
- Task 5: complete (db base/models/session incl. content_hash unique index; review clean). Applied `DateTime(timezone=True)` fix (latent Postgres bug) to file + plan. Re-dispatched once after transient API ConnectionRefused.
- Task 6: complete (JobRepository incl. get_job_by_hash; review clean). Strengthened review_queue test to assert NULL risk sorts last (file + plan).
- Task 17: complete (dedup hashing.py + neardup.py seam; review clean, only style Minors).
- Task 7: complete (PipelineRegistry; review clean). Noted: register() silently overwrites same-name (intended dict semantics; consider ValueError guard for prod).
- Task 8: complete (5 stub pipelines + register_default_pipelines; review clean, deterministic confirmed). Fixed TriageClassifier.explain to return None on empty findings (consistency; file + plan).
- Task 9: complete (Extractor protocol + StubExtractor; controller-reviewed, trivial stub, clean).
- Task 10: complete (RiskAggregator; sonnet review clean). Logic verified by inspection (gambling>pyramid precedence, clamp).
- **Pace change (user: "давай быстрее" + "бесполезные тесты"):** dropped per-task subagent ceremony; implemented Tasks 11,12,13,15,14,16 directly from the plan code. Kept only high-value tests (API/dedup + end-to-end integration); skipped trivial unit tests for orchestrator/workers/sources/factory/redis (covered by integration) per user feedback [[hackathon-speed-over-test-ceremony]].
- Tasks 11 (orchestrator), 12 (workers), 13 (sources), 15 (redis+factory), 14 (API+main+dedup), 16 (docker/compose/README): all implemented directly.
- Fixed FastAPI deprecation: `@app.on_event` → lifespan (pristine output). NOTE: plan doc main.py still shows on_event (minor drift; code is lifespan).
- **FINAL: full suite 40 passed, 0 warnings. `app.main:app` imports, worker entrypoints import. Backend done & verified. Skipped heavy multi-agent final review per user's speed preference; did controller-level verification instead.**

## Deferred Minors (for final whole-branch review)
- Unused imports in tests (e.g. `test_registry.py` imports Finding/JobContext/Unit unused) — F401 sweep across test files.
- Optional: `PipelineRegistry.register` duplicate-name guard (ValueError) for production hardening.
