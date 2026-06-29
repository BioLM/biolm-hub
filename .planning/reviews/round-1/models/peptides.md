# Review — `models/peptides/` (Round 1)

## Summary

`peptides` is the repo's simplest model: a CPU-only, weightless wrapper around the PyPI
`peptides==0.3.4` library that exposes a single `encode` action returning a free-form dict of
physicochemical features. The plumbing is clean and conforms well to the house pattern — correct
`ModelFamily`/`ActionSchemaMap`, canonical `encode` verb, `setup_source_layer` (no weights, so no
`download.py`/`r2_then_*` is appropriate), structured logging with no `print`, strict Pydantic
request/response models whose field descriptions all render (the schema-docs checker passes), and a
`TestSuite` with integration + deployment cases and no module-scope R2 access.

The serious problem is **licensing/attribution**: the model installs and wraps *althonos/peptides.py*
(by Martin Larralde) but documents and licenses it as a different project — *dosorio/Peptides.py* by
Daniel Osorio — under **Apache-2.0**. The installed package's own source declares `__license__ =
"GPLv3"` and ships a GPLv3 `COPYING` (its PyPI metadata inconsistently says MIT). So both the license
identity and the copyright holder are wrong, and the real license may be copyleft — which would
conflict with the repo's permissive-only inclusion policy. This is launch-gating.

Beyond that: one fabricated feature count ("557") in `comparison.yaml`, a `display_name`
inconsistency, and a few minor doc/code nits. I empirically verified library behavior with
`peptides==0.3.4` (method names, feature counts, numpy types, extended-alphabet handling).

---

## 🔴 Must-fix

### 1. Wrong upstream license **and** wrong code attribution; possible copyleft (GPLv3) dependency
**Category:** Licensing · **Location:** `models/peptides/LICENSE` (whole file, esp. 174–183),
`models/peptides/sources.yaml:3-6,27-34`, `models/peptides/README.md:184-188,213`,
`models/peptides/MODEL.md:9`

`app.py:32` installs `peptides==0.3.4`. That PyPI package is **althonos/peptides.py by Martin
Larralde** (`martin.larralde@embl.de`, home-page `https://github.com/althonos/peptides.py`), an
independent Python reimplementation — *not* a "Python port … by Osorio et al." Verified from the
installed distribution:

- `peptides/__init__.py` → `__license__ = "GPLv3"`
- `peptides-0.3.4.dist-info/COPYING` → full **GNU GPL v3** text (`License-File: COPYING`)
- `METADATA` → `License: MIT` + MIT OSI classifier  ← contradicts the COPYING/`__license__`

The model instead ships:
- `LICENSE`: the full **Apache-2.0** text, with an attribution note crediting "Daniel Osorio, Paola
  Rondon-Villarreal, and Rodrigo Torres" and `github.com/dosorio/Peptides.py`.
- `sources.yaml`: `license.type: "Apache-2.0"`, `license.url:
  https://github.com/dosorio/Peptides.py/blob/master/LICENSE`, `source_repos[0].url:
  https://github.com/dosorio/Peptides.py`, notes "Python port of the R Peptides package".
- `README.md`: "Code: Apache-2.0", "Library: Apache-2.0", GitHub link to `dosorio/Peptides.py`.
- `MODEL.md:9`: "wraps the `peptides` Python package (v0.3.4), which is a Python port of the original
  R `Peptides` package by Osorio et al."

So the license identity (Apache-2.0) is wrong no matter how the upstream MIT-vs-GPLv3 ambiguity
resolves, and the copyright holder/repo is the wrong project. The R `Peptides` package by Osorio is a
*separate* CRAN package; Osorio is the right citation for the scientific scales (the 2015 R Journal
paper) but **not** the author or licensor of the code being wrapped.

Why it's launch-gating: the inclusion matrix lists peptides as "Apache-2.0 | SHIP" and the rubric
requires a permissive license (MIT/Apache/BSD/CC-BY). If the true upstream license is **GPLv3**
(strong copyleft), peptides likely fails that criterion and cannot ship as-is; distributing a
service that links the GPLv3 library together with the wrapper raises copyleft obligations.

**Fix:**
1. Resolve the upstream license with the maintainer — the package is self-contradictory (`__license__`
   + `COPYING` say GPLv3; metadata says MIT). Cite the resolution.
2. If GPLv3 is confirmed, escalate to the inclusion-matrix owner — copyleft conflicts with the
   permissive-only policy (re-evaluate SHIP, or pin an MIT-licensed alternative/version).
