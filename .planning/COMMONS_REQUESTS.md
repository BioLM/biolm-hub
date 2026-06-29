# COMMONS_REQUESTS — per-model batches surface commons changes here

> **Purpose.** Per-model W5 batches **never edit `models/commons/`** (a commons change touches every
> model). When a batch needs a commons change, it **appends a row below** instead of editing commons.
> The coordinator addresses all rows in **one reviewed commons-reconciliation pass (W3b)** after the
> fan-out. This file is internal — it lives in `.planning/` and is deleted before launch.

**Row format:** `| model | file:line | what | why | status |`

| model | file:line | what | why | status |
|---|---|---|---|---|
| boltzgen | `models/commons/util/config.py:71-72` | Remove `protocols_r2_bucket_secret` + `protocols_r2_bucket_secret_name = "protocols-r2-bkt"` | Now unused after boltzgen's protocols output-delivery (checkpoint/resume to internal R2 bucket) removal. boltzgen was the only referencer; `grep -rl protocols_r2_bucket_secret models/` now matches only `commons/util/config.py`. Drop the definition (and the `protocols-r2-bkt` Modal secret) in W3b. | ✅ DONE (already removed during Phase-A de-internalization — config.py now only defines `cloudflare-r2`+`hf-api-token`; `nvidia_ngc_secret`/`ngc-cli-api-key` also already gone. Remaining: user may delete the unused `protocols-r2-bkt` Modal secret from the workspace — harmless infra cleanup, not a code task.) |
| W8/gateway | `models/commons/core/decorator.py:252-283` + `gateway/routing.py:_run_cached._compute` | De-duplicate the partial-payload-reconstruction closure shared by the decorator and the cached gateway (extract a `build_partial_payload(payload, full_items, indices, request_schema)` helper into `commons/core/caching.py`; both call it). | W8 listed this de-dup as a task, but it touches `decorator.py` — every model's runtime path — so it belongs in the reviewed W3b commons pass with a representative deploy (the interim-validation rule), not in Modal-free W8. The cached gateway currently carries its own copy of the closure (correct, just duplicated). Pure refactor; no behavior change intended. | open |
| W8/gateway | `models/commons/util/config.py:16` | `local_models_path = Path(__file__).resolve().parent.parent` resolves to `models/commons`, **not** `models/` — a misnomer. It's now **unused** (only the old gateway consumed it; W8's gateways compute the real models dir locally). Either fix it to mean `models/` (`.parent.parent.parent`) or delete it. Deploy-proven during W8 smoke test: the wrong value mounted commons internals straight into `/root/models`, so `import models.commons` failed in-container. | ✅ DONE (deleted — was unused; `Path` import dropped from config.py; the two gateway comments that name-referenced it updated to be self-contained). |
