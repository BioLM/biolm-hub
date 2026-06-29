# Review — `models/sadie/`

**Reviewer:** independent round-1 (rubric A–D)
**Verdict:** Solid, faithful port of an algorithmic annotation tool. Layout, config, tags, actions,
logging, license, and acquisition (none needed — bundled HMM DBs) all conform. No internal-reference
or secret leakage. The launch blockers are *plumbing-uniformity* issues, not science: an input
sequence is echoed into an error message, all exceptions are funnelled into a user-`400`, three
response fields ship in PascalCase against the snake_case house norm, and the public docs state a
fabricated expansion of the "SADIE" acronym that contradicts the model's own LICENSE/sources.yaml.

No 🔴 (nothing crashes, leaks secrets, or breaks the wire contract). Findings are 🟠/🟡.

---

## 🟠 Should-fix

### 1. Error message echoes the full input sequence — `app.py:128`
```python
raise ValidationError400(f"Error processing sequence {seq}: {e}") from e
```
`{seq}` interpolates the entire user-supplied amino-acid sequence into the error string, which is
returned to the caller and logged. The house rule (rubric A.4/A.6) is "no leaked sequences" in
descriptions/logs/errors. It also re-emits the raw upstream exception text `{e}` verbatim.
**Fix:** reference the item by index, not content, and don't splice raw library text into a user
message — e.g. `raise ValidationError400(f"Could not annotate item {idx}: not a recognizable antibody/TCR variable domain.")`.
Keep the original cause for the server log via `from e` / `exc_info`.

### 2. Blanket `except Exception → ValidationError400` misclassifies server faults — `app.py:122-128` (and `89-102`)
`_compute_sadie` wraps *everything* from `run_single(...)`/`to_dict(...)[0]`/`SADIEPredictResponseResult(**r)`
into a `ValidationError400` (a `UserError`, HTTP 400). Real server faults — missing HMMER binary, an
OOM, a library bug, or a schema/library field mismatch on `SADIEPredictResponseResult(**r)` — would be
reported to the caller as "your input was bad." A common, legitimate case also lands here cryptically:
when SADIE finds no Ig/TCR domain, `run_single(...).to_dict(orient="records")` is empty and `[0]` raises
`IndexError: list index out of range`, surfaced as a confusing 400. The outer `try/except` in `predict`
(89-102) then logs that same user-400 at `error` level with a full traceback on every bad input.
The W7 taxonomy wants caller mistakes as `UserError` with stable codes and system faults to
propagate/sanitize as `ServerError`. **Fix:** detect the empty-result case explicitly and raise a clear
`ValidationError400` ("no antibody/TCR domain detected"); let unexpected exceptions propagate (or wrap as
`ServerError`) rather than collapsing all of them to 400; drop or downgrade the redundant outer
log-and-reraise so normal 400s aren't logged at `error` with tracebacks.

### 3. Response fields break the snake_case house convention — `schema.py:140,143,146`
`Chain`, `Numbering`, `Insertion` ship in PascalCase because they're the raw SADIE DataFrame column
names; every other field in this and every other model is snake_case (`domain_no`, `hmm_species`,
`chain_type`, …). This is exactly the "plumbing, not science" divergence the repo's north star and
rubric A.3 ("Renames keep a Pydantic alias") target. Relatedly, `app.py:126` does a manual
`r["e_value"] = r["e-value"]` to bridge the `e-value` column — the same problem handled ad-hoc.
**Fix:** declare snake_case fields (`chain`, `numbering`, `insertion`, `e_value`) and map the library's
keys once — either rename the dict keys in `app.py` before `SADIEPredictResponseResult(**r)`, or add a
Pydantic `alias` per field. (Note the v1/v2 split: the result is *constructed* in the pydantic-v1
container but the JSON schema is *rendered* under v2, so prefer renaming the dict keys in `app.py` to
avoid alias/`populate_by_name` behaving differently across the two — it also lets you delete the manual
`e-value` line.)

