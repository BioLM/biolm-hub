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
Adapted from: https://github.com/salesforce/progen/blob/main/progen2/likelihood.py

There is plenty of overlap with sample_utils.py, but they are kept separate
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


########################################################################
# likelihood


def ce(tokens, tokenizer, device, model):
    with torch.no_grad():
        with torch.cuda.amp.autocast(enabled=False):
            target = torch.tensor(tokenizer.encode(tokens).ids).to(device)
            logits = model(target, labels=target).logits

            # shift
            logits = logits[:-1, ...]
            target = target[1:]

            return cross_entropy(logits=logits, target=target).item()


#
def log_likelihood(logits, target, reduction="mean"):
    return -cross_entropy(
        logits.view(-1, logits.size(-1)), target.view(-1), reduction=reduction
    )


#
def ll(tokens, model, tokenizer, device, f=log_likelihood, reduction="mean"):
    with torch.no_grad():
        with torch.cuda.amp.autocast(enabled=False):
            target = torch.tensor(tokenizer.encode(tokens).ids).to(device)
            logits = model(target, labels=target).logits

            # shift
            logits = logits[:-1, ...]
            target = target[1:]

            # remove terminals
            bos_token, eos_token = 3, 4
            if target[-1] in [bos_token, eos_token]:
                logits = logits[:-1, ...]
                target = target[:-1]

            assert (target == bos_token).sum() == 0
            assert (target == eos_token).sum() == 0

            # remove unused logits
            first_token, last_token = 5, 29
            logits = logits[:, first_token : (last_token + 1)]
            target = target - first_token

            assert logits.shape[1] == (last_token - first_token + 1)

            return f(logits=logits, target=target, reduction=reduction).item()


def cross_entropy(logits, target, reduction="mean"):
    return torch.nn.functional.cross_entropy(
        input=logits,
        target=target,
        weight=None,
        size_average=None,
        reduce=None,
        reduction=reduction,
    )


def run_likelihood(context, model, tokenizer, device):
    def reverse(s):
        return s[::-1]

    ll_lr_sum = ll(
        tokens=context,
        reduction="sum",
        model=model,
        tokenizer=tokenizer,
        device=device,
    )
    ll_rl_sum = ll(
        tokens=reverse(context),
        reduction="sum",
        model=model,
        tokenizer=tokenizer,
        device=device,
    )

    ll_lr_mean = ll(
        tokens=context,
        reduction="mean",
        model=model,
        tokenizer=tokenizer,
        device=device,
    )
    ll_rl_mean = ll(
        tokens=reverse(context),
        reduction="mean",
        model=model,
        tokenizer=tokenizer,
        device=device,
    )

    ll_sum = 0.5 * (ll_lr_sum + ll_rl_sum)
    ll_mean = 0.5 * (ll_lr_mean + ll_rl_mean)

    # logger.info(f'll_sum={(ll_sum)}')
    # logger.info(f'll_mean={ll_mean}')

    return {"ll_sum": ll_sum, "ll_mean": ll_mean}


def log_likelihood_custom_1(logits, target, reduction="mean"):
    return -torch.nn.functional.nll_loss(
        input=torch.log_softmax(logits, dim=1), target=target, reduction=reduction
    )


def log_likelihood_custom_2(logits, target, reduction="mean"):
    assert len(target.shape) == 1
    assert logits.shape[0] == target.shape[0]

    log_likelihood = 0.0
    n = logits.shape[0]
    for i in range(n):
        log_likelihood += torch.log_softmax(logits, dim=1)[i, target[i]] / (
            1.0 if reduction == "sum" else n
        )
    return log_likelihood
