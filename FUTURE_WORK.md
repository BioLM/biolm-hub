# Future Work

This is the public, openly-scoped roadmap. We keep deferred work *recorded* (not hidden) so outside
contributors can pick up well-defined pieces. If you want to take one on, open an issue to claim it.

> Items here are intentionally **not** in the current release. They're scoped enough to start, but
> each is a meaningful project on its own.

## Off-Modal Dockerfiles (per eligible model)

Generate a `Dockerfile` + `requirements.txt` per model so models can run **outside Modal**.
Feasibility varies by model:

- **Eligible (realistic):** models with no GPU-at-build step, weights available from a public source
  (HuggingFace Hub or a direct URL), and a standard public base image. The model-source layer maps to
  a plain `COPY`; the weight-download step maps to a `RUN` with build secrets for credentials.
- **Hard / out of scope:** models that compile CUDA/flash-attn extensions during the image build
  (these need build-time GPU access, which standard `docker build` doesn't provide), and any model
  whose base image is a private/closed registry.

The split is the work: define per-model eligibility, generate Dockerfiles for the eligible majority,
and document the tail.

## Benchmarks

Wire standard biological benchmarks (e.g. ProteinGym for variant-effect prediction) into the catalog
so each model's `comparison.yaml` can cite reproducible numbers rather than paper-reported ones.

## Self-improving model-implementation skill

The "add a model" skill should learn from each accepted contribution — capturing recurring review
feedback into the template and the guide so the next contribution starts further along.

## Faster builds

Adopt BuildKit-style caching and shared base layers to cut cold-build times for the heavier
(conda/GPU) models.

## Self-healing weight bake

Every model's `setup_model()` / `@modal.enter` trusts the build-time weight bake — nothing verifies at
runtime that the baked image actually contains the weights. An incomplete or poisoned build-cache layer
therefore crash-loops silently: this class of failure hit `e1-600m`, where a stale cached image was
missing `config.json` (the fix was a `MODAL_FORCE_BUILD=1` rebuild). Proposed: a commons-level runtime
`required_files` check at container start that falls back to `download_model_assets()` when the bake is
incomplete, turning a silent crash-loop into a slower-but-successful cold start. Deferred post-v1: it's a
commons runtime-path change touching every model's startup, and fresh deploys bake correctly, so the risk
of landing it at launch outweighs the benefit.

## Input option-value uniformity

Output field names for per-residue embeddings converged on a single canonical name
(`residue_embeddings`) across the catalog, but the *input* option values that request them still diverge:
`params.include` accepts `per_token` (esm2/esm1b/esmc/e1/zymctrl), `per_residue` (dsm/temberture),
`residue` (igbert/igt5/antifold), and `rescoding` (ablang2) for the same concept. Converging these on one
canonical value — via enum aliases so the existing values keep validating — is a follow-up uniformity
refinement that would bring the input surface in line with the already-unified output surface.

---

*Have something else you think belongs in the catalog? Open an issue — see
[`CONTRIBUTING.md`](CONTRIBUTING.md).*
