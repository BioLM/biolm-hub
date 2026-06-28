# PR Management for biolm-models

Patterns for managing PRs across the biolm-models repo — predicting CI impact, debugging failures, reading logs, and verifying model deployments.

## HARD RULES (Non-Negotiable)

These rules override ALL other guidance. Violating them wastes CI time and delays fixes.

**Rule 1: NEVER assume transient — investigate first.** Do NOT retrigger CI until you have identified the root cause from Modal container logs. "It might be transient" is not a root cause.

**Rule 2: Container logs are the PRIMARY diagnostic.** GitHub Actions logs show symptoms. Modal container logs show causes. If you haven't checked container logs, you haven't investigated.

**Rule 3: Local Debugging Workflow is the DEFAULT first action.** When a model fails in CI, deploy it locally + monitor container logs. This is step 1, not a fallback.

**Rule 4: 2+ failures = confirmed bug.** If a model fails twice with similar errors, stop retriggering. Fix the code.

**Rule 5: Opaque errors are NOT infrastructure errors.** "Empty error," "500," or truncated messages usually mean the real error is in container logs. Investigate, don't retrigger.

**Anti-pattern to avoid:** See failure → assume transient → `gh run rerun --failed` → wait → fails again → THEN investigate. One local deploy + container log check finds the root cause in 5 min. Retriggering without investigating first wastes that time for every model in the matrix.

---

## CRITICAL: Always Check Modal Container Logs

**When assessing individual models in CI or locally, you MUST check the Modal container logs while the potentially failing tests are running.** This is THE MOST INFORMATIVE debugging step. GitHub Actions logs only show the test runner's perspective — the actual crash/error often only appears in the Modal container logs.

```bash
# Find ephemeral app for the model being tested
MODAL_ENVIRONMENT=biolm-models-dev modal app list 2>&1 | grep "ephemeral" | grep "<model-name>"

# Stream its logs
timeout 120 bash -c 'MODAL_ENVIRONMENT=biolm-models-dev modal app logs <app-id> 2>&1'

# Key patterns to look for:
#   "Runner failed with exception:" — actual Python traceback
#   "RuntimeError:" — CUDA/torch errors
#   "ModuleNotFoundError:" — missing packages
#   Multiple "Runner failed" entries — crashloop
```

## CI Architecture: Two Workflows

The repo has two separate workflows with different triggers:

| Workflow | File | Trigger | Secrets | What it does |
|----------|------|---------|---------|--------------|
| **CI** | `ci.yml` | Every push / PR open | None | Style, mypy, unit tests, docs build |
| **Gated Deploy & Test** | `deploy.yml` | Maintainer applies `deploy-approved` label | Modal + R2 | Detects changed models, deploys to `biolm-models-dev`, runs integration + deployment tests |

**Key implication:** Opening or pushing to a PR NEVER triggers model deploys automatically. The deploy+test matrix only runs after a maintainer explicitly applies `deploy-approved`. Any new push to the PR auto-removes the label, forcing re-review of the new code before it can be re-approved.

## Predicting CI Impact Before Pushing / Requesting the Label

The "Gated Deploy & Test" pipeline is SELECTIVE — it uses smart detection scripts to determine which models to deploy+test based on the git diff. **Before requesting `deploy-approved`, predict the blast radius:**

```bash
# Predict which models would be deployed+tested when the label is applied
cd .github/scripts && python detect_models.py origin/main --smart 2>&1

# Check if "CI" is already running (pushing cancels it)
gh run list --branch $(git branch --show-current) --status in_progress --json databaseId --jq length
```

Note: the "CI" workflow always runs all unit tests regardless of what changed.

### What the Deploy Matrix Triggers

| Change | Models Deployed | Unit Tests (CI) |
|--------|----------------|-----------------|
| Single model file (`models/boltz/app.py`) | Only that model | All |
| Non-critical commons file | Smart: only importers of changed symbols | All |
| **Critical commons** (`pydantic.py`, `decorator.py`, `caching.py`) | **All models** | All |
| `pyproject.toml`, `uv.lock`, `Makefile` | 0 models | All |
| `.github/workflows/*.yml` | 0 models | All |
| Only docs (`.md`, `.txt`) | 0 models | 0 |

