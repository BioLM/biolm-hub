# Copyright (c) 2022, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause

# type: ignore
# ruff: disable

import os
import random
import time

import torch
from tokenizers import Tokenizer

from models.progen2.external.modeling_progen import ProGenForCausalLM

"""
Adapted from: https://github.com/salesforce/progen/blob/main/progen2/sample.py

There is plenty of overlap with likelihood_utils.py, but they are kept separate
to stay close to the original code.
"""

########################################################################
# util


class print_time:
    def __init__(self, desc):
        self.desc = desc

    def __enter__(self):
        print(self.desc)
        self.t = time.time()

    def __exit__(self, type, value, traceback):
        print(f"{self.desc} took {time.time()-self.t:.02f}s")


def set_env():
    os.environ["TOKENIZERS_PARALLELISM"] = "false"


def set_seed(seed, deterministic=True):
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.backends.cudnn.deterministic = deterministic
        torch.backends.cudnn.benchmark = not deterministic


########################################################################
# model


def create_model(ckpt, fp16=True):
    if fp16:
        return ProGenForCausalLM.from_pretrained(
            ckpt, revision="float16", torch_dtype=torch.float16, low_cpu_mem_usage=True
        )
    else:
        return ProGenForCausalLM.from_pretrained(ckpt)


def create_tokenizer_custom(file):
    with open(file) as f:
        return Tokenizer.from_str(f.read())


########################################################################
# sample


def sample(
    device,
    model,
    tokenizer,
    context,
    max_length,
    num_return_sequences,
    top_p,
    temp,
    pad_token_id,
):

    with torch.no_grad():
        input_ids = torch.tensor(tokenizer.encode(context).ids).view([1, -1]).to(device)
        tokens_batch = model.generate(
            input_ids,
            do_sample=True,
            temperature=temp,
            max_length=max_length,
            top_p=top_p,
            num_return_sequences=num_return_sequences,
            pad_token_id=pad_token_id,
        )

        def as_lists(batch):
            return [
                batch[i, ...].detach().cpu().numpy().tolist()
                for i in range(batch.shape[0])
            ]

        return tokenizer.decode_batch(as_lists(tokens_batch))


def truncate(sample, terminals):
    pos = []
    for terminal in terminals:
        find_pos = sample.find(terminal, 1)
        if find_pos != -1:
            pos.append(find_pos)
    if len(pos) > 0:
        return sample[: (min(pos) + 1)]
    else:
        return sample


def cross_entropy(logits, target, reduction="mean"):
    return torch.nn.functional.cross_entropy(
        input=logits,
        target=target,
        weight=None,
        size_average=None,
        reduce=None,
        reduction=reduction,
    )


def run_sample(
    device, model, tokenizer, context, num_return_sequences, temp, top_p, max_length
):
    completions = sample(
        device=device,
        model=model,
        tokenizer=tokenizer,
        context=context,
        pad_token_id=tokenizer.encode("<|pad|>").ids[0],
        num_return_sequences=num_return_sequences,
        temp=temp,
        top_p=top_p,
        max_length=max_length,
    )
    truncations = [
        truncate(completion, terminals=["1", "2"]) for completion in completions
    ]

    for _i, _truncation in enumerate(truncations):
        # Remove the '1' and '2' that Progen2 uses as start/end tokens
        truncations[_i] = _truncation.replace("1", "").replace("2", "").replace("0", "")

    return truncations
