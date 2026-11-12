"""Decision points dp1: what the samples show.   dp1_report.py <samples.jsonl> [<samples of another model on the same contexts>]
One file: how often the next step is rewarded, how many contexts are mixed (some samples rewarded, some not), by kind.
Two files: the rewarded share per context under each model, on the contexts both have (difference with a task bootstrap)."""
import collections, json, random, sys


def load(path):
    return {r["id"]: r for r in map(json.loads, open(path))}


a = load(sys.argv[1])
n = sum(len(r["samples"]) for r in a.values())
kinds = collections.Counter(s["kind"] for r in a.values() for s in r["samples"])
rewarded = collections.Counter(s["kind"] for r in a.values() for s in r["samples"] if s["reward"])
share = [sum(s["reward"] for s in r["samples"]) / len(r["samples"]) for r in a.values()]
mixed = [r for r in a.values() if 0 < sum(s["reward"] for s in r["samples"]) < len(r["samples"])]
print(f"{len(a)} contexts of {len({r['task'] for r in a.values()})} tasks, {n} samples | kinds {dict(kinds)} | rewarded {dict(rewarded)} "
      f"({100 * sum(rewarded.values()) / n:.1f}% of samples)")
print(f"contexts: none rewarded {sum(x == 0 for x in share)}, all rewarded {sum(x == 1 for x in share)}, mixed {len(mixed)} "
      f"(of {len({r['task'] for r in mixed})} tasks; mean rewarded share in them {100 * sum(sum(s['reward'] for s in r['samples']) / len(r['samples']) for r in mixed) / max(1, len(mixed)):.0f}%)")
print(f"completion tokens per sample: mean {sum(len(s['token_ids']) for r in a.values() for s in r['samples']) / n:.0f}; "
      f"finish reasons {dict(collections.Counter(s['finish'] for r in a.values() for s in r['samples']))}")
if len(sys.argv) > 2:
    b = load(sys.argv[2])
    both = sorted(set(a) & set(b))
    rate = lambda d, i: sum(s["reward"] for s in d[i]["samples"]) / len(d[i]["samples"])
    by_task = collections.defaultdict(list)
    for i in both:
        by_task[a[i]["task"]].append(i)
    tasks = sorted(by_task)
    mean = lambda d, ts: sum(sum(rate(d, i) for i in by_task[t]) / len(by_task[t]) for t in ts) / len(ts)
    random.seed(1)
    diffs = sorted(mean(b, s) - mean(a, s) for s in ([random.choice(tasks) for _ in tasks] for _ in range(2000)))
    print(f"\n{len(both)} shared contexts of {len(tasks)} tasks: rewarded next step {100 * mean(a, tasks):.1f}% ({sys.argv[1].split('/')[-1]}) -> "
          f"{100 * mean(b, tasks):.1f}% ({sys.argv[2].split('/')[-1]}), difference {100 * (mean(b, tasks) - mean(a, tasks)):+.1f} points "
          f"(95% interval {100 * diffs[50]:+.1f} to {100 * diffs[1949]:+.1f})")
    was_mixed = [i for i in both if 0 < rate(a, i) < 1]
    if was_mixed:
        print(f"on the {len(was_mixed)} contexts that were mixed under the first model: {100 * sum(rate(a, i) for i in was_mixed) / len(was_mixed):.1f}% -> "
              f"{100 * sum(rate(b, i) for i in was_mixed) / len(was_mixed):.1f}%")
print("DP1_REPORT_DONE")
