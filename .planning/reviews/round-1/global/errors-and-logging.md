# Round-1 Cross-Cutting Review — Errors & Logging Taxonomy

**Dimension:** `models/commons/core/` error taxonomy (`BioLMError`/`UserError`/`ServerError` + codes,
`ErrorResponse`, `ERROR_MAP`) and logging (`get_logger`/`configure_logging`/`DebugLogger`), plus
consistency of usage across the 44 model `app.py` files.

**Files of record:**
- `models/commons/core/error.py` — taxonomy + `ErrorResponse`
- `models/commons/core/logging.py` — `get_logger`/`configure_logging`/`DebugLogger`/`truncate_for_debug`
- `models/commons/core/decorator.py` — `ERROR_MAP`, `_handle_errors`, `_error_response`
- `gateway/routing.py` — status promotion + `_sanitize_error_message` (overlap with gateway review)

## Summary

The **core scaffolding is solid and ships cleanly**: a stable, dotted-`code` taxonomy
(`BioLMError → UserError(+ValidationError400, UnsupportedOptionError, ResourceNotFoundError) /
ServerError(+ModelExecutionError)`), a structured `ErrorResponse`, an ordered `ERROR_MAP`
(specific-before-base, correctly commented), and a single-stdout-handler `get_logger`. The W6 "no
`print` in runtime" DoD is effectively **met** for first-party code (only ruff-ignored sites:
`cli/`, `tooling/`, `scripts/`, tests, `_train.py`, and the globally-excluded vendored `external/`;
the lone `print(` in an `app.py`, `dsm/app.py:131`, is text inside a subprocess `python -c` string,
not a real call). All 44 model `app.py` use `get_logger`. No internal-reference leakage in the core
modules.

The weakness is **application consistency**, not the design. The *system* branch of the taxonomy is
almost entirely unused: `ModelExecutionError` is raised in exactly one model (`biotite`, 2 sites),
while the dominant inference-failure idiom across ~15 models is `except Exception as e: logger.error(...);
raise e` — which falls through to the generic "Uncaught exception" 500 handler with `code=null` and
the raw exception string in the body. Two of the four user-error subclasses
(`UnsupportedOptionError`, `ResourceNotFoundError`) are **defined and wired into `ERROR_MAP` but never
raised**, while their obvious use-sites use bare `ValueError`/base `UserError` instead. There is also
one misclassification that leaks an internal path, two core commons modules that bypass `get_logger`,
and the documented "gateway sanitizes system errors" contract does not hold for model-emitted
`ErrorResponse` bodies.

**DoD audit (W6/W7):**
- W6 "zero `print` in runtime (lint-enforced)" — **MET** (first-party); vendored `external/` exempt by policy.
- W6 "one structured logger across the repo" — **PARTIAL** (core commons `caching.py`/`serializer.py` + `thermompnn_d/util.py` use raw `logging.getLogger`).
- W6 "consistent levels; logs via Modal stdout" — **MET**.
- W7 "ship taxonomy + machine-readable `code` + extend `ERROR_MAP`" — **MET** structurally.
- W7 "error types uniform across families" — **PARTIAL** (system branch unused; 2 user subclasses unused; misclassifications).

---

## Findings

### 🟠 should-fix

#### 1. System-error branch is effectively unused — model crashes return `code=null` + leaked exception text
**Category:** Errors / consistency · **Location:** `models/commons/core/decorator.py:454-462`; pattern across `models/esm2/app.py:165-167,189-191`, `models/esm1v/app.py:134-136,168-175`, `models/esm1b/app.py:146,168`, `models/igbert/app.py:189`, `models/igt5/app.py:165`, `models/msa_transformer/app.py:201`, `models/progen2/app.py:188,202`, `models/sadie/app.py:102`, `models/temberture/app.py:222,251`, `models/tempro/app.py:243`, `models/prostt5/app.py:380`, `models/immunebuilder/app.py:265,352`, `models/abodybuilder3/app.py:242`, `models/antifold/app.py:209` (~21 `raise e` sites).
**Detail:** The ratified taxonomy ships `ModelExecutionError` (`code="system.model_execution"`) precisely so inference failures become a clean, machine-readable 500. In practice `ModelExecutionError` is raised in **one** model (`biotite`, lines 257/384). Every other inference path catches, logs, and re-raises the bare exception (`raise e`), which is not in `ERROR_MAP` and hits the fall-through (`decorator.py:454-462`): `detail=f"Uncaught exception: {exc}"`, `code=getattr(exc,"code",None)` → `None`, plus `traceback_info=True`/`print_exc=True`. So a deterministic OOM/CUDA/shape failure looks like an unhandled bug to callers, carries no stable code, and embeds the raw exception string. The system half of the taxonomy is dead in practice.
**Fix:** In each model's inference `try/except`, wrap as `raise ModelExecutionError("...") from e` instead of `raise e` (or wrap once in the decorator: treat any non-`BioLMError` escaping the user function as `ModelExecutionError`). Then the fall-through becomes a true "unknown bug" path only.

