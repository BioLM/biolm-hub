# N bespoke APIs → 1 schema + 6 verbs

Open bio-ML models each arrive as their own research code: a different interface, a
different dependency mess, a different one-off serving story. biolm-hub collapses all of
it onto one substrate — the biology moves into metadata and tags, the plumbing becomes
uniform.

```mermaid
flowchart LR
    subgraph BEFORE["Before — N bespoke models"]
        direction TB
        B1["ESM-2<br/>own API · own deps · own deploy"]
        B2["Boltz<br/>own API · own deps · own deploy"]
        B3["ProGen2<br/>own API · own deps · own deploy"]
        B4["…37 different interfaces to learn"]
    end

    subgraph AFTER["After — biolm-hub"]
        direction TB
        A1["Same 10-file layout · same schemas<br/>(sequence · heavy_chain / light_chain ·<br/>pdb / cif · smiles · items / results)"]
        A2["6 verbs<br/>predict · fold · encode ·<br/>generate · score · log_prob"]
        A3["One contract<br/>POST /api/v1/{slug}/{action}"]
        A4["Learn one → use all 37"]
    end

    BEFORE ==>|"standardize on models/commons"| AFTER
```

Prefer plain text? The same payoff, as a table:

| | Before (per model) | After (biolm-hub) |
|---|---|---|
| **Layout** | ad-hoc, per repo | identical 10-file directory |
| **Interface** | bespoke function calls | closed set of 6 action verbs |
| **Field names** | invented per model | uniform (`sequence`, `pdb`, `smiles`, `items`/`results`) |
| **Serving** | roll your own | `bh deploy` → `POST /api/v1/{slug}/{action}` |
| **Cost to learn the next model** | start over | ~zero — you already know it |
