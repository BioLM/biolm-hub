# {Model Display Name}  --  Biological Context

<!-- Template instructions (delete this block when populating):
     This document provides biological context for the model  --  what areas of
     biology it covers, what problems it can address, and how it has been
     applied in practice.

     This is aimed at scientists and domain experts who want to understand
     the biological relevance, not just the API.

     TODO format (use consistently across all docs):
       <!-- TODO: [Action to take]  --  [Where to find the info] -->

     Primary sources:
     - sources.yaml applied_literature entries for real-world use cases
     - sources.yaml primary_papers for the model's own biological claims
     Access via:
       bm r2 cat r2://biolm-public/knowledge-base/models/{slug}/applied/papers-md/{paper}.md
-->

## Molecule Coverage

### Primary Molecule Type(s)

<!-- What biological molecules is this model designed for?
     Be specific  --  don't just say "proteins". Clarify:
     - Globular proteins? Membrane proteins? Disordered regions?
     - Single-chain or multi-chain?
     - What organism groups? (all organisms, bacterial only, human, etc.)
     - What sequence identity range to training data matters?

     Example:
     "ESM2 is trained on UniRef50, covering proteins from all domains of life.
     It handles single-chain globular proteins best. Performance degrades for:
     - Membrane proteins (under-represented in training)
     - Intrinsically disordered regions (poor contact prediction)
     - Very long sequences (>1022 residues truncated)"
-->

### Cross-Applicability

<!-- Can this model be applied to molecule types beyond its primary design?
     This is especially important for general-purpose protein models that
     may also work for antibodies, enzymes, peptides, etc.

     For each cross-application, describe:
     - Whether it has been tested on this molecule type
     - Expected performance relative to specialized models
     - Any known caveats

     Example format:
     | Molecule Type | Applicability | Evidence | Caveats |
     |--------------|---------------|----------|---------|
     | Antibodies | Moderate | CDR embedding quality shown in [Paper X] | Variable region only; constant region ignored |
     | Enzymes | High | Active site prediction validated in [Paper Y] | No explicit catalytic mechanism modeling |
     | Peptides | Low | Short sequences lose positional context | Consider peptide-specific models instead |
-->

## Biological Problems Addressed

<!-- For each biological problem this model can help with, describe:
     1. The problem in biological terms (what question is being answered?)
     2. How this model contributes to solving it
     3. What the output means biologically
     4. Practical considerations (accuracy, speed, complementary tools)

     Organize by problem type. Include enough biological context for a
     computational biologist who may not be a domain expert.
-->

### {Problem 1}: {e.g., Protein Stability Prediction}

<!-- Description of the biological problem:
     - Why is this important? (drug development, protein engineering, etc.)
     - What experimental methods traditionally address this?
     - What are the limitations of experimental approaches?

     How this model addresses it:
     - What input does it need?
     - What does the output represent biologically?
     - How accurate is it compared to experiment?
     - What are the practical implications?
-->

### {Problem 2}: {e.g., Variant Effect Prediction}

<!-- Same structure as above. Add as many problem sections as applicable. -->

## Applied Use Cases

<!-- Real-world applications from the applied literature (sources.yaml).
     These are examples of HOW researchers have used this model in practice.

     For each use case, include:
     - Paper/blog reference (with link)
     - Biological context (what was the research question?)
     - How the model was used (embeddings? predictions? as a baseline?)
     - Key results (quantitative if available)
     - Relevance to BioLM users
-->

### {Use Case 1}: {e.g., Antibody Developability Screening}

**Source**: Author et al. "Paper title." *Venue* (Year). [DOI](URL)

<!-- Describe:
     - The biological question
     - How this model was applied
     - Key findings relevant to users of this model
     - Any limitations identified
-->

### {Use Case 2}: {e.g., Enzyme Engineering for Industrial Applications}

**Source**: Author et al. "Paper title." *Venue* (Year). [DOI](URL)

<!-- Same structure. Add as many use cases as found in applied literature. -->

## Related Models

### Predecessor Models

<!-- Models that this model builds upon or replaces:
     - What came before? (e.g., ESM-1b preceded ESM-2)
     - What was improved?
     - Is the predecessor still useful for any tasks?
-->

### Complementary Models

<!-- Models on the BioLM platform that are often used together with this one:
     - e.g., "Use ESM2 embeddings as input to ESMStabP for stability prediction"
     - e.g., "Use Boltz for structure, then MPNN for sequence design"
     - Include the typical pipeline or workflow
-->

### Alternative Models

<!-- Models that solve the same or similar problems:
     - When to choose this model vs the alternative
     - Key tradeoffs (accuracy vs speed, generality vs specialization)

     | Alternative | Advantage over this model | Disadvantage |
     |-------------|--------------------------|--------------|
     | Model X | Faster inference | Lower accuracy on benchmark Y |
     | Model Y | Handles longer sequences | Requires MSA input |
-->

## Biological Background

<!-- Domain primer for non-specialists. This section should give enough
     context for a computational scientist (not a biologist) to understand
     the biological relevance of this model.

     Cover:
     - What is the molecule type? (e.g., "Proteins are chains of amino acids...")
     - What is the key biological property being modeled?
     - Why does this matter? (disease, drug development, agriculture, etc.)
     - Key terminology defined

     Keep this accessible but not oversimplified. Aim for a PhD-level
     computational scientist who may be new to this specific subdomain.

     For protein models:
     - Protein function, folding, structure-function relationship
     - Relevant to: drug discovery, enzyme engineering, diagnostics

     For antibody models:
     - Antibody structure (VH/VL, CDRs, framework regions)
     - Relevant to: therapeutic antibody design, immunology

     For DNA/RNA models:
     - Gene regulation, promoters, enhancers, variant effects
     - Relevant to: genomics, gene therapy, synthetic biology
-->

---

*See also: [README.md](README.md) for API reference | [MODEL.md](MODEL.md) for technical details*
