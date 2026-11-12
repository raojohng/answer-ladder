"""Parity check, comparison (no GPU): trainer against server, per token.

    parity_compare.py <out folder> <repo with post_training/>
"""
import importlib.util, json, sys
from pathlib import Path
import numpy as np

OUT, REPO = Path(sys.argv[1]), Path(sys.argv[2])
server, trainer, rows = (json.load(open(OUT / f)) for f in ("server_logprobs.json", "trainer_logprobs.json", "rows.json"))


def line(label, d):
    a = np.abs(d)
    return (f"{label:34s} n {len(d):6d} | mean {d.mean():+.4f} | abs mean {a.mean():.4f} median {np.median(a):.4f} "
            f"p99 {np.percentile(a, 99):.3f} max {a.max():.3f} | over 0.1: {100 * (a > 0.1).mean():.2f}% over 0.5: {100 * (a > 0.5).mean():.2f}%")


print("== Log-probabilities (nats): trainer minus server, same token ids ==")
for name, row in rows.items():
    n = len(row["input_ids"])
    target = np.zeros(n, bool)
    for a, b in row["targets"]:
        target[a:b] = True
    get = lambda source, tag: np.array([np.nan if v is None else v for v in source[f"{name}|{tag}"]], float)
    sp, sa, tp, ta = get(server, "plain"), get(server, "adapter"), get(trainer, "plain"), get(trainer, "adapter")
    ok = ~np.isnan(sp) & ~np.isnan(sa) & ~np.isnan(tp) & ~np.isnan(ta)
    print(f"\n{name}: {n} tokens, {target.sum()} targets, {int((~ok).sum()) - 1} positions without a server value")
    print(f"  mean log-probability on targets: server plain {sp[ok & target].mean():.4f} trainer plain {tp[ok & target].mean():.4f} | "
          f"server adapter {sa[ok & target].mean():.4f} trainer adapter {ta[ok & target].mean():.4f}")
    third = np.arange(n) * 3 // n
    for label, mask in (("all", ok), ("targets", ok & target), ("context", ok & ~target), ("first third", ok & (third == 0)),
                        ("last third", ok & (third == 2))):
        print("  " + line(f"plain, {label}", (tp - sp)[mask]))
    for label, mask in (("all", ok), ("targets", ok & target), ("last third", ok & (third == 2))):
        print("  " + line(f"adapter, {label}", (ta - sa)[mask]))
    ds, dt = (sa - sp), (ta - tp)                      # what the adapter changes, in each engine
    for label, mask in (("all", ok), ("targets", ok & target)):
        print(f"  adapter effect, {label}: server abs mean {np.abs(ds[mask]).mean():.4f} (mean {ds[mask].mean():+.4f}) | trainer abs mean "
              f"{np.abs(dt[mask]).mean():.4f} (mean {dt[mask].mean():+.4f}) | correlation {np.corrcoef(ds[mask], dt[mask])[0, 1]:.4f} | "
              f"abs mean of the difference {np.abs(dt[mask] - ds[mask]).mean():.4f}")
    noise = np.abs((tp - sp)[ok & target])              # is the adapter's effect larger than the engines' disagreement?
    print(f"  on targets: engines disagree by {noise.mean():.4f} on plain; the adapter moves the server by {np.abs(ds[ok & target]).mean():.4f}")

print("\n== Tokens: the server's ids for recorded requests against the trainer's rendering ==")
spec = importlib.util.spec_from_file_location("render", REPO / "post_training/datasets/d1_flash_next/render.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
renderer = module.Renderer(REPO / "post_training/render/model_files/e4b")
for t in json.load(open(OUT / "server_tokens.json")):
    mine = renderer.tokenizer.encode(renderer.render(t["messages"], t["tools"], True), add_special_tokens=False).ids
    print(f"\nturn {t['turn']}: recorded {t['recorded_prompt_tokens']}, replay {t['replay_prompt_tokens']}, trainer rendering {len(mine)}, "
          f"extra_body {t['extra_body']}")
    for label in ("server_ids", "tokenize_ids"):
        theirs = t[label]
        if not theirs:
            print(f"  {label}: not returned")
            continue
        i = next((k for k, (a, b) in enumerate(zip(mine, theirs)) if a != b), min(len(mine), len(theirs)))
        j = next((k for k, (a, b) in enumerate(zip(mine[::-1], theirs[::-1])) if a != b), min(len(mine), len(theirs)))
        print(f"  {label}: {len(theirs)} ids; same first {i}, same last {j}")
        if mine != theirs:
            show = lambda ids: [(x, renderer.tokenizer.decode([x], skip_special_tokens=False)) for x in ids]
            print("    trainer around the first difference:", show(mine[max(0, i - 4):i + 6]))
            print("    server  around the first difference:", show(theirs[max(0, i - 4):i + 6]))
            print("    trainer end:", show(mine[-6:]))
            print("    server  end:", show(theirs[-6:]))
        else:
            print("    identical")
print("COMPARE_DONE")
