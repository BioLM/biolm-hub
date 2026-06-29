# Review — `models/rf3/` (RosettaFold3)

## Summary

RF3 is structurally a well-formed port: it has all standard files, the right closed-set
action (`fold`), a Pydantic v2 schema with rendering `Field(description=...)`, glossary-pinned
descriptions that match (`seed`, `diffusion_batch_size`, `ptm`, `pae`), structured logging with
no `print`, and a canonical acquisition path (`r2_then_urls`, self-populating R2; no build-time
library import so no `extra_pip_packages` needed — build-order rule satisfied). The plumbing
mostly matches the house pattern (esm2 / dummy).

However, this model reads as **not finished or end-to-end verified**, and several launch gates
are unmet. The runtime still contains scaffolding that admits "foundry integration is [not]
complete," `setup_model` swallows the foundry `ImportError`, the knowledge graph and LICENSE ship
with `pending`/`TODO`/`unknown2025`/`commit: ''`/inferred-copyright placeholders, the public
docs name the wrong action (`predict` vs `fold`) and the wrong GPU (80GB vs 40GB), and there are
real schema↔runtime mismatches: the **required `type` field and the documented `structure_cif`
field are silently dropped by `app.py`**, while the fields that *are* wired (`structure_path`,
`msa_path`) are container-filesystem paths that don't belong in a public API. Inference faults are
also mislabeled as `UserError`. None of these are exotic — they're the kind of thing that means
the diff between rf3 and its siblings is plumbing, not science.

DoD audit (relevant items): self-populates weights via canonical wrapper — **MET**; closed-set
action verb — **MET**; structured logging / no print — **MET**; knowledge graph complete & free of
placeholders — **NOT MET**; no leftover scaffolding — **NOT MET**; error taxonomy correct — **PARTIAL**
(uses typed errors but misapplies `UserError` to server faults); fixtures reproducible via
`fixture.py` — **NOT MET** (generates 1 of 4); per-model LICENSE verified — **NOT MET** (self-admitted
unverified). No internal-reference leakage found (`biolm-modal` / `.planning` / `qa` / internal
domains all clean).

---

## 🔴 Must-fix before launch

### 1. Leftover scaffolding in shipped runtime; foundry `ImportError` swallowed
**Category:** correctness / scaffolding — **`models/rf3/app.py:160-168, 214-219`**

`setup_model` wraps the foundry import in `try/except ImportError` and only `logger.warning`s
("This may be expected if foundry is not yet installed"), explicitly *not* raising. `fold` then
guards with `if not hasattr(self, "RF3InferenceEngine"): raise UserError("... This is expected
during initial setup before foundry integration is complete.")`. This is leftover scaffolding that
must not ship: (a) the message text concedes the integration may be incomplete; (b) a missing core
dependency is a server/deploy fault, not a caller error, yet every request returns a `UserError`
(4xx) instead of failing the container fast; (c) a deploy can come up "healthy" while being
fundamentally broken. No sibling (esm2/dummy) defers a hard dependency this way — they import at
`setup_model` and let failure surface.
**Fix:** import `rf3` unconditionally in `setup_model` (let `ImportError` crash the container at
load), delete the `hasattr` guard and the "initial setup" message in `fold`. If a soft signal is
truly needed, raise `ServerError`, not `UserError`.

### 2. Knowledge graph + LICENSE ship with placeholders / unverified content
**Category:** knowledge graph / licensing — **`sources.yaml:39,48-49,57-58,66-67,76-77,86-87`,
`BIOLOGY.md:72`, `LICENSE:33-36`, `sources.yaml:39` (`commit: ''`)**

The rubric makes "no stray `TODO`/`pending`/template placeholders shipping" and "no inferred
holder/year left unflagged" launch gates. RF3 ships: `snapshot_r2: pending` and eight
`pdf_r2/md_r2: pending` values; an `unknown2025.pdf` placeholder filename
(`sources.yaml:57`); `source_repos[].commit: ''` even though `app.py:54` pins commit
`6866d610…`; a literal `<!-- TODO: Add specific applied literature citations … -->` in
`BIOLOGY.md:72`; and a `LICENSE` whose footer says the copyright holder/year were *inferred* and
"Reviewer should verify the exact copyright line against the upstream LICENSE file before public
release." These must be resolved (not merely flagged) before the repo is public.
**Fix:** fill the real `commit` (6866d610…) into `sources.yaml`; resolve or remove the `pending`
entries and `unknown2025.pdf`; delete the `BIOLOGY.md` TODO comment; verify the upstream
`foundry/LICENSE` copyright line and replace the inferred LICENSE footer with the confirmed text.

---

## 🟠 Should-fix