3. Replace `LICENSE` with the actual upstream license text and the correct holder (Martin Larralde /
   althonos), keeping the scientific citation to Osorio separate.
4. Correct `sources.yaml` (`license.type`, `license.url`, `source_repos[].url` → `althonos/peptides.py`;
   drop/reword "Python port … by Osorio"), `README.md` (License section + GitHub link), and
   `MODEL.md:9` accordingly. Credit Osorio for the *scales/paper*, Larralde for the *code*.

---

## 🟠 Should-fix

### 2. Fabricated "557 features/descriptors" count
**Category:** Docs accuracy · **Location:** `models/peptides/comparison.yaml:6,45`

`comparison.yaml` claims the model "Computes 557 physicochemical descriptors" (line 6) and "provides
557 features" (line 45). Empirically with `peptides==0.3.4`: `descriptors()` returns **102** keys,
`frequencies()` returns **26**, plus **10** scalar features and **3** profile vectors = **~138**
feature keys (no key collisions when flattened). "557" is unsupported and ~4× too high. README and
MODEL.md sensibly avoid a hard count, so this is isolated to `comparison.yaml`.
**Fix:** replace "557" with an accurate figure (~130–140) or qualitative wording, or drop the number.

### 3. `display_name` inconsistent across knowledge-graph vs config
**Category:** Consistency · **Location:** `models/peptides/comparison.yaml:2` vs `config.py:60` /
`schema.py:18` / `sources.yaml:2`

`comparison.yaml` uses `display_name: Peptides` (capitalized) while `config.py`, `schema.py`
(`PeptidesParams.display_name = "peptides"`) and `sources.yaml` use lowercase `peptides`. Rubric A9
requires display_name to match config. Separately, lowercase "peptides" is an odd "full,
human-readable name" (esm2 → "ESM2", dummy → "Dummy").
**Fix:** standardize on one form. Recommend "Peptides" everywhere and update
`PeptidesParams.display_name` to "Peptides" to match the capitalization convention of the other
families (verify nothing keys off the lowercase string).

---

## 🟡 Nits

### 4. Stray markdown artifact in MODEL.md glossary
**Category:** Docs · **Location:** `models/peptides/MODEL.md:182`

"…principal component analysis of 18 hydrophobicity scales, **##** steric parameters, and electronic
properties." — a leftover `## ` sits mid-sentence. **Fix:** delete `## `.

### 5. No reproducible fixture-generation path (diverges from house pattern)
**Category:** Tests / uniformity · **Location:** `models/peptides/fixture.py`

`fixture.py` defines only filename constants; the comment says expected outputs are "manually created
and stored in R2". esm2's `fixture.py` has `_build_fixture_generation_suite()` + `generate()` so
fixtures can be regenerated, and CLAUDE.md's ground rules say "generate fixtures first". Low risk
because the model is deterministic, but it's a plumbing divergence ("the diff should be the science").
**Fix:** add a `generate()` that recomputes the expected outputs from the model (mirroring esm2), or
explicitly document why hand-authored fixtures are acceptable here.

### 6. float32 downcast applied inconsistently; redundant first conversion pass
**Category:** Correctness/readability · **Location:** `models/peptides/app.py:80-90,124-129`

`_convert_value` rounds numpy scalars to float32 precision (`float(np.float32(obj))`), but profile
vectors come back as `array.array` of Python `float` (float64) and pass through `_convert_value`
unchanged — so scalars are float32-rounded while profiles keep full float64 precision. README:166 /
MODEL.md state "all numpy float values converted to float32," which doesn't match the profile path.
Also, in the main loop a vector feature is first stored via `_convert_value(array.array)` (a no-op,
since `array.array` is neither `np.floating`/`list`/`dict`) and then re-processed in the
`if include_vectors:` block — a redundant pass.
**Fix:** apply the float conversion uniformly (or document the intended difference) and drop the
redundant first pass by converting profiles to lists in one place.

### 7. Primary-source knowledge-graph fields left as `pending`/empty
**Category:** Knowledge graph completeness · **Location:** `models/peptides/sources.yaml:16,25,30,31`

The *primary* paper has `arxiv: ""` and `md_r2: "pending"`, and `source_repos` has `commit: ""` and
`snapshot_r2: "pending"`. esm2's primary section carries real values (the `applied_literature`
`pending` entries are the accepted convention, so only the primary section is the gap). The
`source_repos[0].url` also points at the wrong project (see finding 1).
**Fix:** populate the primary `md_r2`/repo `commit`/`snapshot_r2` (or remove the keys), and point the
repo at `althonos/peptides.py`.