### Push / Label-Request Decision Rules

```
# Before pushing:
IF CI (style/mypy/unit) is currently running:
    WARN: "Pushing now CANCELS the in-progress CI run"
    Consider waiting, or use: gh run rerun <id> --failed

# Before requesting the deploy-approved label:
IF model_count == 0:
    No deploy cost — label is safe

ELIF model_count <= 5 AND NOT commons_changed:
    Label OK — but test those models locally first

ELIF model_count <= 15:
    Batch preferred — accumulate fixes, test locally, then request label
    Warn: "This label triggers {N} model deploys"

ELIF model_count > 15 OR critical_commons_changed:
    MUST batch everything. Test models_with_code_changes locally.
    Never request label with known failures.
    Warn: "This label triggers all models"
```

### Which Models to Test Locally

Test the models in `models_with_code_changes` (those with direct file changes). These are most likely to fail. Models triggered only by commons inheritance are lower risk.

## Reading CI Logs

GitHub Actions job names contain emojis which break `gh run view --job`. Use the API directly:

```bash
# Get run ID for "Gated Deploy & Test" (integration/deployment failures)
run_id=$(gh run list --branch <branch> --json databaseId,name --jq \
  '[.[] | select(.name=="Gated Deploy & Test")][0].databaseId')

# Get run ID for "CI" (style/mypy/unit failures)
run_id=$(gh run list --branch <branch> --json databaseId,name --jq \
  '[.[] | select(.name=="CI")][0].databaseId')

# List failed jobs
gh api "repos/BioLM/biolm-models/actions/runs/$run_id/jobs?per_page=100" \
  --jq '.jobs[] | select(.conclusion=="failure" and (.name | test("Integration"))) | "\(.id)|\(.name | sub(".*- "; ""))"'

# Get logs for a specific job
gh api "repos/BioLM/biolm-models/actions/jobs/<JOB_ID>/logs"
```

## Real-Time Failure Triage

When "Gated Deploy & Test" is running, don't wait for it to finish:

1. **Monitor Modal container logs immediately** — as soon as a model starts its integration test, find its ephemeral app and stream logs (see "Local Debugging Workflow" below for the exact technique)
2. **Get CI test output** via the GitHub API
3. **Cross-reference both streams using timestamps** — CI logs show test failures (assertion errors, HTTP 500s, timeouts); Modal container logs show WHY (Python tracebacks, import errors, CUDA crashes). Match the timing: a test failure at T+30s corresponds to whatever the container was doing at T+30s in the modal logs.
4. **Categorize**: image build error (container never started), import error (started but crashed immediately), runtime crash (started, loaded, then died), or test assertion (model ran but returned wrong output)
5. **Start fixing locally** using the parallel debugging workflow while other CI jobs continue
6. **Do NOT push until full run completes** — collect all failures, fix all in one batch

### Failure Triage Decision Tree

Follow IN ORDER. Do NOT skip to action.

1. **Is the job `cancelled` (not `failure`)?** → Safe to retrigger: `gh run rerun <id> --failed`
2. **Does the CI log have a CLEAR error?**
   - `Image build failed` → Fix deps, test locally
   - `ModuleNotFoundError` → Fix package versions
   - `Actual output does not match expected` → Regen fixtures locally, retrigger
   - Clear traceback → Fix the bug
   - Opaque/empty/500/timeout → **Go to step 3**
3. **Run Local Debugging Workflow (MANDATORY)** — deploy model + stream container logs. The real error is there.
4. **After investigation** — fix code and push, OR if local test passes with no errors, THEN retrigger

| Category | CI Pattern | Container Log Pattern | Action |
|----------|-----------|----------------------|--------|
| Cancelled | Status: cancelled | N/A | Retrigger OK |
| Image build | `Image build failed` | Build step traceback | Fix deps locally |
| Import/CUDA | Opaque 500, timeout, empty | RuntimeError, ImportError, NVRTC | Fix deps/container |
| Fixture mismatch | `does not match expected` | Model runs OK | Regen fixtures locally |
| True transient | Varies | Local test PASSES | Retrigger |

### CRITICAL: Investigate Before Retriggering

**As SOON as a failure appears in CI (even while other jobs are still running), start investigating locally.** Don't wait for the full run to finish. The sooner you understand the failure, the sooner you can fix it. Start the local debugging workflow immediately.

