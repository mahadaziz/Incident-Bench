# Architecture

incident-bench is an on-call incident investigator plus a benchmark that scores it. This
file covers how the pieces fit and, more importantly, how each one fails.

## Components

| Component | Language | Owns | Status |
|---|---|---|---|
| `agent/scenarios/` | Python | Scenario schema, validation, loader, `agent_view()` | Built (step 1) |
| `agent/` scorer and eval harness | Python | Scoring, `make eval`, run logs in `results/` | Step 2 |
| `agent/` runtime | Python | `POST /investigate`, one step per call | Step 4 |
| `control-plane/` | Go | Ingest, dedupe, queue, workers, retries, checkpoints | `/healthz` only (step 1) |
| Postgres + pgvector, Redis 7 | — | Jobs, checkpoints, reports, RAG; queue | Compose only (step 1) |

```
scenario JSON ──load_dir──► Scenario ──agent_view()──► AgentView ──► agent
                               │                                       │
                               └──── ground truth ───► scorer ◄─ report┘
```

The agent only ever receives an `AgentView`. That's a separate type holding the alert,
evidence, and budget, and nothing else. It's built field by field (an allowlist), so a
field added to `Scenario` later stays hidden unless someone adds it on purpose. Ground
truth goes only to the scorer.

The dev/test split is defined by directory (`agent/scenarios/data/<split>/`), not by a
field in the file. That way a split change shows up as a git file move, and the test
directory can be blocked from reads.

## Failure modes

Each row names the test that proves the handling. A row with no test isn't handled yet.

| Failure | What would go wrong | Handling | Test |
|---|---|---|---|
| Two pieces of evidence share an ID | A citation could resolve to the wrong item, so citation validity means nothing | Scenario validation rejects it | `test_schema.py::test_rejects_duplicate_id_within_kind` |
| Ground truth references an ID that isn't in the evidence | Required-evidence recall can never reach 100%, or a distractor penalty never fires | Validation rejects unknown IDs in `required_evidence` and `distractors` | `test_schema.py::test_rejects_unknown_required_evidence`, `::test_rejects_unknown_distractor` |
| An ID is both required and a distractor | Citing it both rewards and penalises; the score is contradictory | Validation rejects the overlap | `test_schema.py::test_rejects_id_both_required_and_distractor` |
| Descriptive evidence ID (`log-cert-expired`) | The ID leaks the answer to the agent | IDs must match `<kind>-<digits>`, and the prefix must match the evidence kind | `test_schema.py::test_rejects_malformed_evidence_id` |
| Typo in a field name (`distractor`) | Field silently dropped; scenario scores easier than intended | `extra="forbid"` on every model | `test_schema.py::test_rejects_unknown_field` |
| Timestamp without a time zone | Event order is ambiguous, and event order is how a root cause is found | `AwareDatetime` on every timestamp | `test_schema.py::test_rejects_naive_timestamp` |
| Same scenario id in two files (e.g. dev and test) | One silently overwrites the other; the scenario set and its hash are wrong | Loader rejects duplicate ids across directories | `test_loader.py::test_rejects_duplicate_id_across_directories` |
| Filename doesn't match scenario id | Two files could claim the same id; audit trail confusing | Loader rejects the mismatch | `test_loader.py::test_rejects_filename_not_matching_id` |
| Stray or misnamed file in a scenario directory | Scenario silently missing from the set | Loader rejects any non-hidden entry that isn't a `.json` file | `test_loader.py::test_rejects_non_scenario_entries` |
| Empty or missing scenario directory | Eval "passes" on zero scenarios | Loader raises | `test_loader.py::test_rejects_empty_directory`, `::test_rejects_missing_directory` |
| Ground truth, id, title, tags, difficulty, or source reaches the agent | Benchmark measures leakage, not investigation | `AgentView` has no such fields; leak check on fixture and every seed | `test_agent_view.py::test_agent_view_fields_are_exactly_the_allowlist`, `::test_agent_view_leaks_nothing_hidden`, `::test_seed_agent_view_leaks_nothing_hidden` |
