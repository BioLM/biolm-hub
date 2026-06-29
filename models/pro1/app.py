import re

import modal

from models.commons.core.decorator import modal_endpoint
from models.commons.core.error import UserError
from models.commons.core.logging import get_logger
from models.commons.data.validator import aa_unambiguous
from models.commons.modal.downloader import setup_download_layer
from models.commons.modal.source import setup_source_layer
from models.commons.model.base import ModelMixin
from models.commons.model.config import biolm_model_class
from models.commons.util.config import (
    cloudflare_r2_secret,
    common_requirements,
    huggingface_api_token_secret,
)
from models.commons.util.environment import parse_variant
from models.pro1.config import (
    MODEL_FAMILY,
    PRO1_VARIANT_TO_HF_CONFIG,
    get_build_gpu,
)
from models.pro1.schema import (
    Pro1GenerateParams,
    Pro1GenerateRequest,
    Pro1GenerateResponse,
    Pro1GenerateResult,
    Pro1MutationProposal,
    Pro1Params,
    Pro1Variant,
)

logger = get_logger(__name__)

variant_config = parse_variant(
    env_var_name="MODEL_VARIANT",
    allowed_values=Pro1Variant,
    default=Pro1Variant.SIZE_8B,
)
model_variant = Pro1Variant(variant_config["MODEL_VARIANT"])

# Build the CUDA base image matching source repo setup.sh:
#   pip install unsloth vllm==0.8.2
#   pip install --force-reinstall --no-cache-dir --no-deps git+https://github.com/unslothai/unsloth.git
build_gpu = get_build_gpu(model_variant)
image = (
    modal.Image.from_registry(
        "pytorch/pytorch:2.6.0-cuda12.4-cudnn9-devel",
        add_python="3.11",
    )
    .apt_install("procps", "git")
    .uv_pip_install(common_requirements)
    .uv_pip_install(
        [
            # transformers 4.51.3 requires huggingface_hub>=0.30
            "huggingface_hub==0.30.2",
            # unsloth execs transformers source; 4.52+ added auto_docstring which breaks exec
            "transformers==4.51.3",
            "peft==0.14.0",
            "accelerate==1.3.0",
            # 0.45.0 imports `triton.ops` which was removed in triton>=3.0;
            # 0.46.0+ made the triton import lazy.
            "bitsandbytes==0.46.1",
            "triton==3.1.0",
            "trl==0.13.0",
        ]
    )
    # Step 1: install vLLM (source setup.sh: pip install unsloth vllm==0.8.2)
    .uv_pip_install(
        ["vllm==0.8.2"],
        gpu=build_gpu,
        extra_options="--no-build-isolation",
    )
    # Step 2: install unsloth + unsloth_zoo without deps to avoid conflicts
    # (source setup.sh: pip install --force-reinstall --no-cache-dir --no-deps git+https://github.com/unslothai/unsloth.git)
    .uv_pip_install(
        ["unsloth==2025.3.19", "unsloth_zoo==2025.3.17"],
        extra_options="--no-deps",
    )
)

# Setup download layer with model weights
image = setup_download_layer(
    image,
    base_model_slug=Pro1Params.base_model_slug,
    weights_version=Pro1Params.weights_version,
    variant_config=variant_config,
)
# Add all model source files
image = setup_source_layer(MODEL_FAMILY.base_model_slug)(image)

# Define the app using MODEL_FAMILY config
app_name, modal_resource_spec = MODEL_FAMILY.get_app_config(**variant_config)
logger.info("App name: %s", app_name)
app = modal.App(app_name, image=image)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_AA = set(aa_unambiguous)
_AA_RE = f"[{aa_unambiguous}]"
_MUTATION_RE = re.compile(rf"\b({_AA_RE})(\d{{1,4}})({_AA_RE})\b")


