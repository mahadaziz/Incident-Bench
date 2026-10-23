# Step 1: repo skeleton, scenario schema, CI

Branch: `step-1-skeleton`. The first commit saves this plan as `docs/plans/step-1-skeleton.md`.

## Like I'm five

Before you run a spelling bee, you need two things. First, a classroom: desks, a
whiteboard, and a bell that rings when something's wrong. Second, the official word cards,
each with the right spelling on the back where the kids can't see it.

- **The classroom** is the repo skeleton. It has folders for the Go side and the Python
  side, a `Makefile` (one remote control: `make test` runs every test), Docker Compose
  (starts the database and Redis with one command), and CI. CI is a robot on GitHub that
  runs lint and tests on every push, so a broken change can't slip in unnoticed.
- **The word cards** are the scenarios. Each one is a made-up (later, real) incident:
  an alert, logs, metrics, deploys, and configs. The answer sits on the back (the
  *ground truth*). The **schema** is the rule for what a valid card looks like. The
  **validator** throws out bad cards, for example a card whose answer points at a log
  line that doesn't exist.
- **`agent_view()`** is the front of the card: everything except the answer. The agent
  only ever gets the front.

Nothing in this step calls an LLM. It's all foundation.

## Diagrams

How the pieces connect after step 1:

```
                    make (Git Bash on Windows, bash on Linux)
        ┌──────────────┬───────────────┬──────────────┬──────────────┐
      setup          test            lint            up/down
        │        ┌─────┴─────┐    ┌─────┴─────┐          │
        ▼        ▼           ▼    ▼           ▼          ▼
   uv sync /  pytest     go test  ruff      gofmt -l  docker compose
   go mod     (agent/)    -race   check +   go vet    ├─ postgres+pgvector 0.8.1-pg17
   download              (control- format              └─ redis 7.4.6
                           plane/)  --check

   GitHub push ──► Actions (ubuntu) ──► make setup ─► make lint ─► make test
```

How a scenario file becomes something the agent can see:

```
 agent/scenarios/data/dev/<id>.json
            │  load_dir(path)
            ▼
 ┌────────────────────────── Scenario (pydantic, extra=forbid) ─────────────────┐
 │ id, title, source, difficulty, tags          ◄── hidden from the agent       │
 │ alert, logs[], metrics[], deploys[], configs[], budget                       │
 │ ground_truth: root_cause, summary, required_evidence[], distractors[], ...   │
 └──────────────────────────────────────────────────────────────────────────────┘
            │ validators: ID format per kind, IDs unique, ground truth IDs exist,
            │ required ∩ distractors = ∅, required non-empty, aware timestamps,
            │ loader: filename == id, no duplicate scenario ids across files
            ▼
       scenario.agent_view()  ── built by ALLOWLIST (copy named fields in)
            ▼
 ┌──────── AgentView (separate type) ────────┐
 │ alert, logs, metrics, deploys,            │   ← no field exists for ground truth,
 │ configs, budget                           │     so it can't leak by accident
 └───────────────────────────────────────────┘
```

Before/after: before, the repo has only `CLAUDE.md`. After:

```
.gitattributes  .gitignore  .env.example  Makefile  docker-compose.yml  ARCHITECTURE.md
.github/workflows/ci.yml
docs/plans/step-1-skeleton.md
control-plane/  go.mod  cmd/control-plane/main.go  internal/health/{health.go,health_test.go}
agent/          pyproject.toml  uv.lock  .python-version
                scenarios/{__init__,schema,loader}.py
                scenarios/data/dev/{3 seed scenarios}.json
                tests/{test_schema,test_agent_view,test_loader,test_seed_scenarios}.py
```

## The real plan

### Decisions (already confirmed with you)
- Deps: `pydantic` (runtime); `pytest` and `ruff` (dev group). Go: stdlib only, so there
  are no deps and Go generates no `go.sum` yet. I'll commit one as soon as a Go dependency
  exists.
