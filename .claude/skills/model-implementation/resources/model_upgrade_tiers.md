# Model Upgrade Tiers

A model's dependency stack determines how freely its Python version and package pins can move.
Classify each model into one of three tiers and act accordingly — the more exotic the compiled/ML
dependencies, the more conservative the pin.

| Tier | Stack | Action |
|------|-------|--------|
| GREEN | `debian_slim`, no ML dependencies (pure-Python / algorithmic tools) | Safe to upgrade Python freely |
| YELLOW | A standard PyTorch container with mainstream dependencies | Upgrade the tag, then verify the image builds and tests pass |
| RED | Fragile compiled/ML stacks — `flash-attn`, `openfold`, `torch_scatter`, TensorFlow, `sadie` | Stay pinned; document why |

**GREEN** models (e.g. `dna_chisel`, `biotite`) carry nothing that couples to a specific Python or
CUDA build, so their pins move with little risk.

**YELLOW** models run on a pinned PyTorch base image with common ML dependencies. A version bump is
usually fine but must be confirmed with a local image build plus the model's tests before it ships.

**RED** models depend on packages whose builds are tightly coupled to exact `torch` / CUDA / Python
versions (or ship pre-built wheels for a narrow matrix). Keep these pins frozen and record the reason a
version is held back in the PR / implementation notes, so a later contributor doesn't "modernize" them
and break the build.
