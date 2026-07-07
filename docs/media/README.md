# docs/media — launch & onboarding assets

Visual assets for the README, the docs site, and launch posts. All are self-contained and
render on GitHub (Mermaid) or generate locally (VHS).

| Asset | File | What it is |
|-------|------|------------|
| Architecture diagram | [`architecture.md`](architecture.md) | Mermaid: the uniform substrate — 10-file model dir → `commons` → `bh deploy` → Modal → gateway → human/agent. |
| Uniformity diagram | [`uniformity.md`](uniformity.md) | Mermaid before/after (+ table): N bespoke APIs → 1 schema + 6 verbs. |
| Hero cast (tape) | [`hero.tape`](hero.tape) | VHS script for the "zero-to-serving" terminal gif. Run `vhs docs/media/hero.tape` → `hero.gif`. |
| Recording runbook | `../../.planning/DEMO_RECORDING_RUNBOOK.md` | Internal: how to record the two launch videos (quickstart + skill-implements-a-model). |

**Rendering the diagrams:** GitHub renders fenced ` ```mermaid ` blocks natively — no build step.
For the docs site, mkdocs renders them via the Mermaid superfences already configured.

**Generating the hero gif:** `brew install vhs`, then `vhs docs/media/hero.tape`. The tape header
lists prerequisites (a Modal account) and the pre-warm tip for a tight ~20-30s gif. `hero.gif` is a
build artifact — generate it locally and commit the gif, or attach it to the release.

## Additional visual ideas (worth doing later)

- **Catalog UI walkthrough gif** — screen-cast of `bh serve` → browse `/catalog` → pick a model →
  fill the schema-driven form → Run → see results. Shows the human face of the gateway.
- **Action-verbs legend graphic** — the 6-verb closed set (`predict` · `fold` · `encode` ·
  `generate` · `score` · `log_prob`) each with an icon and a one-line "what it means."
- **Per-modality model grid** — models as chips grouped by input molecule (protein / antibody / DNA /
  small-molecule / structure), so newcomers see the breadth at a glance.
- **"Which model?" knowledge-graph snippet** — a short animation of an agent reading `comparison.yaml`
  to *choose* a model, not just call it — the payoff of the machine-readable KG.
- **Deploy fan-out animation** — `bh deploy esm2 --all-variants` → five Modal apps light up (8m → 3B),
  illustrating one family, many variants.
- **"Only the science differs" code diff** — a side-by-side of two models' `config.py`/`schema.py`
  with the plumbing greyed out and the biology highlighted — the uniformity thesis in one frame.
