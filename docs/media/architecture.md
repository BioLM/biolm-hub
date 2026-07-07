# Architecture — the uniform substrate

Every model is the same ten files in the same layout. `models/commons` supplies the
shared framework, `bh deploy` ships each variant to *your* Modal account, and the
`biolm-hub` gateway exposes them all behind one HTTP contract and one browser UI.
Same layout, same six verbs, same schemas — **learn one model, use all 37.**

```mermaid
flowchart TD
    subgraph MODEL["models/&lt;name&gt;/ — one model, uniform layout"]
        direction LR
        subgraph CODE["Code — 5 files"]
            direction TB
            C1["config.py<br/>ModelFamily: variants,<br/>action→schema map, class name"]
            C2["schema.py<br/>request / response<br/>Pydantic models"]
            C3["app.py<br/>Modal app +<br/>action methods"]
            C4["download.py<br/>weights<br/>(r2_then_hf, optional)"]
            C5["test.py<br/>TestSuite +<br/>golden fixtures"]
        end
        subgraph KG["Knowledge graph — 5 files"]
            direction TB
            K1["sources.yaml<br/>license · papers · repos"]
            K2["comparison.yaml<br/>when to use / alternatives"]
            K3["README.md"]
            K4["MODEL.md"]
            K5["BIOLOGY.md"]
        end
    end

    COMMONS["models/commons — shared framework<br/>base schemas · decorators · Modal image helpers ·<br/>R2 / download · error taxonomy · logging · test harness"]

    DEPLOY(["bh deploy &lt;model&gt;"])

    subgraph MODAL["Modal — your own account"]
        direction LR
        M1["esm2-8m app"]
        M2["esm2-650m app"]
        M3["… one app per variant"]
    end

    subgraph GW["biolm-hub gateway — bh serve"]
        direction TB
        API["HTTP API<br/>POST /api/v1/{variant-slug}/{action}<br/>6 verbs: predict · fold · encode ·<br/>generate · score · log_prob"]
        UI["Browser catalog UI<br/>/catalog — run inference by hand"]
    end

    subgraph CLIENT["One client, any of 37 models"]
        direction LR
        HUMAN["Human"]
        AGENT["Agent / LLM"]
    end

    CODE --> COMMONS
    COMMONS --> DEPLOY
    DEPLOY --> MODAL
    MODAL --> API
    API --> UI
    API --> HUMAN
    API --> AGENT
    UI --> HUMAN
    KG -. "machine-readable:<br/>which model to use" .-> AGENT
```

*The diff between any two models is the science, never the plumbing — so an agent that
learns one model can call, compare, and even add another.*