### Efficiency Trick: Local Fixture Regen + Surgical CI Retrigger

When a model fails due to fixture mismatch (model works but outputs differ from golden files):
1. Regenerate fixtures **locally**: `MODAL_ENVIRONMENT=biolm-models-dev python models/MODEL/fixture.py`
2. Fixtures upload directly to R2 — no code commit needed
3. Surgically retrigger ONLY the failed CI jobs: `gh run rerun <id> --failed`
4. The retrigger pulls fresh fixtures from R2 and should pass

This avoids a full CI rebuild.

## Local Debugging Workflow (The Primary Technique)

The most effective debugging approach requires PARALLEL monitoring of two output streams: the local test runner (which shows assertion failures and HTTP-level errors) and the Modal container logs (which show the actual Python tracebacks, import errors, and CUDA crashes inside the container). **Neither stream alone tells the full story.**

### Step-by-step flow

```
1. DEPLOY the model:
   MODAL_ENVIRONMENT=biolm-models-dev bm deploy MODEL

2. RUN the test IN THE BACKGROUND so you can simultaneously monitor logs:
   # Run test in background, capture output
   python -m pytest models/MODEL/test.py -k integration -v --no-cov -s > /tmp/test_output.log 2>&1 &
   TEST_PID=$!

3. IMMEDIATELY find the ephemeral app (it only exists while the test is running):
   MODAL_ENVIRONMENT=biolm-models-dev modal app list 2>&1 | grep "ephemeral" | grep "MODEL"
   # Note: the app name contains the model name. Apps disappear shortly after
   # the test ends, so you must capture the app-id NOW.

4. STREAM the Modal container logs with a timeout:
   timeout 120 bash -c 'MODAL_ENVIRONMENT=biolm-models-dev modal app logs <app-id> 2>&1' | tee /tmp/modal_logs.log

5. WAIT for the test to finish and READ its output:
   wait $TEST_PID
   cat /tmp/test_output.log

6. CROSS-REFERENCE both outputs:
   - Match timestamps: if the test hung at second 45, look at what the container
     was doing at that same time in the modal logs
   - Test shows "500 Internal Server Error" → container logs show the traceback
   - Test shows timeout → container logs may show the function never started
     (image build issue) or started but crashed (runtime error)

7. HYPOTHESIZE → CHANGE CODE → repeat from step 1
```

### For Claude Code agents specifically

Since you operate in a single terminal, use `run_in_background` for the test, then actively poll `modal app list` to find the ephemeral app and stream its logs. After the background test completes, read both outputs and cross-reference. The key insight: **you must start streaming container logs WHILE the test is still running** -- if you wait until after the test finishes, the ephemeral app may already be gone.

### Timing and ephemeral app lifecycle

- Ephemeral apps are created when the test calls the deployed Modal function
- They appear in `modal app list` within a few seconds of the test starting
- They persist for a short window after the test ends (seconds to ~1 minute)
- App names follow the pattern: look for `ephemeral` entries containing the model name
- If you miss the window, you must re-run the test and be faster

### WiFi resilience

```bash
# Use nohup for long-running deploys
nohup bash -c "MODAL_ENVIRONMENT=biolm-models-dev bm deploy MODEL" > /tmp/deploy.log 2>&1 &
```

## Pre-Push Checklist

1. `make style` passes
2. Run blast-radius prediction: `cd .github/scripts && python detect_models.py origin/main --smart`
3. All `models_with_code_changes` models deploy locally without errors
4. Integration tests pass locally for modified models
5. No inline comments inside `from_registry()` strings
6. Python 3.12 models: numpy >= 1.26, scipy >= 1.11
7. `models/commons/model/pydantic.py` uses `try/except ImportError` (sadie compat)
8. CI is not currently running (or you accept cancelling it)

## Model Upgrade Tiers

| Tier | Description | Action |
|------|-------------|--------|
| GREEN | debian_slim, no ML deps | Safe to upgrade Python |
| YELLOW | PyTorch container, standard deps | Upgrade tag, verify builds+tests |
| RED | flash-attn, openfold, torch_scatter, TF, sadie | Stay pinned, document why |