#### 2. `UnsupportedOptionError` and `ResourceNotFoundError` are never raised; their use-sites use bare exceptions
**Category:** Errors / dead code / consistency · **Location:** defined `models/commons/core/error.py:44-53`, wired `models/commons/core/decorator.py:425-426`; missed use-sites: `models/boltz/app.py:453`, `models/abodybuilder3/app.py:171`, `models/immunebuilder/app.py:85,199`, `models/dsm/app.py:234`, `models/prostt5/app.py:175,218`.
**Detail:** Both subclasses are exported and present in `ERROR_MAP` but raised **zero** times repo-wide. Meanwhile textbook use-sites pick something else: `boltz:453 raise UserError("Only batch size 1 is supported currently.")` and `abodybuilder3:171 / immunebuilder:85,199 raise ValueError("Unsupported/Unknown model type: ...")` are exactly `UnsupportedOptionError`. The result is an inconsistent contract — the same class of "you asked for an option I don't support" surfaces as `user.error`, a bare `ValueError` (→ generic 500 fall-through!), or nothing — and two taxonomy slots are dead.
**Fix:** Either adopt the subclasses at their natural sites (`UnsupportedOptionError` for unsupported variants/model-types/batch-limits; `ResourceNotFoundError` for missing named inputs/assets) or, if the project decides the two granular slots aren't warranted, delete them and the `ERROR_MAP` entries. Pick one; don't ship reserved-but-unused public error codes.

#### 3. `ServerError` base is not in `ERROR_MAP`
**Category:** Errors / correctness · **Location:** `models/commons/core/decorator.py:417-430`.
**Detail:** Only `ModelExecutionError` appears in `ERROR_MAP`; the `ServerError` base (and any future system subclass) is absent. A raised `ServerError` therefore skips the clean `(500, "{exc}")` mapping and lands in the fall-through "Uncaught exception" branch with traceback capture — i.e. a *deliberately raised* system error is reported as an *unhandled* one. The mapping is incomplete relative to the shipped taxonomy.
**Fix:** Add a catch-all `ServerError: (500, "{exc}")` entry **after** `ModelExecutionError` (insertion order = isinstance order, so the specific subclass still wins).

#### 4. Misclassified error + internal-path leak in boltz
**Category:** Errors / leakage · **Location:** `models/boltz/app.py:571`.
**Detail:** `raise UserError(f"Model directory does not exist: {self.model_dir}")` reports a **deployment/internal** fault (weights dir missing in the container) as a **400 caller error**, and interpolates an internal container filesystem path into the client-visible `detail`. It is not the caller's fault and the path should not be returned.
**Fix:** Raise `ModelExecutionError("Model weights are not available.")` (→ 500, system branch) and log the concrete path server-side only.

#### 5. Documented gateway sanitization does not cover model-emitted error bodies
**Category:** Errors / leakage / docs-vs-behavior · **Location:** `models/commons/core/error.py:56-61` (docstring claim) vs `models/commons/core/decorator.py:455-462` + `gateway/routing.py:208-213`.
**Detail:** `ServerError`'s docstring states system errors are "sanitized to 5xx by the gateway." But the decorator places `f"Uncaught exception: {exc}"` into the `ErrorResponse.detail`, and the gateway promotes a model's structured `ErrorResponse` body **verbatim** (`routing.py:211-213`, `JSONResponse(status_code=..., content=err.payload)`). `_sanitize_error_message` (`routing.py:71-77`) is only applied to errors raised *at the gateway layer* (`routing.py:344`), never to the model's body. So raw internal exception text/paths from finding #1/#4 reach API callers unsanitized, contradicting the documented contract. (Overlaps the gateway review; recording here because the claim lives in `error.py`.)
**Fix:** Either sanitize/clip `detail` before returning system-branch errors from the decorator, or have the gateway run `_sanitize_error_message` over promoted model bodies for `status_code >= 500`. At minimum, correct the `ServerError` docstring to match actual behavior.

