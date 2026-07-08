# docs/media — diagrams & demo assets

Visual assets for the README and the docs site. All are self-contained and render on GitHub
(Mermaid) or generate locally (VHS).

| Asset | File | What it is |
|-------|------|------------|
| Architecture diagram | [`architecture.md`](architecture.md) | Mermaid: the uniform substrate — 10-file model dir → `commons` → `bh deploy` → Modal → gateway → human/agent. |
| Uniformity diagram | [`uniformity.md`](uniformity.md) | Mermaid before/after (+ table): N bespoke APIs → 1 schema + 6 verbs. |
| Hero demo (gif/mp4) | `hero.gif` · `hero.mp4` | The "zero-to-serving" terminal demo — the final rendered clip embedded in the README. |
| Hero source (tape) | [`hero.tape`](hero.tape) | VHS script that produces the hero demo, so anyone can regenerate it when the CLI changes. |

**Rendering the diagrams:** GitHub renders fenced ` ```mermaid ` blocks natively — no build step.
For the docs site, mkdocs renders them via the Mermaid superfences already configured.

**Regenerating the hero demo:** install VHS (`brew install vhs`), then run `vhs docs/media/hero.tape`
to rebuild `hero.gif` + `hero.mp4`. The tape header lists the prerequisites (a Modal account, a
pre-warmed checkout).