def _build_prompt(item) -> str:
    """Build the Llama-chat-formatted prompt from a Pro1ProteinData item."""
    seq = item.sequence

    # Format reaction
    if item.reaction:
        rxn = item.reaction[0]
        substrates = ", ".join(rxn.substrates) if rxn.substrates else "None"
        products = ", ".join(rxn.products) if rxn.products else "None"
    else:
        substrates = "None"
        products = "None"

    # Format metal ions and active site residues
    metal_ions = ", ".join(item.metal_ions) if item.metal_ions else "None"
    active_sites = (
        ", ".join(item.active_site_residues) if item.active_site_residues else "None"
    )

    # Format known mutations
    if item.known_mutations:
        known_muts = ", ".join(
            f"{m.mutation} ({m.effect})" for m in item.known_mutations
        )
    else:
        known_muts = "None"

    base_prompt = (
        "You are an expert protein engineer in rational protein design. "
        "You are working with a protein sequence given below, as well as other useful information "
        "regarding the enzyme/reaction (if applicable): \n\n"
        f"PROTEIN NAME: {item.name or 'Unknown'}\n"
        f"EC NUMBER: {item.ec_number or 'Unknown'}\n"
        f"PROTEIN SEQUENCE: {seq}\n"
        f"SUBSTRATES: {substrates}\n"
        f"PRODUCTS: {products}\n"
        f"GENERAL INFORMATION: {item.general_information or 'No additional information available'}\n"
        f"METALS/IONS: {metal_ions}\n"
        f"ACTIVE SITE RESIDUES (DO NOT MODIFY): {active_sites}\n"
        f"KNOWN MUTATIONS: {known_muts}\n\n"
        "Propose NOVEL mutations to optimize the stability of the protein given the information above. "
        "If applicable, be creative with your modifications, including insertions or deletions of sequences "
        "that may help improve stability (make sure to have good reasoning for these types of modifications). "
        "Ensure that you preserve the activity or function of the protein as much as possible.\n\n"
        "****all reasoning must be specific to the protein and reaction specified in the prompt. "
        "cite scientific literature. consider similar proteins and reactions****\n\n"
        "Provide detailed reasoning for each mutation, including the position number and the amino acid change "
        "(e.g., A23L means changing Alanine at position 23 to Leucine).\n"
        r"Return the modified sequence with all changes applied correctly in the \boxed{} tag. "
        r"ex. \boxed{MGYARRVMDGIGEVAV...}. DO NOT INCLUDE ANY OTHER TEXT OR FORMATTING WITHIN THE BRACKETS. "
        r"IT IS CRUCIAL YOU APPLY THE MUTATIONS CORRECTLY AND RETURN THE MODIFIED SEQUENCE in the \boxed{} tag."
    )

    # Llama 3 chat template (matches the fine-tuning format used in pro-1 setup.sh).
    prompt = (
        "<|start_header_id|>system<|end_header_id|>\n"
        "You are a helpful assistant that helps users with protein engineering tasks. "
        "You first think about the reasoning process and then provide the answer. "
        "The reasoning process and answer should be enclosed within <think> </think> and "
        "<answer> </answer> tags respectively. Think deeply and logically. "
        "<|eot_id|><|start_header_id|>user<|end_header_id|>\n"
        f"{base_prompt}"
        "<|eot_id|><|start_header_id|>assistant<|end_header_id|>"
    )
    return prompt


def _extract_sequence(response: str) -> str | None:
    """Extract modified sequence from model response.

    Tries `\\boxed{...}` first (the format Pro-1 was fine-tuned on), then a
    bare `boxed{...}` fallback, then an `<answer>...</answer>` block. Returns
    None if nothing parses — caller falls back to the deterministic mutation
    applier.
    """
    boxed = re.findall(r"\\boxed\{([A-Z]+)\}", response)
    if boxed:
        return boxed[-1].strip()

    # Bare `boxed{...}` (negative lookbehind avoids re-matching `\boxed{...}`).
    boxed_alt = re.findall(r"(?<!\\)boxed\{([A-Z]+)\}", response)
    if boxed_alt:
        return boxed_alt[-1].strip()

    # <answer>...</answer> fallback. Bound the search and use a single re.search
    # to avoid pathological backtracking on 8k-token responses.
    answer_match = re.search(r"<answer>[\s\S]{0,16000}?([A-Z]{10,})", response)
    if answer_match:
        return answer_match.group(1).strip()

    return None