### 4. Fabricated, self-contradicting SADIE acronym in shipped docs — `README.md:7`, `MODEL.md:7`
Both say **"SADIE (Sequence Analysis and Domain Identification Engine)"**, which is invented and
contradicts the model's own files: `LICENSE:25` and `sources.yaml:20` both use the real upstream name
**"(The) Sequencing Analysis and Data Library for Immunoinformatics Exploration."** The README
References/BibTeX (`README.md:231,237`) give yet a third title ("Antibody sequence analysis, numbering,
and annotation"). Three names for one tool, one of them wrong, in public-facing docs (rubric C/A.9).
**Fix:** use the upstream expansion ("Sequencing Analysis and Data Library for Immunoinformatics
Exploration") consistently across README.md, MODEL.md, and the citation.

---

## 🟡 Nits

### 5. Wrong memory comment — `config.py:21`
`memory=1024,  # 1MB RAM` — 1024 is **MB**, i.e. 1 GB (which is what README/MODEL state). The dummy
template gets this right (`memory=512,  # 512MB RAM`). **Fix:** `# 1024 MB (1 GB) RAM`.

### 6. `run_multiproc=True` is pointless overhead here — `app.py:117`
A fresh `Renumbering(run_multiproc=True)` is created per sequence and then called with `run_single`
(one sequence). Multiprocessing can't parallelize a single sequence, and under `cpu=0.125`
`multiprocessing` typically sizes pools to the *host* core count (it doesn't see the cgroup limit),
so this is pure fork/IPC overhead at best. **Fix:** `run_multiproc=False` for the per-sequence path,
or restructure to one `run_multiple(...)` call over the batch where the flag would actually help.

### 7. Memory snapshot is cosmetic; docs overstate it — `app.py:58-69`, `README.md:215`, `MODEL.md:215`
`@modal.enter(snap=True) load_model` only binds `self.Renumbering = Renumbering` (the *class*); the
expensive HMM-profile/germline-DB load happens at request time inside `Renumbering(...)` in
`_compute_sadie`. So the snapshot captures essentially nothing, while the README claims it
"pre-load[s] the model." **Fix:** either pre-construct a `Renumbering` instance in the snap=True
enter so the DBs actually live in the snapshot, or soften the docs to say only the import is snapshotted.

### 8. Thinner knowledge graph than the house norm — `sources.yaml:34-41`
`commit: ''` is empty and `snapshot_r2: pending` for both the GitHub and PyPI repos; esm2 pins the
commit hash and captures a `snapshot_r2` tarball. (`pending` on the *paper* PDF/MD is acceptable —
SADIE has no paper — but the repo pin/snapshot are the reproducibility anchors here, especially since
there's no peer-reviewed citation.) **Fix:** pin the GitHub commit for `sadie-antibody==1.0.6` and
capture the repo snapshot, or set the unused paper fields to empty rather than `pending`.

### 9. Single happy-path test fixture — `test.py:13-25`, `fixture.py`
Only one `predict` case (one antibody sequence, default params) is exercised. The non-trivial,
self-advertised paths — `scfv=True` (multi-domain output), TCR chains, and batch >1 — have no
coverage, and `request_schema=None` means the request model itself is never validated in tests.
**Fix:** add at least an scFv and a TCR/multi-sequence fixture; these are the cases most likely to
regress and the ones the docs promote.

---

## D. Definition-of-Done audit (per-model hardening)
- **Layout / config / tags / single action `predict`** — met. `config.py` mirrors the dummy template
  exactly; tags (`ANTIBODY`, `TCR`, `ANNOTATION`, `ANNOTATIONS`, `ALGORITHMIC`) all exist.
- **Field descriptions render** — met. All request/response fields use field-level `Field(description=...)`
  (no `Optional[Annotated[...]]` drop trap); descriptions are accurate and free of leaked content.
- **Errors typed** — *partially met* (finding #2): typed `ValidationError400` is used, but over-broadly.
- **Logging** — met. `get_logger`, no `print` (T20 clean), no full sequences in *logs* (but see #1 for the
  error-message echo).
- **Acquisition** — N/A and correct: algorithmic tool, HMM DBs ship inside `sadie-antibody==1.0.6`;
  `setup_source_layer` only, no `download.py` (same shape as dummy). Pydantic-v1 constraint is documented
  in `app.py:30-37` and handled by the commons dual-path `RequestModel`/`ResponseModel`.
- **Licensing** — met. Per-model MIT `LICENSE` with upstream attribution; consistent with `sources.yaml`.
- **Knowledge graph (5 files)** — *partially met*: present, but the acronym inconsistency (#4) and
  thinner `sources.yaml` (#8) are gaps.
- **Tests (integration + deployment)** — met structurally (both generated); coverage is thin (#9).

---

## Verification

Adversarial re-check of the four high-severity findings against the actual code (verdicts are DATA).

1. **Error message echoes the full input sequence — REAL.** `app.py:128`
   `raise ValidationError400(f"Error processing sequence {seq}: {e}")` — `seq` (set at `app.py:121`)
   is the full user sequence; `ValidationError400` is a `UserError` whose message is "returned to the
   user ... surfaced verbatim" (`commons/core/error.py:20-41`), and the outer handler logs it at
   `error` with `exc_info=True` (`app.py:101`). Sequence leaks to both caller and logs, plus raw `{e}`.

2. **Blanket `except Exception` → `ValidationError400` misclassifies server faults — REAL.**
   `app.py:122-128` catches *all* exceptions and re-raises as HTTP-400 `ValidationError400`; the
   empty/no-domain case makes `to_dict(orient="records")[0]` (`app.py:123-125`) raise `IndexError` →
   cryptic 400; the outer `try/except` (`app.py:100-102`) logs every such user-400 at `error` with a
   full traceback. Minor inaccuracy in the finding: `SADIEPredictResponseResult(**r)` (`app.py:130`)
   is *outside* the try block, so that one example is mischaracterized — but it does not change the
   verdict; the core claim is demonstrable.

3. **PascalCase response fields vs snake_case house norm — REAL.** `schema.py:140/143/146` declare
   `Chain`/`Numbering`/`Insertion` (PascalCase) with no Pydantic `alias` (grep: none) and
   `ResponseModel` has no `alias_generator` (`commons/model/pydantic.py:38-41`), so they ship verbatim
   against otherwise-snake_case fields; `app.py:126` `r["e_value"] = r["e-value"]` confirms the ad-hoc
   key bridge.

4. **Fabricated, self-contradicting SADIE acronym in shipped docs — REAL.** `README.md:7` and
   `MODEL.md:7` say "Sequence Analysis and Domain Identification Engine"; `LICENSE:25-26` and
   `sources.yaml:20` say "Sequencing Analysis and Data Library for Immunoinformatics Exploration";
   `README.md:231,237` (BibTeX) give a third title. The README/MODEL expansion contradicts the model's
   own LICENSE/sources and is the fabricated one.
