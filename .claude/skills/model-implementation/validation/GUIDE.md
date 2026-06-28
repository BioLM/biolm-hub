# Phase 3: Validation

## Purpose
Verify the implementation is correct before documentation and PR. Follow steps in the exact order below — skipping or reordering causes hard-to-debug failures.

---

## 3.1 `make check` — MANDATORY

`make check` runs style (`ruff` + `black`), mypy, and unit tests. This is exactly what CI runs on every PR.

```bash
make check
```

Fix every failure before proceeding. Never push with `make check` red.

If you want to run the sub-checks individually:

```bash
make style        # ruff + black formatting
make mypy         # static type checking (enforced)
make test-unit    # fast unit tests (no Modal, no R2)
```

---

## 3.2 Generate Fixtures — Before Running Integration Tests

If `test.py` uses golden output files (not just custom validators), generate them first:

```bash
python models/<name>/fixture.py
```

This runs the model against predefined inputs and uploads the outputs to R2 as reference ("golden") values. Without this step, integration tests fail with "file not found" errors.

**The golden output is the oracle.** Only regenerate when an output change is intentional, and say so in the PR.

---

## 3.3 Integration Tests — Optional Locally, Mandatory in CI

Integration tests require a Modal account and R2 access. They are OPTIONAL for local development. CI runs them automatically once a maintainer applies the `deploy-approved` label.

If you have a Modal account, run locally with:

```bash
# Single model
python -m pytest models/<name>/test.py -m integration -n auto --no-cov -v -s

# Both integration and deployment tests
python -m pytest models/<name>/test.py -n auto --no-cov -v -s
```

Requirements:
- All tests pass
- Coverage ≥85% on testable code
- Both integration and deployment test types configured in `test.py`

If coverage is below 85%, add test cases for:
- All actions
- Edge cases (empty input, max-length sequences, invalid characters)
- Error paths (bad input, OOM)

Check coverage with:
```bash
pytest models/<name>/test.py --cov=models/<name> --cov-report=term -m integration
```

---

## 3.4 Local Deployment — Optional But Recommended

Building the image locally catches dependency and path errors before CI:

```bash
python models/<name>/app.py
```

This builds the Modal container locally, loads the model, and validates basic inference. Much faster to debug here than in a CI failure.

---

## 3.5 Deploy to Dev Environment — Optional

If you want to verify a live endpoint before PR:

```bash
MODAL_ENVIRONMENT=biolm-models-dev bm deploy <name> --force
```

The full deploy + integration + deployment test matrix runs in CI under the `deploy-approved` label — you do not need to run this before submitting a PR. Once a maintainer approves and applies the label, CI deploys to `biolm-models-dev` and runs the full test suite.

> **Note:** Pushing new commits to an approved PR automatically removes the `deploy-approved` label. Ping a maintainer to re-approve after your last push.

---

## Validation Checklist

- [ ] `make check` passes (style + mypy + unit)
- [ ] All dependencies pinned to exact versions
- [ ] Seeds set (torch, numpy, random, CUDA) — deterministic outputs
- [ ] `UserError` used for bad-input paths
- [ ] Fixtures generated before integration tests (if using golden outputs)
- [ ] Coverage ≥85%
- [ ] Both integration and deployment test types configured
- [ ] No modifications to `models/commons/`

---

## Common Issues

**Tests fail with "file not found"**
You forgot to generate fixtures. Run `python models/<name>/fixture.py` first.

**`Module not found`**
Ensure `models/<name>/__init__.py` exists.

**Coverage below 85%**
Add test cases for edge cases and error paths. Test every action.

**Non-deterministic outputs**
Set all seeds in `move_to_gpu` (or your `@modal.enter(snap=False)` method): `torch`, `numpy`, `random`, and `torch.cuda`.

**GPU OOM**
Reduce batch size, or upgrade the resource spec in `config.py`.

**Image build fails locally**
Check `app.py` image build — wrong dependency version or missing system package.

## Gate

Before Phase 4: `make check` green; unit tests pass; coverage ≥85%.