def _apply_mutations_deterministically(
    original: str, mutations: list[str]
) -> str | None:
    """Apply a list of standard-notation mutations (e.g. K116E) to the original sequence."""
    mutation_pat = re.compile(rf"({_AA_RE})(\d+)({_AA_RE})")
    seq = list(original)
    applied = 0
    for mut in mutations:
        m = mutation_pat.match(mut.strip())
        if not m:
            continue
        wt, pos_str, sub = m.group(1), m.group(2), m.group(3)
        pos = int(pos_str) - 1  # 0-indexed
        if pos < 0 or pos >= len(seq):
            continue
        if seq[pos] != wt:
            continue  # WT doesn't match — skip to avoid misapplying
        seq[pos] = sub
        applied += 1
    if applied == 0:
        return None
    return "".join(seq)


def _parse_mutations_from_reasoning(reasoning: str) -> list[dict]:
    """
    Extract mutation proposals and rationale from reasoning text.

    Restricts the wild-type and substitute letters to the 20 standard
    single-letter AA codes (avoids matching non-AA uppercase letters like
    B/J/O/U/X/Z, version strings such as 'L3.1B', etc.).
    """
    results = []
    seen = set()
    mut_pat = _MUTATION_RE

    for m in mut_pat.finditer(reasoning):
        wt, pos, sub = m.group(1), m.group(2), m.group(3)
        if wt == sub:
            continue  # Skip synonymous
        mut_str = f"{wt}{pos}{sub}"
        if mut_str in seen:
            continue
        seen.add(mut_str)

        # Extract ~200 chars of context around the mutation for rationale
        start = max(0, m.start() - 100)
        end = min(len(reasoning), m.end() + 200)
        context = reasoning[start:end].strip()
        # Clean up the context snippet
        context = re.sub(r"\s+", " ", context)

        results.append({"mutation": mut_str, "rationale": context})

    return results


# ---------------------------------------------------------------------------
# Modal App Class
# ---------------------------------------------------------------------------


# NOTE: Memory snapshots are disabled for Pro-1.
# unsloth's in-place model patching + bitsandbytes 4-bit CUDA quantization
# context aren't snapshot-compatible on Modal — snapshot creation fails
# repeatedly in the background even though requests are still served.
# E1 disables snapshots for the same family of reasons (see models/e1/app.py).
# Trade-off: slower cold start (~3 min vs ~30 s with snap) but reliable startup.


