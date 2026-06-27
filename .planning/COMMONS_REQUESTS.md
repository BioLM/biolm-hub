# COMMONS_REQUESTS — per-model batches surface commons changes here

> **Purpose.** Per-model W5 batches **never edit `models/commons/`** (a commons change touches every
> model). When a batch needs a commons change, it **appends a row below** instead of editing commons.
> The coordinator addresses all rows in **one reviewed commons-reconciliation pass (W3b)** after the
> fan-out. This file is internal — it lives in `.planning/` and is deleted before launch.

**Row format:** `| model | file:line | what | why | status |`

| model | file:line | what | why | status |
|---|---|---|---|---|
| _(none yet — batches append here)_ | | | | |
