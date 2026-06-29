# Round-1 Review — Gateway design

**Dimension:** Gateway design
**Scope:** `gateway/` — bare `server.py`, cached `server_with_cache.py`, `routing.py`, `config.py`,
`model_discovery.py`, `deploy_gateway.py`, `catalog/`, and gateway tests.
**Reviewer focus:** config-driven discovery, `status_code`→HTTP promotion, both cache tiers off by
default, no auth/billing/analytics residue, OSS readiness, W8/W9 Definition-of-Done.

## Summary

The core routing design is genuinely good and matches the ratified plan. Discovery is config-driven
via `ModelFamily.modal_class_name` (no runtime AST — the AST lives only in the `test_discovery.py` CI
guard, which is the right place). The bare gateway never imports the cache/acquisition stack; the
cached gateway gates **both** tiers behind `BIOLM_CACHE_ENABLED` and is a clean no-op when off. The
`status_code`→HTTP promotion (the deferred W7→W8 decision) is implemented correctly and the
exception/sanitization handling is sound. The two-file split (`server.py` / `server_with_cache.py`)
with a shared `build_gateway_app(use_cache=...)` core is the right abstraction.

The one launch-blocker is a leftover **auth/billing/analytics schema file** (`gateway/schemas/
introspection.py`) that is fully orphaned, contradicts the "no auth/billing/analytics residue" design
mandate, and leaks an internal data-model migration note. Beyond that: a stale-filename doc drift in
`routing.py`, a catalog layer that re-derives grouping/display-names with string heuristics instead of
the authoritative config (and gets multi-variant models like `progen2` visibly wrong), an unfinished
W8 de-dup task, and leftover `console.log` debug scaffolding in the shipped catalog JS.

**DoD status (W8/W9 items):**
- ✅ Bare + cached gateways ship; both caching tiers off by default; discovery is config-driven (no
  runtime AST).
- ✅ `status_code`→HTTP decision implemented + documented.
- ✅ Web app serves catalog with deployed/undeployed/unknown state.
- ❌ "No billing/auth/analytics/internal-domain references anywhere" — **violated** by
  `gateway/schemas/introspection.py` (Finding 1).
- 🟠 W8 "de-dup the partial-payload closure shared by gateway + decorator.py" — **not done**
  (Finding 4).

---

## 🔴 Must-fix

### 1. Orphaned auth/billing/analytics residue + internal leakage — `gateway/schemas/introspection.py`
**Category:** internal leakage / dead code / DoD violation
**Location:** `gateway/schemas/introspection.py:1-50` (entire file; `gateway/schemas/` has no
`__init__.py`)
**Detail:** This file defines `IntrospectionUser`, `IntrospectionAuthorization`, `UsageState`,
`BillingState`, `IntrospectionUsageState`, `IntrospectionBillingState`, `IntrospectionPolicy`
(`rate_limit_per_minute`, `bypass_billing`, `payment_past_due_or_canceled`) and `IntrospectionResponse`
(`token_is_valid`, `allowed_models`, `cache_ttl_seconds`). This is exactly the auth/billing/analytics
machinery W8 was told to **strip** ("strip auth/billing/analytics") and that the DoD requires absent
("No billing/auth/analytics/internal-domain references anywhere"). It is **completely unused** — a repo
grep finds zero importers of `gateway.schemas` / `introspection` / `IntrospectionResponse` /
`BillingState` / `UsageState`. Worse, line 7 leaks an internal data-model migration note:
`company_id: str | None  # Consolidated: company_id replaces institute_id`. This ships publicly and
directly contradicts the gateway's "no auth, no billing, no analytics" identity stated in `server.py`,
`config.py`, and `routing.py`.
**Fix:** Delete the entire `gateway/schemas/` directory (the file and its empty package). Nothing
imports it. Confirm with `grep -rn "gateway.schemas\|Introspection\|BillingState" .` returning nothing
afterward.

---

## 🟠 Should-fix

