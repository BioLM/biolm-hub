# COMMONS_REQUESTS — per-model batches surface commons changes here

> **Purpose.** Per-model W5 batches **never edit `models/commons/`** (a commons change touches every
> model). When a batch needs a commons change, it **appends a row below** instead of editing commons.
> The coordinator addresses all rows in **one reviewed commons-reconciliation pass (W3b)** after the
> fan-out. This file is internal — it lives in `.planning/` and is deleted before launch.

**Row format:** `| model | file:line | what | why | status |`

| model | file:line | what | why | status |
|---|---|---|---|---|
| boltzgen | `models/commons/util/config.py:71-72` | Remove `protocols_r2_bucket_secret` + `protocols_r2_bucket_secret_name = "protocols-r2-bkt"` | Now unused after boltzgen's protocols output-delivery (checkpoint/resume to internal R2 bucket) removal. boltzgen was the only referencer; `grep -rl protocols_r2_bucket_secret models/` now matches only `commons/util/config.py`. Drop the definition (and the `protocols-r2-bkt` Modal secret) in W3b. | open |