@app.cls(
    image=image,
    secrets=[cloudflare_r2_secret, huggingface_api_token_secret],
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class Pro1Model(ModelMixin):
    """Pro-1 protein reasoning model for stability engineering."""

    app_username: str = modal.parameter(default="default_user")

    @modal.enter()
    def setup_model(self) -> None:
        """Load Pro-1 model + LoRA adapter into GPU memory."""
        import os
        import time
        from pathlib import Path

        from unsloth import FastLanguageModel

        from models.commons.storage.downloads import setup_hf_cache_env
        from models.pro1.download import get_model_dir

        variant = Pro1Variant(
            os.environ.get("MODEL_VARIANT", Pro1Variant.SIZE_8B.value)
        )
        base_model, adapter_subfolder = PRO1_VARIANT_TO_HF_CONFIG[variant]

        model_dir = Path(get_model_dir())
        setup_hf_cache_env(model_dir)

        t0 = time.time()
        logger.info("Loading Pro-1 (%s) base model: %s", variant, base_model)
        # NOTE: unsloth's `fast_inference=True` (vLLM backend) refuses to load
        # Llama-3.1 because it has RoPE scaling, so we use unsloth's standard
        # 4-bit HF inference path. vLLM is still installed (a transitive build
        # dep we cannot drop without breaking unsloth_zoo), but unused at runtime.
        self.model, self.tokenizer = FastLanguageModel.from_pretrained(
            model_name=base_model,
            max_seq_length=32768,
            load_in_4bit=True,
            max_lora_rank=32,
        )

        adapter_path = model_dir / "adapter" / adapter_subfolder
        logger.info("Loading LoRA adapter: %s", adapter_path)
        self.model.load_adapter(str(adapter_path))
        FastLanguageModel.for_inference(self.model)
        logger.info(f"Pro-1 ({variant}) loaded and ready ({time.time() - t0:.1f}s)")

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def generate(self, payload: Pro1GenerateRequest) -> Pro1GenerateResponse:
        """Generate stability-improving mutations for a protein sequence."""
        import random
        import time
        import traceback

        import numpy as np
        import torch

        item = payload.items[0]
        params: Pro1GenerateParams = payload.params
        prompt = _build_prompt(item)

        # Seed all RNG sources (matches evo / progen2 reproducibility pattern).
        seed = params.seed if params.seed is not None else int(time.time_ns() % (2**32))
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        logger.debug("Prompt token count: %s", inputs["input_ids"].shape[1])

        results = []
        last_error: str | None = None
        for iteration in range(params.max_iterations):
            logger.info("=== Iteration %s/%s ===", iteration + 1, params.max_iterations)
            try:
                t_gen = time.time()
                logger.info("Generating...")
                with torch.no_grad():
                    output_ids = self.model.generate(
                        **inputs,
                        max_new_tokens=params.max_new_tokens,
                        temperature=params.temperature,
                        top_p=params.top_p,
                        do_sample=True,
                    )
                new_ids = output_ids[0, inputs["input_ids"].shape[1] :]
                response = self.tokenizer.decode(new_ids, skip_special_tokens=True)
                logger.info(
                    f"Generation done ({time.time() - t_gen:.1f}s) — {len(response)} chars"
                )

                parsed_mutations = _parse_mutations_from_reasoning(response)
                modified_seq = _extract_sequence(response)

                if modified_seq is None and parsed_mutations:
                    mut_strs = [p["mutation"] for p in parsed_mutations]
                    modified_seq = _apply_mutations_deterministically(
                        item.sequence, mut_strs
                    )
                    if modified_seq:
                        logger.info(
                            "Applied %s mutations deterministically", len(mut_strs)
                        )

                if modified_seq is not None:
                    invalid_aa = set(modified_seq) - _VALID_AA
                    if invalid_aa:
                        logger.warning(
                            "Invalid AA in extracted sequence: %s — discarding",
                            invalid_aa,
                        )
                        modified_seq = None
                    elif (
                        len(modified_seq) < 10
                        or len(modified_seq) < len(item.sequence) // 2
                    ):
                        logger.warning(
                            "Extracted sequence implausibly short (%d AA vs original %d AA) — discarding",
                            len(modified_seq),
                            len(item.sequence),
                        )
                        modified_seq = None

                mutation_proposals = [
                    Pro1MutationProposal(
                        mutation=p["mutation"], rationale=p["rationale"]
                    )
                    for p in parsed_mutations
                ]

                results.append(
                    Pro1GenerateResult(
                        reasoning=response,
                        mutations=mutation_proposals,
                        modified_sequence=modified_seq,
                    )
                )

            except Exception as e:
                # Keep the full exception in server-side logs; never echo
                # internal details (stack frames, library internals) to the
                # caller via UserError.
                last_error = type(e).__name__
                logger.error(
                    "Error in iteration %s: %s", iteration + 1, e, exc_info=True
                )
                logger.debug(traceback.format_exc())
                continue

        if not results:
            detail = f" (last failure: {last_error})" if last_error else ""
            raise UserError(
                f"Pro-1 produced no results across {params.max_iterations} "
                f"iteration(s){detail}"
            )
        return Pro1GenerateResponse(results=results)


if __name__ == "__main__":
    """
    Usage:
        MODEL_VARIANT="8b" python models/pro1/app.py

        # Force deploy to your target environment:
        MODEL_VARIANT="8b" python models/pro1/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        Pro1Model,
        description=f"Run and optionally deploy the {Pro1Params.display_name} {model_variant} Modal app.",
    )