### 3. Required `type` field is silently dropped by the input builder
**Category:** correctness / broken contract — **`models/rf3/app.py:391-437`, `schema.py:61-63`**

`RF3Component.type` is required (`Field(...)`) and documented as the entity type
(protein/DNA/RNA/ligand), but `_create_input_specification` builds `comp_spec` only from
`sequence`→`seq`, `smiles`, `ccd_code`, `structure_path`→`path`, `chain_id`, and the MSA fields —
`comp.type` is never read. For DNA and RNA components the sequence goes into the same `seq` key as
protein with nothing to disambiguate it, so the headline multi-molecule (DNA/RNA) capability is
likely broken; at minimum the user is forced to supply a field the code ignores.
**Fix:** map `comp.type` into the RF3 spec (e.g. `comp_spec["entity_type"] = comp.type.value` per
foundry's input format), or, if foundry truly infers type from the alphabet, make `type` optional
and document that it's advisory. Verify against a real DNA/RNA run before launch.

### 4. `structure_cif` ignored; only container-path template field is wired
**Category:** schema↔runtime mismatch / API hygiene — **`schema.py:75-80`, `app.py:400-401`,
`README.md:228-259`**

`RF3Component` exposes both `structure_path` ("Path to a template structure file") and
`structure_cif` ("Input structure in mmCIF format"). `app.py` wires only `structure_path`
(`comp_spec["path"]`); `structure_cif` is never read. But the README "Templated Folding" example
(and the docs table) pass `structure_cif=...`, so the only inline/documented way to supply a
template is silently dropped — a broken documented example. Meanwhile `structure_path` (and
`msa_path`) are arbitrary container filesystem paths: useless to an external API caller (they have
no files in the container) and a minor local-file-read smell since the path is handed straight to
the engine.
**Fix:** wire `structure_cif` (write it to a temp file like the MSA path is handled) and drop or
clearly mark `structure_path`/`msa_path` as not-for-public-API; keep `structure_cif` /
`msa_content` / `alignment` as the public inputs. Make README match what's wired.

### 5. Public docs name the wrong action and the wrong GPU
**Category:** docs / broken contract — **`README.md:76` (`### predict`), `README.md:294`
(A100 80GB), `config.py:27-29` (A100_40GB)**

The deployed action is `fold` (`config.py:60-65`, `app.py:174`), but README's "Actions /
Endpoints" section documents `### predict` ("Predicts biomolecular structures") — a caller
following the docs hits the wrong verb. Separately, the Resource Requirements table claims
"A100 80GB" while `config.py` provisions `A100_40GB` (and `MODEL.md`/`comparison.yaml` say 40GB);
the config comment also describes an A100_40GB→80GB "fallback" that doesn't exist (the
`resource_function` returns a fixed spec).
**Fix:** rename the README action section to `fold`; fix the table to A100 40GB; delete the
misleading fallback comment in `config.py`.

### 6. Inference / server faults mislabeled as `UserError`; raw exception leaked
**Category:** errors — **`models/rf3/app.py:249-251`** (also 214-219)

`except Exception as e: … raise UserError(f"RosettaFold3 inference failed: {str(e)}")` blames the
caller (4xx) for what are usually server faults (CUDA OOM, model crash, foundry bug) and
interpolates the raw exception text into the user-facing message, leaking internal detail. esm2
uses `ValidationError400` for caller mistakes and re-raises system faults. The taxonomy
(`BioLMError → UserError/ServerError`, W7) wants genuine faults as `ServerError`.
**Fix:** raise `ServerError` for engine/inference failures with a sanitized message; reserve
`UserError` for validated bad input; don't embed `str(e)` in caller-visible text.

### 7. No input validation (length / alphabet / one-of) unlike the house pattern
**Category:** correctness / uniformity — **`schema.py:65-91, 162-173`**

`RF3Component.sequence` has no `min_length`/`max_length` and no residue-alphabet validator, so the
documented "CANNOT: sequences longer than 2048" (`README.md:64`, `MODEL.md`) is not enforced at the
schema layer — an over-long or garbage sequence passes and fails deep in RF3 (then surfaces as the
mislabeled `UserError` from #6). esm2 enforces both (`max_length=…max_sequence_len` +
`AAExtendedPlusExtra`). There's also no `model_validator` requiring a component to carry at least
one of `sequence`/`smiles`/`ccd_code`, so an empty component validates.
**Fix:** add `max_length=RF3Params.max_sequence_len` (and an alphabet validator) to `sequence`, and
a model-level validator that exactly one payload-bearing field is present per component.

### 8. Field descriptions inaccurate: `name` is required and not echoed
**Category:** field descriptions — **`schema.py:57-60` and `schema.py:162-165`**

