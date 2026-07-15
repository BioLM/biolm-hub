# Debugging CI failures and Modal crashes

The default first action on any model failure. The Core Rules in `SKILL.md` always apply — read the
container logs before you retrigger anything.

## CRITICAL: Always Check Modal Container Logs

**When assessing individual models in CI or locally, you MUST check the Modal container logs while the potentially failing tests are running.** This is THE MOST INFORMATIVE debugging step. GitHub Actions logs only show the test runner's perspective — the actual crash/error often only appears in the Modal container logs.

```bash
# Find ephemeral app for the model being tested
MODAL_ENVIRONMENT=biolm-hub-dev modal app list 2>&1 | grep "ephemeral" | grep "<model-name>"

# Stream its logs (Ctrl-C to stop):
MODAL_ENVIRONMENT=biolm-hub-dev modal app logs <app-id> 2>&1
# To auto-stop after 120s, wrap it: `timeout 120 …` on Linux/CI; on macOS use
# `gtimeout 120 …` (coreutils: `brew install coreutils`) — plain `timeout` is not installed there.

# Key patterns to look for:
#   "Runner failed with exception:" — actual Python traceback
#   "RuntimeError:" — CUDA/torch errors
#   "ModuleNotFoundError:" — missing packages
#   Multiple "Runner failed" entries — crashloop
```

## Reading CI Logs

Job names contain separators and matrix suffixes (e.g. `lint · types · unit`, `Integration tests — esm2`) that are awkward to match with `gh run view --job`. Query the API directly instead:

```bash
# Get run ID for "Gated Deploy & Test" (integration/deployment failures)
run_id=$(gh run list --branch <branch> --json databaseId,name --jq \
  '[.[] | select(.name=="Gated Deploy & Test")][0].databaseId')

# Get run ID for "CI" (style/mypy/unit failures)
run_id=$(gh run list --branch <branch> --json databaseId,name --jq \
  '[.[] | select(.name=="CI")][0].databaseId')

# List failed jobs
gh api "repos/BioLM/biolm-hub/actions/runs/$run_id/jobs?per_page=100" \
  --jq '.jobs[] | select(.conclusion=="failure" and (.name | test("Integration"))) | "\(.id)|\(.name | sub(".*- "; ""))"'

# Get logs for a specific job
gh api "repos/BioLM/biolm-hub/actions/jobs/<JOB_ID>/logs"
```

## Real-Time Failure Triage

When "Gated Deploy & Test" is running, don't wait for it to finish:

1. **Monitor Modal container logs immediately** — as soon as a model starts its integration test, find its ephemeral app and stream logs (see "Local Debugging Workflow" below for the exact technique)
2. **Get CI test output** via the GitHub API (see "Reading CI Logs" above)
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
1. Regenerate fixtures **locally**: `MODAL_ENVIRONMENT=biolm-hub-dev python models/MODEL/fixture.py`
2. Fixtures upload directly to R2 — no code commit needed. **Writing goldens needs your own R2 bucket + write credentials** (public goldens are maintainer-populated); a credential-less contributor can't take this path.
3. Surgically retrigger ONLY the failed CI jobs: `gh run rerun <id> --failed`
4. The retrigger pulls fresh fixtures from R2 and should pass

This avoids a full CI rebuild.

## Local Debugging Workflow (The Primary Technique)

The most effective debugging approach requires PARALLEL monitoring of two output streams: the local test runner (which shows assertion failures and HTTP-level errors) and the Modal container logs (which show the actual Python tracebacks, import errors, and CUDA crashes inside the container). **Neither stream alone tells the full story.**

### Step-by-step flow

```
1. DEPLOY the model:
   MODAL_ENVIRONMENT=biolm-hub-dev bh deploy MODEL

2. RUN the test IN THE BACKGROUND so you can simultaneously monitor logs:
   # Run test in background, capture output. `-m integration` is a pytest MARKER
   # (not `-k`) — matches every model's test.py and the Makefile / deploy.yml.
   python -m pytest models/MODEL/test.py -m integration -v --no-cov -s > /tmp/test_output.log 2>&1 &
   TEST_PID=$!

3. IMMEDIATELY find the ephemeral app (it only exists while the test is running):
   MODAL_ENVIRONMENT=biolm-hub-dev modal app list 2>&1 | grep "ephemeral" | grep "MODEL"
   # Note: the app name contains the model name. Apps disappear shortly after
   # the test ends, so you must capture the app-id NOW.

4. STREAM the Modal container logs (Ctrl-C or a timeout wrapper to stop):
   MODAL_ENVIRONMENT=biolm-hub-dev modal app logs <app-id> 2>&1 | tee /tmp/modal_logs.log
   # To auto-stop after 120s: prefix `timeout 120 …` on Linux/CI, or `gtimeout 120 …`
   # on macOS (coreutils: `brew install coreutils`) — plain `timeout` is absent on macOS.

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

### Long-running deploys (detach with nohup)

```bash
# Use nohup for long-running deploys
nohup bash -c "MODAL_ENVIRONMENT=biolm-hub-dev bh deploy MODEL" > /tmp/deploy.log 2>&1 &
```
