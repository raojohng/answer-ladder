"""Paths and the vLLM config shared by the RTX scripts. Same server settings as e4b_track/notebook/cells/04_server.py."""
import json, os
from pathlib import Path
from adk_submission import VllmConfig, VllmServer

ROOT = Path.home() / "workspace/Gemma4"
DATA = ROOT / "competition_data"
SERVED_NAME = os.environ.get("MODEL_NAME", "gemma-4-e4b-it-qat-w4a16-ct")   # a folder in models/, and the name agent.yaml uses
MODEL = ROOT / "models" / SERVED_NAME   # the default model's folder


def server(port=None, name=None):
    """vLLM config for one served model. name defaults to MODEL_NAME; LORA_MODULES applies to that default model only."""
    port = port or int(os.environ.get("PORT", "8000"))
    first = name is None
    name = name or SERVED_NAME
    extra = []
    if name.startswith("Qwen"):      # Qwen's tool-call and thinking formats; everything else as for Gemma
        family = dict(tool_call_parser="qwen3_xml", reasoning_parser="qwen3",
                      reasoning_config={"reasoning_start_str": "<think>", "reasoning_end_str": "</think>"})
        # vLLM turns prefix caching off by default for hybrid (Mamba-style) models such as Qwen3.8; without it every call
        # re-reads the whole conversation (hit rate 0%). On, it uses Mamba cache mode 'all' or 'align' (experimental in 0.19.1).
        extra = ["--enable-prefix-caching"]
        # QWEN_MTP=n: the checkpoint's own multi-token-prediction head drafts n tokens per step (speculative decoding;
        # the output distribution is unchanged). QWEN_TP=2 splits the model over two GPUs (pass gpu "0,1" to start_server.py).
        if os.environ.get("QWEN_MTP"):
            extra += ["--speculative-config", json.dumps({"method": "mtp", "num_speculative_tokens": int(os.environ["QWEN_MTP"])})]
        if int(os.environ.get("QWEN_TP", "1")) > 1:   # WSL2: custom all-reduce needs CUDA IPC; NCCL needs NCCL_CUMEM_ENABLE=0 (cuMem alloc fails, error 999) and NCCL_P2P_DISABLE=1
            extra += ["--disable-custom-all-reduce"]
    else:
        family = dict(tool_call_parser="gemma4", reasoning_parser="gemma4")
    if os.environ.get("KV_CACHE_GB"):   # fixed cache size: on a GPU shared with another server (WSL), vLLM's estimate fails
        extra += ["--kv-cache-memory-bytes", str(int(float(os.environ["KV_CACHE_GB"]) * 2**30))]
    lora = dict(item.split("=", 1) for item in os.environ.get("LORA_MODULES", "").split(",") if item) if first else {}   # name=folder,name=folder
    return VllmServer(VllmConfig(
        model=str(ROOT / "models" / name), host="127.0.0.1", port=port, default_chat_template_kwargs={"enable_thinking": True},
        max_model_len=32768, dtype="bfloat16", gpu_memory_utilization=float(os.environ.get("GPU_MEMORY", "0.80")), enable_auto_tool_choice=True,
        tensor_parallel_size=int(os.environ.get("QWEN_TP", "1")) if name.startswith("Qwen") else 1, startup_timeout=20 * 60,
        extra_args=["--served-model-name", name] + extra + (["--seed", os.environ["SERVER_SEED"]] if os.environ.get("SERVER_SEED") else []), **family), lora_modules=lora or None)


def registry():
    """Requests carry the plain model name, as Kaggle's carry a path with gemma-4 in it. ADK switches the tool-result role
    to 'tool_responses' if 'gemma4' appears in the model string, and the folder ~/workspace/Gemma4 would trigger that."""
    models = server().create_model_registry(aliases={SERVED_NAME: SERVED_NAME}, model_prefix="openai/", api_key="EMPTY")
    assert "gemma4" not in SERVED_NAME.lower()
    if os.environ.get("MODEL2"):     # a second model on its own server (MODEL2=name PORT2=port), e.g. a teacher stage in a bundle
        name2 = os.environ["MODEL2"]
        assert "gemma4" not in name2.lower()
        extra = server(int(os.environ["PORT2"]), name2).create_model_registry(aliases={name2: name2}, model_prefix="openai/", api_key="EMPTY")
        for n in extra.list_available():
            models.register(n, extra.get(n))
    return models

