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

---

*Have something else you think belongs in the catalog? Open an issue — see
[`CONTRIBUTING.md`](CONTRIBUTING.md).*