### 2. Stale filename references in the routing module docstring — `gateway/routing.py:3-4`
**Category:** documentation / consistency
**Location:** `gateway/routing.py:3-4`
**Detail:** The module docstring says: *"Both gateway variants — the bare `gateway/gateway.py` (no
response cache) and `gateway/gateway_with_cache.py` ..."*. Those files no longer exist; they were
renamed to `gateway/server.py` and `gateway/server_with_cache.py` (the `__pycache__` still holds the
old `gateway.cpython-312.pyc` / `gateway_with_cache.cpython-312.pyc` from before the rename). Every
other file (`server.py`, `server_with_cache.py`, `deploy_gateway.py`, `catalog/mount.py`) correctly
says `server.py`. A contributor following this docstring looks for files that aren't there.
**Fix:** Update the docstring to reference `gateway/server.py` and `gateway/server_with_cache.py`.

### 3. Catalog re-derives grouping & display names with string heuristics, ignoring authoritative config — `gateway/catalog/generator.py`
**Category:** weak abstraction / correctness / consistency
**Location:** `gateway/catalog/generator.py:281` (`display_name` from slug), `:302-313`
(`_extract_base_model_slug` regex), `:316-341` (`group_models_by_base`)
**Detail:** The design principle is config-driven discovery — `ModelMapper` already holds the
authoritative `base_model_slug` and `public_display_name` per variant (`model_discovery.py:99-105`).
The catalog throws that away: `generate_catalog_data(app)` takes only the FastAPI app and
reverse-engineers metadata from route paths — deriving `display_name` via
`model_slug.replace("-", " ").title()` and base-slug via regex that only strips `-<size>`/`-n<digit>`
suffixes. This produces **wrong output for descriptive-variant families**. Verified concretely for
`progen2` (variants `progen2-oas/medium/large/bfd90`): the heuristic maps each to its own base
(`progen2-oas`, `progen2-medium`, ...), so the catalog renders **four separate single-variant groups**
instead of one "ProGen2" group with four variants. Display names are also wrong vs config:
`progen2-oas` → "Progen2 Oas" (config: "ProGen2"), `esm2-650m` → "Esm2 650M" (config's curated name).
`esm2-*` and `esm1v-n*` happen to work by luck of matching the regex; named variants don't.
`mount_catalog` already receives the `ModelMapper`, so the authoritative data is in hand.
**Fix:** Pass the `ModelMapper` into `generate_catalog_data` and key grouping/display off
`variant_info["base_model_slug"]` and `variant_info["display_name"]`. Delete `_extract_base_model_slug`
and the slug-`.title()` derivation.

### 4. W8 "de-dup the partial-payload closure" not done — duplication across `routing.py` and `commons/decorator.py`
**Category:** duplication / unfinished DoD task
**Location:** `gateway/routing.py:148-161` (`_compute`) vs `models/commons/core/decorator.py:252-283`
(`compute_function`)
**Detail:** W8 explicitly tasked "de-dup the partial-payload closure shared by `gateway/app.py` +
`decorator.py`." Both closures still independently implement the same tricky reconstruction:
`serialize_model(payload)` → replace `["items"]` with the full/raw items selected by
`indices_to_compute` → re-validate against the request schema. Both even carry the same subtle caveat
that `exclude_none` would strip nested fields if you didn't capture the full items first
(`routing.py:143-146` mirrors `decorator.py:259-265`). This is real, bug-prone duplication: a fix to
the partial-reconstruction logic must be made in two places or the gateway and model-side caches will
diverge.
**Fix:** Extract a shared helper in commons (e.g.
`reconstruct_partial_payload(payload, full_items, indices, request_schema) -> BaseModel`) and call it
from both closures. The gateway/decorator-specific glue (Modal `.remote.aio` vs signature re-bind)
stays in each caller.

### 5. Leftover `console.log` debug scaffolding in shipped catalog JS — `gateway/catalog/static/script.js`
**Category:** leftover scaffolding / OSS readiness
**Location:** `gateway/catalog/static/script.js` — 16 `console.log` calls (lines 9, 11, 26, 39, 544,
571, 596, 604, 607, 633, 637, 643, 649, 660, 670, 680, 697, 706)
**Detail:** The catalog JS ships developer debug logging that runs in every visitor's browser console:
`console.log('Raw schema data:', schemaData)`, `console.log('Parsed schema:', schema)`,
`console.log('Containers found:', {...})`, `console.log('Schema structure check:', ...)`,
`console.log('Processing nested schema structure')`, etc. This is leftover scaffolding that clutters
the console and signals unfinished polish in a public artifact. (The two `console.error` calls for
genuine parse failures are fine to keep.)
**Fix:** Remove the debug `console.log` statements; keep the `console.error` error reporting.

---

## 🟡 Nits

### 6. Internal "legacy" history leaked in a comment — `gateway/routing.py:85`
**Category:** minor internal leakage / polish
**Location:** `gateway/routing.py:84-85`
**Detail:** `_model_class` is documented as instantiating "with no arguments — the container class
supplies defaults for any constructor parameters (e.g. the legacy `app_username`)." `app_username` is
an internal-history artifact that means nothing to an outside contributor and hints at the prior
auth-coupled design. Low severity (it's only a comment), but the public repo shouldn't reference
internal legacy params.
**Fix:** Rephrase generically, e.g. "(the container class supplies defaults for any constructor
parameters)" — drop the `app_username` reference.

### 7. `model_discovery.py` style drift vs sibling files
**Category:** readability / consistency
**Location:** `gateway/model_discovery.py:1-10` (no module docstring), `:3` + throughout
(`Optional[...]`)
**Detail:** Unlike every other gateway module, `model_discovery.py` has no module docstring (it opens
straight into imports) and uses `Optional[X]` while sibling files (`config.py:17`, `server.py`) use the
modern `X | None`. `catalog/generator.py` also does function-body `import re` / `import json`
(`:98`, `:52`, `:309`). Minor, but the dimension's north star is uniformity.
**Fix:** Add a one-line module docstring; normalize to `X | None`; hoist the inline imports. (Low
priority — internally consistent within each file.)

### 8. `cache_enabled_at_build` can mislead operators — `gateway/routing.py:356`
**Category:** minor / observability
**Location:** `gateway/routing.py:350-358` (`health_check`)
**Detail:** The health endpoint reports `cache_enabled_at_build: use_cache`, which reflects which
gateway binary was deployed, **not** whether `BIOLM_CACHE_ENABLED` is actually set at runtime. An
operator reading `cache_enabled_at_build: true` on the cached gateway (with caching off by default at
runtime) could think caching is active. The `_at_build` suffix makes it technically honest, so this is
a nit. (Low confidence it matters in practice.)
**Fix:** Optionally also surface the runtime state (call the same `cache_enabled()` the cache stack
uses) so health reflects whether requests will actually hit a cache.

---

## What's solid (no action needed)
- Config-driven discovery via `modal_class_name`; runtime AST eliminated; CI guard
  (`test_discovery.py`) keeps the declared class name + every action's `@modal_endpoint` method honest.
- Both cache tiers off by default; bare gateway provably avoids the `requests`/acquisition deps via
  lazy imports in the cache-only path (`routing.py:39-41,137,196`).
- `status_code`→HTTP promotion correct for both the direct and cached paths; Modal exceptions mapped to
  404/503/504; uniform sanitized 500 handler; error messages stripped of paths/long tokens.
- All 44 model request schemas carry the `items` field, so the cached path's items-reconstruction
  assumption holds repo-wide (not a latent break).
- `print` is correctly absent from runtime gateway code; the only `print`s are in
  `test_deployment.py`, which is T20-exempt by `pyproject.toml` per-file-ignores.
- Deployment-status check is best-effort with a 3-state (`True`/`False`/`None`) sentinel that avoids
  wrongly greying out models, runs off the event loop, and is cached to avoid per-request subprocesses.

## Verification

Adversarial re-check of the flagged HIGH-severity finding(s) against the actual cited code.

- **"test"** (`gateway/schemas/introspection.py:1`) — **REFUTED.** This is a placeholder stub
  (title "test", detail "test detail"); it makes no demonstrable claim about the code. Line 1 is
  merely `from pydantic import BaseModel`, and "test detail" asserts nothing verifiable, so there is
  no concrete defect to confirm at the cited location.