Both `RF3Component.name` and `RF3PredictRequestInput.name` are required (`Field(...)`) but described
as *"Optional human-readable label for this input, echoed back in the response."* Neither is
optional, and neither is echoed: `RF3PredictResponse`/`RF3PredictResponseResult` carry no name
field (only `structure_cif`, `confidence`, `early_stopped`, `sample_idx`). Reads as a copy-paste
from a model where `name` was optional/echoed.
**Fix:** correct both descriptions (e.g. "Human-readable label for this input/component; used as
the prediction job name."), and drop "echoed back in the response" unless you add the name to the
response.

### 9. `fixture.py` regenerates only 1 of the 4 fixtures the tests consume
**Category:** tests / reproducibility — **`fixture.py:132-150` vs `test.py:137-176`**

`test.py` references four expected-output fixtures (`…input1/2/3/…input4-msa…`), but
`fixture.py`'s generation suite contains only `INPUT4_MSA`. A contributor running
`python models/rf3/fixture.py` cannot regenerate `input1/2/3`, breaking the documented
generate-then-test workflow (esm2's `fixture.py` generates exactly what its `test.py` consumes).
The four inputs are also hardcoded inline (and duplicated verbatim between `fixture.py` and
`test.py`) rather than drawing on `commons.testing.shared_assets` (W12).
**Fix:** add `input1/2/3` to the generation suite (or drop the unused cases), de-duplicate the
inputs into one module imported by both files, and prefer shared standard sequences where
applicable.

---

## 🟡 Nits

### 10. Multi-checkpoint download map is dead at build time
**Category:** simplicity — **`download.py:18-28, 39-66`**

`download_model_assets(checkpoint_version="latest")` carries `preprint`/`benchmark` URL+filename
maps, but the commons downloader always calls `download_model_assets(base_model_slug,
params_version, variant_config, sub_path)` (no `checkpoint_version`), so only `latest` is ever
fetched. README/MODEL advertise three selectable checkpoints that aren't reachable through any API
path. Either wire checkpoint selection to a variant axis or trim the dead maps and soften the docs.

### 11. Weights fetched over plaintext HTTP with SSL verification disabled, no checksum
**Category:** security — **`download.py:19-21, 58-66`**

Checkpoints come from `http://files.ipd.uw.edu/...` with `verify_ssl=False` and no integrity check.
This is inherent to the upstream IPD host, but a MITM could swap weights on first populate. Worth a
checksum verification step after download (compare to a pinned SHA) before caching to R2.

### 12. pLDDT scale inconsistency between output and threshold
**Category:** docs / schema — **`schema.py:131-135` vs `schema.py:212-215`**

Output `plddt` is documented as 0–100, but `early_stopping_plddt_threshold` is `ge=0.0, le=1.0`
(default 0.5), implying a 0–1 scale internally. Clarify which scale the threshold uses so callers
aren't surprised (e.g. note "fraction in [0,1]" vs "0–100").

### 13. `sources.yaml` metadata polish
**Category:** knowledge graph — **`sources.yaml:25,30`**

`arxiv: 2025.08.14.670328` is a bioRxiv date-DOI, not an arXiv ID (use the `doi` field / a `biorxiv`
key). `authors:` lists `- Simon Mathis et al.` — "et al." inside an author entry; list the named
authors or use a separate flag.

### 14. `comparison.yaml` references `af2_nim`, which has no model dir
**Category:** consistency — **`comparison.yaml:49`**

`af2_nim` is referenced as an alternative but is not a catalog model (also referenced by
boltz/chai1/esmfold, so likely a planned entry). Low confidence — flag only so the cross-reference
is resolved (add the model or rename to the real slug) before launch.

### 15. Minor style: imports inside loops, long `fold`
**Category:** readability — **`app.py:308, 334, 347` (`import gzip`/`numpy` inside loop), `app.py:174`
(`fold` `# noqa: C901`)**

`gzip`/`numpy` are imported inside the per-sample loop; hoist to function top. `fold` is long enough
to warrant `# noqa: C901`; consider extracting output-parsing into a helper for parity with the
small, focused methods in esm2.

---

## Verification

Adversarial re-review of the findings supplied to this verifier.

- **Finding "t" (`a.py:1`, detail "d") — REFUTED.** No file `a.py` exists in `models/rf3/` (contents: `app.py`, `schema.py`, `config.py`, `download.py`, `fixture.py`, `test.py`, `__init__.py`, plus docs/yaml) or anywhere in the repo (`find ... -name a.py` returns nothing); the finding carries no substantive title/detail and cannot be demonstrated against any actual line of code.