- Scenario files are JSON, one per file, named `<scenario-id>.json`.
- ARCHITECTURE.md starts now, with a failure-mode table seeded by the loader's
  rejection cases.
- Go gets a tiny `/healthz` server with a table-driven test.

### Files
- **`.gitattributes`**: `* text=auto eol=lf`. On Windows, git can turn line endings into
  CRLF, and CRLF breaks Makefile recipes, shell scripts, and gofmt.
- **`.gitignore`**: `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`,
  `agent/.scratch/` (where debug runs will go later). **Never `results/`.**
- **`.env.example`**: Postgres user, password, and db names with dev defaults. `.env`
  stays gitignored.
- **`docker-compose.yml`**: `pgvector/pgvector:0.8.1-pg17` and `redis:7.4.6` (I already
  checked that both tags exist), each with a healthcheck, ports bound to `127.0.0.1`,
  and a named volume for Postgres.
- **`Makefile`**:
  - `SHELL` follows the rule in CLAUDE.md: under `ifeq ($(OS),Windows_NT)` it's
    `C:/PROGRA~1/Git/bin/bash.exe`, otherwise `bash`, with
    `.SHELLFLAGS := -eu -o pipefail -c`.
  - Targets: `setup` (checks for `uv` and prints how to install it if missing), `test`,
    `test-py`, `test-go` (with `-race`), `lint`, `fmt`, `up`, `down`.
  - `lint` runs `ruff check`, `ruff format --check`, `test -z "$(gofmt -l .)"` (plain
    `gofmt -l` always exits 0, so on its own it can't fail the build), and `go vet ./...`.
  - No `eval` target until step 2.
- **`.github/workflows/ci.yml`**: runs on every push and PR, on `ubuntu-latest`. It uses
  `actions/checkout@v4`, `actions/setup-go@v5` (with `go-version-file`), and
  `astral-sh/setup-uv@v6` (pinned to uv 0.13.5), then runs `make setup lint test`.
- **`control-plane/`**: module `github.com/mahadaziz/incident-bench/control-plane`,
  `go 1.24`.
  - `internal/health` has a `Handler()` that answers `GET /healthz` with 200 and `ok`,
    and anything else with 405.
  - `cmd/control-plane/main.go` wires the handler up with `http.Server` timeouts and
    shuts down cleanly on SIGINT.
- **`agent/pyproject.toml`**:
  - `requires-python = ">=3.12,<3.13"`, and `.python-version` is `3.12`.
  - uv `package = false` (flat layout). pytest uses `pythonpath = ["."]` and
    `testpaths = ["tests"]`.
  - ruff: line length 100, rules `E,F,I,B,UP`.
- **`agent/scenarios/schema.py`**:
  - Every model uses `ConfigDict(extra="forbid", frozen=True)`, so a typo in a field
    name is an error instead of being silently dropped. `frozen` means a loaded scenario
    can't be changed by mistake.
  - Enums: `Source` (real, synthetic) and `RootCause` (the 8 values in CLAUDE.md).
  - Evidence:
    - `LogLine`: id `log-NNN`, timestamp, service, level, message.
    - `MetricSeries`: id `met-NNN`, name, service, unit, and points of (timestamp, value).
    - `Deploy`: id `dep-NNN`, service, version, timestamp, author, description.
    - `ConfigSnapshot`: id `cfg-NNN`, service, captured_at, `values: dict[str, str]`.
  - `Alert`: name, service, severity, fired_at, summary. No ID: the alert is the
    starting point, not evidence.
  - `GroundTruth` and `Budget` (`max_steps`, `max_tokens`, both > 0). `Scenario` has
    difficulty 1–3, a kebab-case `id`, and `AwareDatetime` timestamps, so a timestamp
    without a time zone is rejected.
  - A `model_validator` on `Scenario` checks four things: evidence IDs are unique across
    all evidence kinds, every `required_evidence` and `distractors` ID exists,
    `required_evidence` isn't empty, and no ID is both required and a distractor.
  - The error message names the scenario and the bad ID.
- **`AgentView` + `Scenario.agent_view()`**: `AgentView` is its own model with only
  alert, logs, metrics, deploys, configs, and budget. `agent_view()` builds it by naming
  those fields one by one (an allowlist), never by copying the scenario and deleting
  the answer fields (a denylist).
- **`agent/scenarios/loader.py`**: `load_dir(path) -> list[Scenario]` loads every
  `*.json` file, sorted. It raises an error that names the file if a file doesn't parse,
  if a filename doesn't match its scenario `id`, or if two files share an id. The
  dev/test split comes from which directory a file is in, not from a field in the file.
  This step creates only `data/dev/`; the split gets assigned in step 3.
- **Seed scenarios** in `agent/scenarios/data/dev/`, as in CLAUDE.md:
  1. Renamed env var after a deploy (difficulty 1, `config_error`).
  2. Connection pool exhausted by a slow payments gateway (difficulty 2,
     `dependency_slowdown`).
  3. Cert expiry from a broken renewal after an IAM change, with a red-herring deploy
     and a CPU spike as distractors (difficulty 3, `cert_expiry`).

  Evidence IDs are opaque and numbered, never descriptive, so an ID can't give away the
  answer. Required evidence is spread through each list instead of always being
  `log-001`. **These files are ground truth, so I'll draft them and you review them line
  by line in the PR.**
- **`ARCHITECTURE.md`**: a short component overview plus the failure-mode table. Columns:
  failure, what happens, how it's handled, the test that proves it. Starting rows:
  - duplicate evidence ID
  - ground truth points at an unknown ID
  - an ID is both required and a distractor
  - duplicate scenario id or filename mismatch
  - unknown field or typo
  - a timestamp with no time zone
  - ground truth leaking into the agent's input
- **`CLAUDE.md`** updates:
  - Drop "(planned)" from Commands and mark `make eval` as step 2.
  - Cut the schema section down to a pointer to `schema.py`.
  - Update the Current status line once the step is done.

### Tests (all offline; no LLM)
- `test_schema.py` builds a valid scenario as a fixture, then checks that each of these
  is rejected:
  - a duplicate ID within one kind
  - a duplicate ID across two kinds
  - `required_evidence` pointing at an unknown ID
  - `distractors` pointing at an unknown ID
  - an ID in both lists
  - an empty `required_evidence`
  - a wrong ID prefix (a log with id `dep-001`)
  - an unknown field
  - difficulty 0 or 4
  - a naive timestamp
  - an unknown `root_cause`
- `test_agent_view.py`:
  - `AgentView`'s field set is exactly the allowlist.
  - The serialized agent view doesn't contain the scenario's id, title, tags,
    ground-truth summary, or remediations.
  - Evidence is passed through unchanged.
- `test_loader.py` uses `tmp_path` to check: two files with the same id are rejected, a
  filename that doesn't match its id is rejected, malformed JSON is rejected with the
  filename in the message, and the result is sorted the same way every time.
- `test_seed_scenarios.py` checks that the dev directory loads exactly 3 scenarios, one
  per difficulty, with the expected root causes.
- Go: a table-driven `health_test.go` using `httptest` (GET returns 200, POST returns
  405).

### Commits, in order (`make test` before each one once the Makefile exists)
1. `docs: add step 1 plan`
2. `chore: add gitignore and gitattributes`
3. `feat(control-plane): add healthz server with test`
4. `chore(agent): init uv project with pydantic, pytest, ruff`
5. `chore(infra): add makefile with setup, test, lint, fmt targets`
6. `feat(scenarios): add pydantic scenario schema with id validation`
7. `feat(scenarios): add allowlisted agent view`
8. `feat(scenarios): add directory loader`
9. `feat(scenarios): add three seed scenarios`
10. `chore(infra): pin postgres and redis images in compose` (adds `up`/`down`)
11. `chore(infra): add github actions ci for lint and test`
12. `docs: add architecture overview and failure-mode table`
13. `docs: point schema section of CLAUDE.md at schema.py` (also drops the Commands
    "planned" marker)
14. `docs: mark step 1 done in CLAUDE.md` (only after the definition of done is shown)

### Review loop
Run `/code-review high` on the diff against main. `high` is the right level because the
schema and agent view protect eval integrity, but this step has no concurrency, queue,
or scorer, which are the things that call for `max`. I'll also check the diff against
Core design rules, Eval integrity, and Rules, then fix, run `make test`, and review again,
up to 3 rounds.

### How the definition of done gets shown
- I'll paste the output of `make lint` and `make test` from Windows. Go runs with
  `-race`, and the results include the seed scenarios test.
- I'll show `make up` with both containers healthy, then `make down`.
- I'll push, open a PR, and link the green Actions run.
- Then I stop, summarize each review round, and wait for your merge approval. The merge
  will be a merge commit, not a squash.

## Interview points
- **"The agent's input is a separate type built from an allowlist."** If I copied the
  scenario and deleted the answer fields, adding a new secret field later would leak it
  by default. With an allowlist, a new field stays hidden until someone deliberately adds
  it. Fail closed, not open.
- **"Bad data fails at load time, not at scoring time."** If ground truth points at a
  log line that doesn't exist, every score for that scenario is quietly wrong. The loader
  rejects it, so a broken scenario can't produce a number.
- **"Evidence IDs are opaque."** `log-007` says nothing. `log-cert-expired` would hand
  the agent the answer. The same goes for scenario titles and ids, which is why the agent
  view strips them.
- **"`extra=forbid` and time-zone-aware timestamps."** A typo like `distractor` instead
  of `distractors` would otherwise be silently dropped, so the scenario would have no
  distractors and score easier. Timestamps without a time zone make it ambiguous which
  event came first, and the order of events is how you find a root cause.
- **"The split is a directory, not a field."** Moving a scenario between dev and test
  shows up in git as a file move anyone can audit. A directory is also easy to block,
  which is how step 4 hides the test split from the agent.
- **"The Makefile is the single entry point."** CI runs the exact same `make` targets I
  run locally, so "works on my machine" and "works in CI" are the same check.
- **"Pinned images and a lockfile."** `redis:7` could mean a different build next month.
  Exact tags plus `uv.lock` mean someone who clones the repo a year from now gets the
  same environment.

## Questions for me
None blocking. You'll review the drafted seed scenarios' ground truth in the PR, since
that content is the benchmark's answer key.

## Deviations from plan

Recorded after review. Where this list and the plan above disagree, this list wins.

- **AgentView has no `budget`.** Seed budgets scale with difficulty, so showing the budget
  leaked difficulty. The runtime enforces it instead. Don't add it back.
- **CI runs on every push and has no `pull_request` trigger.** Push runs already report on
  PR commits, so a `pull_request` trigger would run everything twice.
- **`required_evidence` is a list of groups**, one per causal fact; citing any ID in a
  group covers it. `distractors` lists every ID of every red herring. In the env-var
  seed, the triggering v3.4.1 deploy is neutral (neither required nor a distractor).
- **The seed test checks the three seed ids exist**, not that dev holds exactly 3
  scenarios, so step 3 can add dev scenarios without breaking it.
- **Commit order:** the schema commit came before the Makefile, because pytest fails
  when there are no tests.
- **Dropped the "duplicate ID across kinds" test.** The per-kind ID prefixes make that
  case impossible.
- **Validation is stricter than planned:**
  - strict types
  - non-blank text
  - at least one distractor
  - `affected_service` must be a known service
  - metric points in time order
  - finite metric values
  - ASCII-digit IDs
  - UTF-8 only, with no byte-order mark
  - no duplicate JSON keys
  - hidden `.json` files rejected
  - an empty directory list rejected
- **Images are pinned by digest** as well as tag. Postgres is 17.8.
- **Not met yet:** the cert seed's causes are `log-001`/`log-002`, not spread through the
  list as planned. The seeds get renumbered before the step-2 baseline is logged (see
  the ARCHITECTURE.md failure-mode table).
