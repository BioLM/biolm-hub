# Maintainer launch checklist — the needs-human / infra items

> Consolidated list of everything that requires **you (the maintainer)** before the public launch —
> things an agent cannot decide or do. Compiled 2026-06-30 (session `oss-w3b-wsec`) from the Round-1
> review + W-sec sweep. Code-side work is tracked separately in `REMAINING_WORK.md`. Internal doc,
> deleted at launch — copy what you need out first.

## A. Licenses — confirm before launch (none are copyleft; these are attribution/accuracy)
The catalog is **permissive** (the only copyleft candidate, `peptides`, was dropped). No model ships a
GPL/copyleft license. Remaining items are attribution obligations and inferred metadata to confirm:

- [ ] **esmc** — honors Cambrian-Open "Built with ESM" attribution + naming in its per-model LICENSE.
      Confirm the wording matches the upstream ESM Open Model License agreement.
- [ ] **pro1** — LICENSE asserts Apache-2.0 (per the HF model card; the GitHub repo has no LICENSE file)
      AND notes the **Llama-3.1-8B base** under Meta's Llama Community License. Confirm both are acceptable
      for redistribution (Meta's license has use-based restrictions).
- [ ] **igbert / igt5** — CC-BY-4.0: confirm the attribution (author/citation) in each LICENSE is correct.
- [ ] **tempro — REAL LEGAL DECISION.** Upstream (github.com/Jerome-Alvarez/TEMPRO) ships **no LICENSE**
      (GitHub API: `license: null`) → default copyright, **all rights reserved**. Per your Round-1 call we
      KEEP it with an explicit honest notice (not a fabricated MIT) — `models/tempro/LICENSE` already says
      "No upstream license found … all rights reserved." **But:** if tempro's weights are hosted in
      `biolm-public` (self-population), that's redistribution of all-rights-reserved weights. Decide:
      (a) accept the risk, (b) get the author's permission/relicense, or (c) drop tempro like peptides.
- [ ] **prody — transitive GPL system dep.** prody's own code is MIT, but it uses **OpenBabel (GPL-2.0)**,
      apt-installed at build time (not vendored, used as a tool). Confirm this "system-library / mere-
      aggregation" use is acceptable for your permissive-catalog stance (same class of call you made when
      EXCLUDING `diamond` for cleanliness — prody differs in that OpenBabel is optional + not redistributed).
- [ ] **Inferred copyright holders/years** across many per-model LICENSEs (flagged in-file) — Batch B/E/F +
      chai1/rf3/boltzgen/abodybuilder3/immunebuilder/etc. Spot-confirm the holders aren't wrong.

## B. Public-facing contacts (placeholders that must be real)
- [ ] **`SECURITY.md:8`** — security report goes to **security@biolm.ai**. Confirm it's a real, monitored
      inbox (or replace). Has a `<!-- maintainers: confirm -->` marker.
- [ ] **`CODE_OF_CONDUCT.md:32`** — CoC enforcement contact **conduct@biolm.ai**. Same: confirm/replace.

## C. Knowledge-base PDFs in R2 (Milestone B / pre-launch)
- [ ] Confirm `biolm-public` holds **no raw third-party paper PDFs**. `sources.yaml` files carry internal
      `*_r2` paths pointing at paper PDFs; the docs generator does NOT render those, but verify none of the
      raw PDFs were uploaded to the now-anonymously-readable bucket. (Can only be checked with R2 access.)

## D. Infra / permissions (you provision; gates Milestone B + launch)
- [ ] **Modal CI token** — add **`MODAL_TOKEN_ID`** + **`MODAL_TOKEN_SECRET`** (same values as the internal
      `biolm-modal` repo) as **Environment secrets on the `modal-dev` GitHub Environment** of this repo (env-
      scoped — org secrets don't auto-apply). Plus `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` / `R2_REGION`
      / `R2_ENDPOINT` on the same environment (deploy.yml header lists them).
- [ ] **GitHub deploy-gate** — create the `deploy-approved` label + the `modal-dev` Environment with required
      reviewers (deploy.yml is maintainer-gated `pull_request_target`).
- [ ] **R2 anonymous read** — ✅ DONE (you enabled the bucket Public Development URL
      `https://pub-c56611cf24404740b0ff53b356a6b48d.r2.dev`; the read path is implemented). The remaining
      code follow-up (make the `cloudflare-r2` secret mount optional so a creds-less deploy can start) is an
      agent task, Modal-gated → Milestone B.
- [ ] **Unused Modal secrets** (optional cleanup) — `protocols-r2-bkt` is no longer referenced by any code;
      you can delete it from the Modal workspace. (`ngc-cli-api-key` likewise — NIM models excluded.)

## E. The biolm-hub rebrand (deferred to just-before-launch, per your call)
See `.planning/RENAME_TO_BIOLM_HUB.md` for the full pre-computed checklist. At launch:
- [ ] Create the **`BioLM/biolm-hub`** GitHub repo (it doesn't exist yet — create, don't rename).
- [ ] Apply the in-repo identity sweep (repo name strings, `pip install` examples, docs/README titles,
      per-model LICENSE headers) + **CLI `bm` → `bh`**.
- [ ] Create Modal envs **`biolm-hub`** (prod) + **`biolm-hub-dev`** (dev), copy the `cloudflare-r2` +
      `hf-api-token` secrets into them, update the GitHub `modal-dev` Environment, stop old `biolm-models-dev`
      apps.
- [ ] **Re-path the `biolm-public` bucket** under a `biolm-hub/` prefix (mirror the repo tree) — do this
      BEFORE any real Milestone-B weight writes, else weights land under the old prefix and need migration.

## F. W-launch irreversible sequence (after all the above)
- [ ] R2 completeness sweep + final security sign-off → delete `.planning/` → nuke git history → flip the
      repo public (gated on marketing material being ready).
</content>
