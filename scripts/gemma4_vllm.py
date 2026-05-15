#!/usr/bin/env python3
from __future__ import annotations

import gguf
import transformers.integrations as tf_integrations
import transformers.modeling_gguf_pytorch_utils as gguf_utils

# Temporary compatibility shim for GGUF Gemma 4 artifacts on this machine.
# Transformers 5.7.0 only advertises gemma2/gemma3 GGUF support; Gemma 4 is
# close enough structurally here that we can alias the metadata/config mapping
# and let vLLM continue loading through the normal path.
if "gemma4" not in tf_integrations.GGUF_CONFIG_MAPPING:
    tf_integrations.GGUF_CONFIG_MAPPING["gemma4"] = tf_integrations.GGUF_CONFIG_MAPPING[
        "gemma3"
    ]
if "gemma4" not in gguf_utils.GGUF_SUPPORTED_ARCHITECTURES:
    gguf_utils.GGUF_SUPPORTED_ARCHITECTURES.append("gemma4")
if "gemma4" not in gguf_utils.GGUF_TO_TRANSFORMERS_MAPPING["config"]:
    gguf_utils.GGUF_TO_TRANSFORMERS_MAPPING["config"]["gemma4"] = (
        gguf_utils.GGUF_TO_TRANSFORMERS_MAPPING["config"]["gemma3"]
    )
if gguf.MODEL_ARCH_NAMES.get(gguf.MODEL_ARCH.GEMMA3) != "gemma4":
    gguf.MODEL_ARCH_NAMES[gguf.MODEL_ARCH.GEMMA3] = "gemma4"

# Gemma4 GGUF currently trips the multimodal budget planner because the GGUF
# metadata path does not expose a usable vision_config.default_output_length.
# The server only needs a conservative upper bound here, so we provide one.
import vllm.model_executor.models.gemma4_mm as gemma4_mm
import vllm.multimodal.encoder_budget as encoder_budget


def _patched_mm_max_tokens_per_item(self, seq_len, mm_counts):
    return {"image": 256}


def _patched_get_mm_max_toks_per_item(*args, **kwargs):
    return {"image": 256}


gemma4_mm.Gemma4MultiModalProcessor.get_mm_max_tokens_per_item = _patched_mm_max_tokens_per_item
encoder_budget.get_mm_max_toks_per_item = _patched_get_mm_max_toks_per_item

if __name__ == "__main__":
    from vllm.entrypoints.cli.main import main

    raise SystemExit(main())