### 8. Free-form `dict[str, Any]` response gives consumers no typed/enumerated key contract
**Category:** Schema design · **Location:** `models/peptides/schema.py:68-77`

`PeptidesEncodeResponseResult.features: dict[str, Any]` is a reasonable choice for ~138 heterogeneous
keys (and `OutputModality.DICTIONARY` is a sanctioned tag), but it means the OpenAPI schema enumerates
no keys — README is the only contract for which features appear. Acceptable as-is; flagging so the
maintainer can decide whether to document the key set as a stable contract.
**Fix (optional):** none required; consider listing the canonical key set in README as the stable
contract, or note that keys track the upstream library version.

### 9. "QA" deploy-environment mention (systemic, not peptides-specific)
**Category:** Internal leakage · **Location:** `models/peptides/app.py:139`

`# Force deploy to QA or main:` mirrors `models/commons/modal/deployment.py` (and esm2's app.py),
where `qa`/`main` are Modal environment names. The rubric lists an internal `qa` env as a leak, but
this is repo-wide boilerplate from commons, not specific to peptides. Flagging for the global
reviewer rather than as a peptides defect.
**Fix:** address centrally in commons if `qa` is deemed internal-only (out of scope for this model).

---

## Definition-of-Done audit (peptides scope)

- **Standard layout (A1):** met — all files present; no `download.py` is correct (no weights).
- **Actions (A2):** met — single `encode`, matches intent.
- **Schema field names/descriptions (A3/A4):** met — `items`/`params`/`sequence`/`results`; all
  descriptions render; `tooling/check_schema_docs.py --model peptides` → "schema docs OK".
- **Errors (A5):** met — input validation via commons `validate_aa_extended` (Pydantic
  BeforeValidator → framework UserError); library handles all valid inputs without raising (verified,
  including the extended `BXZUO` alphabet → no crash).
- **Logging (A6):** met — `get_logger`, no `print`.
- **Acquisition (A7):** N/A (weightless pip package); `setup_source_layer` only — correct.
- **Licensing (A8):** **NOT met** — see 🔴 #1.
- **Knowledge graph (A9):** partially met — present and mostly consistent, but `display_name`
  mismatch (#3), fabricated "557" (#2), `pending`/empty primary fields (#7), and wrong code
  attribution (#1).
- **Tests (A10):** met — `TestSuite` with integration + deployment cases; no module-scope R2.

## Verification

Adversarial re-check of the three HIGH-severity findings against the actual files and the real
`peptides==0.3.4` distribution (downloaded sdist + built/installed in a clean venv).

- **#1 Wrong upstream license/attribution; possible GPLv3 copyleft — REAL.** PyPI/sdist for
  `peptides==0.3.4` is `althonos/peptides.py` by Martin Larralde (PKG-INFO `author: Martin Larralde`,
  `home_page: github.com/althonos/peptides.py`), an independent reimplementation — NOT a "Python port
  by Osorio et al." The installed `peptides/__init__.py:25` sets `__license__ = "GPLv3"`; the dist
  ships `COPYING` = full GNU GPL v3 text with `License-File: COPYING` (PKG-INFO:37), while PKG-INFO:8
  inconsistently says `License: MIT`. Apache-2.0 is wrong either way. The model instead ships full
  Apache-2.0 text attributed to Osorio/dosorio across LICENSE:174-183, sources.yaml:3-6,29,34,
  README.md:186-187,213, MODEL.md:9 — wrong license and wrong code author/repo.
- **#2 Fabricated "557 features" — REAL.** Built `peptides==0.3.4` and replicated `app.py`'s flatten:
  `descriptors()` = 102 keys, `frequencies()` = 26, 10 scalar numerics → 138 numeric-only feature
  keys (141 incl. the 3 profile vectors). comparison.yaml:6 ("557 physicochemical descriptors") and
  comparison.yaml:45 ("557 features") are ~4x too high and unsupported; README/MODEL.md avoid a hard
  count.
- **#3 display_name inconsistent — REAL.** comparison.yaml:2 `display_name: Peptides` (capital P)
  vs canonical `schema.py:18 PeptidesParams.display_name = "peptides"` (used by config.py:60 and
  sources.yaml:2), all lowercase. Genuine mismatch (A9). The "odd human-readable name" point is a
  secondary stylistic observation, but the inconsistency itself is demonstrable.
