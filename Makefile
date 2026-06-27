.PHONY: install style lint format mypy check test test-unit test-integration test-deployment docs clean

# Helper to scope tests to one or more models:
#   make test MODEL=esm2
#   make test MODELS=esm2,peptides
comma := ,
define get_test_paths
$(if $(MODEL),models/$(MODEL),$(if $(MODELS),$(foreach m,$(subst $(comma), ,$(MODELS)),models/$(m)),))
endef

# Create the venv and install all dev/test/type dependencies via uv.
install:
	@command -v uv >/dev/null 2>&1 || { echo "Installing uv..."; curl -LsSf https://astral.sh/uv/install.sh | sh; }
	uv venv --python $(shell cat .python-version)
	uv sync --all-extras
	@if [ -d .venv ]; then .venv/bin/pre-commit install --install-hooks || true; fi
	@echo "✅ Installed. Run 'bm setup' to check your Modal/R2 config."

# Run all formatting + lint hooks (ruff, black, basic hygiene). Falls back to ruff+black if pre-commit is absent.
style:
	@if command -v pre-commit >/dev/null 2>&1; then \
		pre-commit run --all-files; \
	else \
		$(MAKE) format lint; \
	fi

lint:
	uv run ruff check .

format:
	uv run black .

# Static type checking (enforced repo-wide).
mypy:
	uv run mypy .

# Everything CI runs on every PR: style + types + unit tests (no Modal/R2 needed).
check: style mypy test-unit

# All non-deployment tests (scope with MODEL=/MODELS=).
test:
	uv run pytest -m "not deployment" -n auto --no-cov -v $(call get_test_paths)

# Fast, safe tests — no Modal, no R2, no external services. Runs anywhere (and in CI on every PR).
UNIT_TEST_MARKER := not integration and not deployment and not slow and not e2e and not live_modal
test-unit:
	uv run pytest -m "$(UNIT_TEST_MARKER)" -n auto --no-cov -v $(call get_test_paths)

# Integration tests — deploy to a Modal env + pull golden fixtures from R2. See 04_TESTING_STRATEGY.
test-integration:
	uv run pytest -m "integration" -n auto --no-cov -v $(call get_test_paths)

# Deployment tests — run against a live deployed endpoint.
test-deployment:
	uv run pytest -m "deployment" -n auto --no-cov -v $(call get_test_paths)

docs:
	uv run mkdocs build --strict

clean:
	@find . -not -path "./.venv/*" \( \
		-name "*.pyc" -o -name "*.pyo" -o -name "__pycache__" -o \
		-name ".pytest_cache" -o -name ".ruff_cache" -o -name ".mypy_cache" -o -name "htmlcov" \
	\) -print0 | xargs -0 rm -rf
	@rm -f .coverage coverage.xml
	@echo "Done cleaning."
