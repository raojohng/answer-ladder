"""Teacher-forced change under each adapter on FRESH untrained tries (probe_fresh_rows.jsonl), pooled over tries: mean change on
positive-advantage tries minus mean change on negative ones, in nats per try, for thinking tokens, search/read calls (every
turn's call but the last) and the first edit call (the last turn's call). Each span: [thinking tokens, thinking log-prob,
call tokens, call log-prob].
    python3 -I probe_fresh_summary.py data/training/probe_fresh_rows.jsonl"""
import collections, json, sys
import statistics as st
rows = [json.loads(l) for l in open(sys.argv[1])]
by = collections.defaultdict(dict)
for r in rows:
    sp = r["spans"]
    by[r["id"]][r["model"]] = (sum(s[1] for s in sp), sum(s[3] for s in sp[:-1]), sp[-1][3] if sp else 0.0, r["advantage"])
plain = "gemma-4-e4b-it-qat-w4a16-ct"
models = sorted({m for v in by.values() for m in v} - {plain})
for m in models:
    ch = [(tuple(v[m][k] - v[plain][k] for k in range(3)), v[plain][3]) for v in by.values() if m in v and plain in v]
    pos = [c for c, a in ch if a > 0]; neg = [c for c, a in ch if a < 0]
    gap = [st.mean(c[k] for c in pos) - st.mean(c[k] for c in neg) for k in range(3)]
    print(f"{m}: {len(pos)} positive, {len(neg)} negative tries, {len({i.split(':')[0] for i in by})} tasks | gap thinking {gap[0]:+.1f}, "
          f"search/read calls {gap[1]:+.1f}, first edit call {gap[2]:+.1f} nats per try")
