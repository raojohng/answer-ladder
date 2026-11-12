"""Parity check, trainer side: the trainer's own model code (train_v8con.py up to its data cell: unpacked 4-bit weights,
block attention, PEFT adapter) scores the same token ids the server scored. Plain = fresh adapter (B = 0); adapter = the
exported file loaded into the same PEFT modules.

    CUDA_VISIBLE_DEVICES=0 R2_MODEL=<model folder> parity_trainer.py <train_v8con.py> <adapter folder> <out folder>
"""
import json, sys
from pathlib import Path

TRAINER, ADAPTER, OUT = sys.argv[1], sys.argv[2], Path(sys.argv[3])
source = open(TRAINER).read().split("# Cell 7: Load the training sessions.")[0]
space = {"__name__": "trainer"}
exec(compile(source, TRAINER, "exec"), space)
torch, model, target_logprobs, first_card = space["torch"], space["model"], space["target_logprobs"], space["first_card"]
from safetensors.torch import load_file

rows = json.load(open(OUT / "rows.json"))
model.eval()


def score(tag, result):
    for name, row in rows.items():
        ids = torch.tensor([row["input_ids"]], device=first_card)
        targets = torch.arange(1, ids.shape[1], device=first_card)
        result[f"{name}|{tag}"] = [None] + target_logprobs(ids, targets).tolist()
        print(name, tag, ids.shape[1], "tokens", flush=True)


result = {}
score("plain", result)
stored = load_file(f"{ADAPTER}/adapter_model.safetensors")
params = {n.replace(".default", ""): p for n, p in model.named_parameters() if p.requires_grad}
assert set(params) == set(stored), (len(params), len(stored))
with torch.no_grad():
    for n, p in params.items():
        p.copy_(stored[n].to(p.device, p.dtype))
print("adapter loaded:", len(stored), "tensors", flush=True)
score("adapter", result)
json.dump(result, open(OUT / "trainer_logprobs.json", "w"))
print("TRAINER_PART_DONE")
