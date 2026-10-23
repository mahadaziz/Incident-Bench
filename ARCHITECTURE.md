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

The agent only ever receives an `AgentView`. That's a separate type holding the alert and
evidence, and nothing else. The view is built field by field (an allowlist), so a field
added to `Scenario` later stays hidden unless someone adds it on purpose. Ground truth goes
only to the scorer.

The budget stays out of the view too: it scales with difficulty, so showing it would leak
difficulty. The runtime enforces it instead.

The dev/test split is defined by directory (`agent/scenarios/data/<split>/`), not by a
field in the file. That way a split change shows up as a git file move, and the test
directory can be blocked from reads.

Each scenario has exactly one `root_cause` label. When an incident fits more than one
category, the label is the earliest link in the causal chain that, if removed, would have
prevented the incident. A slow payments provider that exhausts a connection pool is
`dependency_slowdown`, not `resource_exhaustion`; a renamed env var exposed by a routine
deploy is `config_error`, not `bad_deploy`. Writing the rule down keeps the root-cause
metric from being a judgment call per scenario, and the step-2 prompt should state it.

## Failure modes

Each row names the test that proves the handling. A row with no test isn't handled yet.

| Failure | What would go wrong | Handling | Test |
|---|---|---|---|
| Two pieces of evidence share an ID | A citation could resolve to the wrong item, so citation validity means nothing | Scenario validation rejects it | `test_schema.py::test_rejects_duplicate_id_within_kind` |
| Ground truth references an ID that isn't in the evidence | Required-evidence recall can never reach 100%, or a distractor penalty never fires | Validation rejects unknown IDs in `required_evidence` and `distractors` | `test_schema.py::test_rejects_unknown_required_evidence`, `::test_rejects_unknown_distractor` |
| One fact is provable by several IDs (a log line and a metric for the same pool exhaustion) | Recall penalises an agent for citing the "other" proof | `required_evidence` is a list of groups, one per fact; citing any ID in a group covers it. Empty groups are rejected | `test_schema.py::test_accepts_alternative_ids_within_a_group`, `::test_rejects_empty_evidence_group` |
| A red herring appears under several IDs (a deploy record and its rollout log) but only one is a distractor | An agent blames the red herring and dodges the penalty by citing its twin | Authoring rule: list every ID of every red herring in `distractors`. Not machine-checkable; reviewed per scenario | — |
| An ID is both required and a distractor | Citing it both rewards and penalises; the score is contradictory | Validation rejects the overlap | `test_schema.py::test_rejects_id_both_required_and_distractor` |
| Descriptive or look-alike evidence ID (`log-cert-expired`, non-ASCII digits) | The ID leaks the answer, or looks like an ID the agent can never cite back | IDs must match `<kind>-<number>` with ASCII digits and one spelling per number (3 digits, or more with no leading zero, so `log-001` and `log-0001` can't coexist), and the prefix must match the evidence kind | `test_schema.py::test_rejects_malformed_evidence_id` |
| Typo in a field name (`distractor`) | Field silently dropped; scenario scores easier than intended | `extra="forbid"` on every model | `test_schema.py::test_rejects_unknown_field` |
| Same JSON key twice in a scenario file | The parser keeps the last value, so a stray `"distractors": []` silently empties ground truth | Loader parses with a hook that rejects duplicate keys | `test_loader.py::test_rejects_duplicate_json_keys` |
| NaN or Infinity in a metric | Loads fine but reaches the agent as `null`, so the agent sees different data than the file holds | `allow_inf_nan=False` on metric values | `test_schema.py::test_rejects_non_finite_metric_value` |
| Wrong JSON type (`"difficulty": true`, `"max_steps": "10"`) | Lax parsing coerces it, so a typo in ground truth loads silently | Strict validation; JSON-mode parsing still reads ISO datetimes and enum values | `test_schema.py::test_rejects_wrong_json_type_instead_of_coercing` |
| Blank text (`"summary": "   "`) | Scoring compares against an empty target | Every text field must contain a non-space character | `test_schema.py::test_rejects_blank_text` |
| Scenario with no distractors | Scores easier than intended; breaks core rule 4 | `distractors` needs at least one ID | `test_schema.py::test_rejects_missing_distractors` |
| Service name with a stray space or capital (`'Order-Service '`) | Exact-name tool lookups can never reach that evidence | Every service field must be a lowercase slug | `test_schema.py::test_rejects_non_slug_service_name` |
| Metric name with a stray space or capital (`"CPU_Utilization "`) | An exact-name metrics query can never return it, so a required metric can't be cited | Metric names must be lowercase `snake_case` | `test_schema.py::test_rejects_non_snake_case_metric_name` |
| Config key with stray spaces (`" DATABASE_URL"`) | The evidence quietly says something else, and key lookups miss it | Keys must be non-blank with no surrounding whitespace | `test_schema.py::test_rejects_untrimmed_config_key` |
| `affected_service` typo | Every affected-service match fails for that scenario | Must name the alert's service or a service in the evidence | `test_schema.py::test_rejects_unknown_affected_service` |
| Timestamp without a time zone, or with a non-UTC offset | Event order is ambiguous or misread (sorting timestamp text puts `+05:00` hours off), and event order is how a root cause is found | Every timestamp must be timezone-aware and UTC | `test_schema.py::test_rejects_naive_timestamp`, `::test_rejects_non_utc_timestamp` |
| Same scenario id in two files (e.g. dev and test) | One silently overwrites the other; the scenario set and its hash are wrong | Loader rejects duplicate ids across directories | `test_loader.py::test_rejects_duplicate_id_across_directories` |
| Filename doesn't match scenario id | Two files could claim the same id; audit trail confusing | Loader rejects the mismatch | `test_loader.py::test_rejects_filename_not_matching_id` |
| Stray or misnamed file in a scenario directory | Scenario silently missing from the set | Loader rejects any entry that isn't a `.json` file (hidden non-JSON files like `.gitkeep` are skipped; hidden `.json` files are not) | `test_loader.py::test_rejects_non_scenario_entries`, `::test_rejects_hidden_json_file` |
| Unreadable scenario file | Raw OS error escapes; callers can't tell which scenario broke | Loader wraps it as `ScenarioLoadError` naming the file | `test_loader.py::test_wraps_read_errors_naming_the_file` |
| Empty or missing scenario directory | Eval "passes" on zero scenarios | Loader raises | `test_loader.py::test_rejects_empty_directory`, `::test_rejects_missing_directory` |
| Ground truth, id, title, tags, difficulty (directly or via budget), or source reaches the agent | Benchmark measures leakage, not investigation | Structural guarantee: `AgentView` has no such fields, so they cannot be serialised to the agent. Backstop only: a whole-string check that the id, title, summary, remediations, root cause and tags never appear verbatim (it cannot catch a paraphrase or fragment written into evidence text, which is an authoring rule) on the fixture (including tags) and on every dev scenario (including tags, except an explicit list of plain words like `tls` that legitimately appear in evidence); the view is a deep copy, so the agent can't mutate the scorer's copy | `test_agent_view.py::test_agent_view_fields_are_exactly_the_allowlist`, `::test_agent_view_leaks_nothing_hidden`, `::test_seed_agent_view_leaks_nothing_hidden`, `::test_agent_view_shares_no_mutable_state` |
| Required evidence clusters at low IDs (causes precede symptoms, and IDs follow the timeline) | An agent learns "cite the earliest logs" instead of investigating | Planned: renumber the seeds as a ground-truth commit before the step-2 baseline is logged (the cert seed's causes are `log-001`/`log-002`), and assign IDs in shuffled order when authoring step-3 scenarios | — |
| Strict models reject a parsed dict at an HTTP boundary (FastAPI hands over dicts) | Every valid `/investigate` request fails with 422 | Planned, step 4: validate request bodies as raw JSON or relax strictness on boundary models, with a round-trip test | — |
| A harness loads splits separately or together and loses either the cross-split duplicate check or the dev/test label | Dev scores mix into headline test numbers, or one scenario counts in both splits | Planned, step 2/3: one loader call that returns scenarios keyed by split and still rejects ids shared across splits | — |
| A scenario budget typo (`"max_tokens": 8000000`) | One scenario burns ~100x its intended tokens on every eval run | Planned, step 4: a global hard cap in the runtime that per-scenario budgets can't exceed | — |
| Two metric series share a service and name | An exact-match metrics query can't return one of them, so it can never be cited | Planned, step 4: decide the metric lookup key, then validate uniqueness on it | — |
| Harness or scorer code mutates a loaded scenario's config values in place | Scores computed against evidence the agent never saw | Known limit: `frozen` is shallow, and `ConfigSnapshot.values` is a dict (so scenarios are also unhashable; key them by `id`). The agent gets a deep copy; harness code must treat scenarios as read-only. A read-only mapping would break the deep copy, so it isn't used | `test_agent_view.py::test_agent_view_shares_no_mutable_state` (agent side only) |
