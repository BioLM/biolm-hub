# Pre-push / pre-PR checklist

The house-rules gate is canonical in `.github/PULL_REQUEST_TEMPLATE.md` and `CONTRIBUTING.md`. Confirm
that gate first (item 1), then the operational checks the template can't cover:

1. The PR-template gate is green: `make check` passes and `make docs` builds, and you didn't push just to re-trigger CI.
2. Blast radius predicted **from the repo root**: `python .github/scripts/detect_models.py origin/main --smart` (see `references/ci-impact.md`).
3. Every `models_with_code_changes` model deploys locally without error.
4. Integration tests pass locally for the modified models.
5. No inline comments inside `from_registry()` strings.
6. Python 3.12 models: `numpy >= 1.26`, `scipy >= 1.11`.
7. `models/commons/model/pydantic.py` keeps its `try/except ImportError` (sadie compat).
8. No secrets in the diff (the `secret scan` job scans full history).
9. CI is not mid-run (or you accept that pushing cancels it).
