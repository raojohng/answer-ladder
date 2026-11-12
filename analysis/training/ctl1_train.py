"""Positive control, training: memorise four short prefixes with cross-entropy, tool-call tokens weighted 4, thinking 1.
Model code = train_v8con.py up to its data cell (the code the parity check cleared). Rank/alpha 64, AdamW 2e-4, no decay,
warm-up 5 updates, all four prefixes in every update, at most 80 updates.

    CUDA_VISIBLE_DEVICES=0 R2_MODEL=<model> ctl1_train.py <train_v8con.py> <a_train.jsonl> <out adapter folder>
"""
import json, math, shutil, sys, time
from pathlib import Path

TRAINER, DATA, OUT = sys.argv[1], sys.argv[2], Path(sys.argv[3])
space = {"__name__": "trainer"}
exec(compile(open(TRAINER).read().split("# Cell 7: Load the training sessions.")[0], TRAINER, "exec"), space)
torch, model, core, trainable, first_card, SOFTCAP = (space[k] for k in ("torch", "model", "core", "trainable", "first_card", "SOFTCAP"))
from safetensors.torch import load_file, save_file

W_THINK, W_ACTION, UPDATES, LR, WARMUP = 1.0, 4.0, 80, 2e-4, 5
rows = [json.loads(l) for l in open(DATA)]
batch = []
for r in rows:
    targets, weights, action = [], [], []
    for (a, b), (think, act) in zip(r["targets"], r["weights"]):
        targets += range(a, b)
        weights += [W_THINK] * think + [W_ACTION] * act
        action += [False] * think + [True] * act
    batch.append((r["id"], torch.tensor([r["input_ids"]], device=first_card), torch.tensor(targets, device=first_card),
                  torch.tensor(weights), torch.tensor(action)))
TOTAL = sum(w.sum().item() for *_, w, _ in batch)


def step(ids, targets, weights, action, backward):
    """Weighted cross-entropy of one prefix, divided by the batch's total weight. Returns (weighted sum, thinking CE sum,
    action CE sum, action tokens whose most likely token is the right one)."""
    with torch.set_grad_enabled(backward):
        hidden = core.model(input_ids=ids, use_cache=False).last_hidden_state[0]
    picked = hidden[targets.to(hidden.device) - 1]
    leaf = picked.detach().requires_grad_(backward)
    labels = ids[0, targets]
    total = think = act = right = 0.0
    for start in range(0, len(targets), 256):
        with torch.set_grad_enabled(backward):
            logits = core.lm_head(leaf[start:start + 256]).float()
            if SOFTCAP:
                logits = torch.tanh(logits / SOFTCAP) * SOFTCAP
            ce = torch.nn.functional.cross_entropy(logits, labels[start:start + 256].to(logits.device), reduction="none")
            w, a = weights[start:start + 256].to(ce.device), action[start:start + 256].to(ce.device)
            part = (ce * w).sum() / TOTAL
        if backward:
            part.backward()
        total += part.item(); think += ce[~a].sum().item(); act += ce[a].sum().item()
        right += (logits.argmax(-1) == labels[start:start + 256].to(logits.device))[a].sum().item()
    if backward:
        picked.backward(leaf.grad)
    return total, think, act, right


optimizer = torch.optim.AdamW(trainable, lr=LR, weight_decay=0.0)
schedule = torch.optim.lr_scheduler.LambdaLR(optimizer, lambda u: min(1.0, (u + 1) / WARMUP))
n_think = sum((~a).sum().item() for *_, a in batch); n_act = sum(a.sum().item() for *_, a in batch)
print(f"{len(batch)} prefixes, {n_think} thinking tokens, {n_act} action tokens, total weight {TOTAL:.0f}", flush=True)
started, log = time.time(), []
model.train()
for update in range(UPDATES + 1):
    for p in trainable:
        p.grad = None
    sums = [0.0, 0.0, 0.0, 0.0]
    last = update == UPDATES                      # the last pass only measures
    for _, ids, targets, weights, action in batch:
        for i, v in enumerate(step(ids, targets, weights, action, backward=not last)):
            sums[i] += v
    norm = 0.0
    if not last:
        norm = torch.nn.utils.clip_grad_norm_(trainable, 1.0).item()
        assert math.isfinite(norm)
        optimizer.step(); schedule.step()
    log.append(dict(update=update, weighted=sums[0], thinking=sums[1] / n_think, action=sums[2] / n_act, action_top1=sums[3] / n_act, grad_norm=norm))
    print(f"{'after' if last else 'before'} update {update + (not last):2d}: weighted loss {sums[0]:.4f} | thinking {sums[1] / n_think:.4f} | action {sums[2] / n_act:.4f} "
          f"| action tokens right {100 * sums[3] / n_act:.1f}% | grad norm {norm:.3f} | {time.time() - started:.0f}s", flush=True)

if OUT.exists():
    shutil.rmtree(OUT)
model.save_pretrained(str(OUT))
(OUT / "README.md").unlink(missing_ok=True)
weights = load_file(str(OUT / "adapter_model.safetensors"))
save_file({n: t.to(torch.bfloat16).contiguous() for n, t in weights.items()}, str(OUT / "adapter_model.safetensors"))
config = json.loads((OUT / "adapter_config.json").read_text())
config.update(base_model_name_or_path="google/gemma-4-e4b-it-qat-w4a16-ct", inference_mode=True, lora_dropout=0.0,
              target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
(OUT / "adapter_config.json").write_text(json.dumps(config, indent=2) + "\n")
json.dump(log, open(str(OUT) + "_log.json", "w"), indent=1)
print(f"exported {OUT.name}: {len(weights)} tensors, {(OUT / 'adapter_model.safetensors').stat().st_size / 2**20:.0f} MiB")
print("CTL1_TRAINED")