#### 6. Core commons modules bypass `get_logger`
**Category:** Logging / consistency (W6) · **Location:** `models/commons/core/caching.py:19`, `models/commons/data/serializer.py:13`, `models/thermompnn_d/util.py:19`.
**Detail:** W6's goal is "one structured logger across the repo," and all 44 model `app.py` honor `get_logger(__name__)`. But two **core commons** modules use raw `logging.getLogger(__name__)` — ironically they import `DebugLogger` from `commons/core/logging.py` yet skip `get_logger` in the same module. Because `get_logger` is what calls `configure_logging()`, any log these modules emit before some other module has called `get_logger` goes through an unconfigured logger (last-resort handler / wrong format).
**Fix:** Replace with `from models.commons.core.logging import get_logger; logger = get_logger(__name__)` in `caching.py`, `serializer.py`, and `thermompnn_d/util.py`.

### 🟡 nits

#### 7. `raise e` instead of idiomatic bare `raise`
**Category:** Readability / uniformity · **Location:** 21 sites (see finding #1 list).
**Detail:** Within the handling `except`, bare `raise` re-raises without rebinding and is the idiomatic form; `raise e` is slightly noisier. Low impact, but it's a repeated cross-model pattern worth normalizing (and most of these should become `raise ModelExecutionError(...) from e` per #1 anyway).
**Fix:** Prefer bare `raise`, or wrap-and-chain with `from e`.

#### 8. `ValidationError400` name embeds an HTTP status and shadows pydantic's `ValidationError`
**Category:** Naming · **Location:** `models/commons/core/error.py:38`; both names imported into `models/commons/core/decorator.py:10,22`.
**Detail:** The HTTP status (400) lives in `ERROR_MAP`, not the class, so baking `400` into the class name is redundant and brittle if the status ever changes. The name is also one character off from pydantic's `ValidationError` (both in scope in `decorator.py`), inviting confusion.
**Fix:** Consider `InvalidInputError` / `BusinessRuleError` (keep a Pydantic-style alias if any caller imports the old name).

#### 9. User sequence echoed into error detail
**Category:** Logging / leakage · **Location:** `models/sadie/app.py:128`.
**Detail:** `raise ValidationError400(f"Error processing sequence {seq}: {e}")` returns the user's full raw sequence in the response body. It's the caller's own input (not a third-party secret), but it can be large and is inconsistent with the "don't put sequences in messages" convention.
**Fix:** Reference the item by index (`f"Error processing item {i}: {e}"`).

#### 10. `configure_logging` trusts an unvalidated `LOG_LEVEL`
**Category:** Logging / robustness · **Location:** `models/commons/core/logging.py:31-37`.
**Detail:** `root.setLevel(os.environ.get("LOG_LEVEL", "INFO"))` raises `ValueError: Unknown level` if `LOG_LEVEL` is a typo (e.g. `verbose`). Since `configure_logging` runs at the first `get_logger` (import time), a bad env var crashes module import rather than degrading gracefully.
**Fix:** Validate against `logging.getLevelName`/known names and fall back to `INFO` with a one-line warning.

#### 11. `DebugLogger.remove_handler()` is never called; latent handler leak when `debug=True`
**Category:** Logging / correctness · **Location:** `models/commons/core/logging.py:105,162-168`; instantiated `models/commons/core/decorator.py:105`, `gateway/routing.py:163`.
**Detail:** Harmless today because both call sites construct with `enabled=False`/`debug=False` (no handlers created). But if `debug=True` is ever enabled, each request creates `logging.getLogger(f"biolm_debug.{id(self)}")`, adds 1–2 handlers, and never removes them. Logger objects persist in the global `loggerDict` forever, and `id()` reuse after GC can hand a new `DebugLogger` an old same-named logger with stale handlers → duplicated output / unbounded growth.
**Fix:** Call `remove_handler()` in a `finally` around the wrapped call, or build the per-request handler on a transient logger that isn't registered by a reusable `id()`-based name.

#### 12. SMILES fragment logged at debug
**Category:** Logging / leakage completeness · **Location:** `models/boltz/app.py:556`.
**Detail:** `logger.debug("    SMILES: %s", mol.smiles[:64])` writes up to 64 chars of a user molecule to stdout. Debug-level and truncated, so low risk, but noted for completeness against the "never log user inputs" rule. `truncate_for_debug`'s 500-char default (`logging.py:10`) similarly allows ≤500 chars of a sequence in debug payload dumps — acceptable by design.
**Fix:** None required; optionally drop the SMILES debug line.

#### 13. Vendored `external/` prints user sequences at runtime (policy-exempt)
**Category:** Logging / print · **Location:** `models/antifold/external/antiscripts.py:954-956` (full original/mutated sequences), `models/progen2/external/{sample_utils,likelihood_utils}.py:34,38`.
**Detail:** `external/` is globally ruff-excluded and T20-exempt by W6 policy, so these `print`s don't violate the lint gate. But `visualize_mutations` would dump full sequences to stdout if reached. Low priority (vendored, likely off the hot path), flagged only for the "never log full sequences" completeness check.
**Fix:** Leave as vendored unless reachable on the inference path; if reachable, gate behind the structured logger or remove.

#### 14. Central decorator carries shipped `# FIXME(noqa: C901)` complexity suppressions
**Category:** Readability / OSS-readiness · **Location:** `models/commons/core/decorator.py:33,69,89`.
**Detail:** Three functions in the public, central decorator are above the mccabe threshold and suppress it with `# noqa: C901` + a `FIXME` to refactor. This is the most-read commons file; shipping `FIXME` scaffolding in it is a minor OSS-polish smell and signals the error/cache flow is more tangled than ideal.
**Fix:** Track the refactor as a real issue and drop the inline `FIXME`s, or split the wrapper/cache/error concerns so the suppressions aren't needed.

## Verification

Adversarial re-check of the six HIGH-severity findings against the actual code.

1. **System-error branch effectively unused — REAL.** Confirmed `raise ModelExecutionError` appears only in `models/biotite/app.py:257,384`; all 21 other inference paths use `except Exception as e: logger.error(...); raise e` (verified `models/esm2/app.py:165-167,189-191` et al.). Generic exceptions are not in `ERROR_MAP` (decorator.py:417-430), so they hit the fall-through (decorator.py:454-462): `detail=f"Uncaught exception: {exc}"`, `code=None`. (Traceback capture only fires in debug mode per `_error_response` lines 503-510, so that sub-claim is conditional, but the code=null + leaked exception text claim holds.)

2. **UnsupportedOptionError / ResourceNotFoundError defined+wired but never raised — REAL.** `grep "raise UnsupportedOptionError\|raise ResourceNotFoundError"` returns zero hits repo-wide; both are exported (error.py:44-53) and in ERROR_MAP (decorator.py:425-426). Cited use-sites confirmed: boltz/app.py:453 `raise UserError("Only batch size 1 is supported currently.")`; abodybuilder3/app.py:171 and immunebuilder/app.py:85,199 raise bare `ValueError("Unsupported/Unknown model type: ...")` (→ generic 500 fall-through).

3. **ServerError base missing from ERROR_MAP — REAL.** ERROR_MAP (decorator.py:417-430) lists only `ModelExecutionError` in the system branch; `ServerError` base is absent. `isinstance(ServerError(), ModelExecutionError)` is False, so a deliberately-raised `ServerError` skips the clean `(500,"{exc}")` mapping and lands in the fall-through "Uncaught exception" branch. Mapping is incomplete vs the shipped taxonomy (error.py:56-69). (Currently theoretical since ServerError is never raised, but the mapping gap is demonstrable.)

4. **boltz misclassifies internal weights-dir fault as 400 + leaks path — REAL.** boltz/app.py:571 `raise UserError(f"Model directory does not exist: {self.model_dir}")`. UserError → (400, "{exc}") in ERROR_MAP, so a deployment/container fault is reported as a 400 caller error and the internal `self.model_dir` path is interpolated verbatim into the client-visible detail.

5. **ServerError docstring claims gateway sanitization not applied to model bodies — REAL.** error.py:60 docstring says system errors are "sanitized to 5xx by the gateway." The gateway promotes a model's structured ErrorResponse verbatim — routing.py:211-214 `JSONResponse(content=err.payload)` and routing.py:220-224 `JSONResponse(content=response_dict)`. `_sanitize_error_message` (routing.py:71-77) is only applied to gateway-raised errors (routing.py:344), never to the model body. Decorator-emitted `f"Uncaught exception: {exc}"` and boltz's leaked path thus reach callers unsanitized, contradicting the documented contract.

6. **Core commons modules bypass get_logger — REAL.** caching.py:19 and serializer.py:13 use raw `logging.getLogger(__name__)` while importing `DebugLogger` from commons/core/logging.py (caching.py:10, serializer.py:11) yet skipping `get_logger`; thermompnn_d/util.py:19 likewise uses raw getLogger. `get_logger` (logging.py:41-48) is what triggers `configure_logging`, so the W6 "one structured logger" convention is bypassed in core modules. (Practical impact is conditional on call-vs-import ordering — app.py modules call `get_logger` at import time, which usually configures the root before request-time logging — but the convention-bypass itself is verifiable.)

**Summary: all 6 findings verified REAL.**
