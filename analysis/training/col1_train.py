"""Transfer test tr1, training: the control's recipe on about 100 tasks. Cross-entropy on each try's replies up to its first
edit, tool-call tokens weighted 4 and thinking 1; rank/alpha 64, AdamW 2e-4, no decay, warm-up 5 updates, 4 rows per update,
up to PASSES passes over the rows (stops early once a pass ends with thinking loss under 0.02). Adapters are exported after
passes 2, 4, 6 and at the end; the loss on the held-out tasks' rows is measured before training and at each export.

    CUDA_VISIBLE_DEVICES=0 R2_MODEL=<model> tr1_train.py <train_v8con.py> <folder with a_train.jsonl, a_held_out.jsonl> <out adapter folder>
"""
import json, math, os, random, shutil, sys, time
from pathlib import Path

TRAINER, DATA, OUT = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
space = {"__name__": "trainer"}
exec(compile(open(TRAINER).read().split("# Cell 7: Load the training sessions.")[0], TRAINER, "exec"), space)
torch, model, core, trainable, first_card, SOFTCAP = (space[k] for k in ("torch", "model", "core", "trainable", "first_card", "SOFTCAP"))
from safetensors.torch import load_file, save_file

W_THINK, W_ACTION, LR, WARMUP, PER_UPDATE = float(os.environ.get("TR_W_THINK", "1.0")), 4.0, 2e-4, 5, 4   # col1: 1.0 full imitation, 0.0 action-only
PASSES, HOURS = int(os.environ.get("TR_PASSES", "10")), float(os.environ.get("TR_HOURS", "1.5"))   # dp1: TR_PASSES=2
EXPORTS = [int(x) for x in os.environ.get("TR_EXPORTS", "2,4,6").split(",") if x]


def prepare(r):
    targets, weights, action = [], [], []
    for (a, b), (think, act) in zip(r["targets"], r["weights"]):
        targets += range(a, b)
        weights += [W_THINK] * think + [W_ACTION] * act
        action += [False] * think + [True] * act
    return r["input_ids"], torch.tensor(targets), torch.tensor(weights), torch.tensor(action)


train = [prepare(json.loads(l)) for l in open(DATA / "a_train.jsonl")]
held = [prepare(json.loads(l)) for l in open(DATA / "a_held_out.jsonl")]


def step(row, divisor, backward):
    """Weighted cross-entropy of one row / divisor. Returns sums: weighted, thinking CE, action CE, action tokens ranked first, thinking tokens, action tokens."""
    ids = torch.tensor([row[0]], device=first_card)
    targets, weights, action = row[1].to(first_card), row[2], row[3]
    with torch.set_grad_enabled(backward):
        hidden = core.model(input_ids=ids, use_cache=False).last_hidden_state[0]
    picked = hidden[targets.to(hidden.device) - 1]
    leaf = picked.detach().requires_grad_(backward)
    labels = ids[0, targets]
    out = [0.0] * 4
    for start in range(0, len(targets), 256):
        with torch.set_grad_enabled(backward):
            logits = core.lm_head(leaf[start:start + 256]).float()
            if SOFTCAP:
                logits = torch.tanh(logits / SOFTCAP) * SOFTCAP
            lab = labels[start:start + 256].to(logits.device)
            ce = torch.nn.functional.cross_entropy(logits, lab, reduction="none")
            w, a = weights[start:start + 256].to(ce.device), action[start:start + 256].to(ce.device)
            part = (ce * w).sum() / divisor
        if backward:
            part.backward()
        out[0] += part.item(); out[1] += ce[~a].sum().item(); out[2] += ce[a].sum().item(); out[3] += (logits.argmax(-1) == lab)[a].sum().item()
    if backward:
        picked.backward(leaf.grad)
    return out + [(~action).sum().item(), action.sum().item()]


def measure(rows):
    model.eval()
    s = [0.0] * 6
    for row in rows:
        for i, v in enumerate(step(row, 1.0, False)):
            s[i] += v
    model.train()
    return s[1] / max(1, s[4]), s[2] / max(1, s[5]), s[3] / max(1, s[5])


def export(folder):
    out = Path(folder)
    if out.exists():
        shutil.rmtree(out)
    model.save_pretrained(str(out))
    (out / "README.md").unlink(missing_ok=True)
    weights = load_file(str(out / "adapter_model.safetensors"))
    save_file({n: t.to(torch.bfloat16).contiguous() for n, t in weights.items()}, str(out / "adapter_model.safetensors"))
    config = json.loads((out / "adapter_config.json").read_text())
    config.update(base_model_name_or_path="google/gemma-4-e4b-it-qat-w4a16-ct", inference_mode=True, lora_dropout=0.0,
                  target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
    (out / "adapter_config.json").write_text(json.dumps(config, indent=2) + "\n")
    print(f"  exported {out.name}: {len(weights)} tensors", flush=True)


optimizer = torch.optim.AdamW(trainable, lr=LR, weight_decay=0.0)
schedule = torch.optim.lr_scheduler.LambdaLR(optimizer, lambda u: min(1.0, (u + 1) / WARMUP))
random.seed(20261111)
started, log = time.time(), []
h = measure(held)
print(f"{len(train)} training rows, {len(held)} held-out rows | held-out before training: thinking {h[0]:.4f} action {h[1]:.4f} action tokens first {100 * h[2]:.1f}%", flush=True)
log.append(dict(passes=0, held_thinking=h[0], held_action=h[1], held_action_top1=h[2]))
model.train()
for p in range(1, PASSES + 1):
    order = list(range(len(train))); random.shuffle(order)
    s = [0.0] * 6
    for at in range(0, len(order), PER_UPDATE):
        batch = [train[i] for i in order[at:at + PER_UPDATE]]
        divisor = sum(r[2].sum().item() for r in batch)
        for q in trainable:
            q.grad = None
        for row in batch:
            for i, v in enumerate(step(row, divisor, True)):
                s[i] += v
        norm = torch.nn.utils.clip_grad_norm_(trainable, 1.0).item()
        assert math.isfinite(norm)
        optimizer.step(); schedule.step()
    entry = dict(passes=p, thinking=s[1] / s[4], action=s[2] / s[5], action_top1=s[3] / s[5], minutes=(time.time() - started) / 60)
    line = f"pass {p:2d} (during it): thinking {entry['thinking']:.4f} | action {entry['action']:.4f} | action tokens first {100 * entry['action_top1']:.1f}% | {entry['minutes']:.0f} min"
    last = p == PASSES or entry["thinking"] < 0.02 or (time.time() - started) / 3600 > HOURS
    if p in EXPORTS or last:
        h = measure(held)
        entry.update(held_thinking=h[0], held_action=h[1], held_action_top1=h[2])
        line += f" | held-out: thinking {h[0]:.4f} action {h[1]:.4f} action tokens first {100 * h[2]:.1f}%"
    print(line, flush=True)
    log.append(entry)
    if p in EXPORTS and not last:
        export(f"{OUT}_p{p}")
    if last:
        break
export(OUT)
json.dump(log, open(str(OUT) + "_log.json", "w"), indent=1)
print("TR1_TRAINED")
