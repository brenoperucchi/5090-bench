"""Desk test v3 (A2 count, C1) over every base run of one prompt arm, grouped by model tag.

Usage: ARM=v3-compact python3 tools/desk_test_by_model.py [model-tag ...]

Items per snapshot come from an existing checklist annex of that snapshot (_blind-key.json).
Needs the git-ignored Guardian evidence of results/guardian-synthesis-20260921 on the lab machine.
"""
import json,glob,collections,statistics as st,sys,os
sys.path.insert(0,'tools')
import desk_test as v1, desk_test_v3 as D
CAMP='results/guardian-synthesis-20260921'; ARM=__import__('os').environ.get('ARM','atual')
key=json.load(open(f'{CAMP}/_blind-key.json'))
annex={}
for bid,m in key.items():
    p=f'{CAMP}/checklists/{bid}.md'
    if m['snapshot'] not in annex and os.path.exists(p):
        it=v1.annex(open(p).read())
        if it: annex[m['snapshot']]=it
tags=set(sys.argv[1:]); agg=collections.defaultdict(list); skipped=collections.Counter()
for f in glob.glob(f'{CAMP}/runs/{ARM}~*~base~*.json'):
    tag=f.split('/')[-1].split('~')[1]
    if tags and tag not in tags: continue
    r=json.load(open(f))
    if not r.get('content') or r['snapshot'] not in annex: skipped[tag]+=1; continue
    e=D.evaluate(r['content'],annex[r['snapshot']])
    c1=e['C1']; c1=c1.get('pass',c1.get('ok',c1.get('pending_first'))) if isinstance(c1,dict) else c1
    agg[tag].append((e['A2']['count'],bool(c1)))
print('snapshots com anexo:', sorted(annex))
print(f"{'modelo':26} {'n':>3} {'fora esc.':>9} {'A2 média':>9} {'mediana':>8} {'A2=0':>6} {'C1 ok':>6}")
def mean_a2(v):
    a=[x[0] for x in v if x[0] is not None]; return st.mean(a) if a else 99
for t,v in sorted(agg.items(), key=lambda kv: mean_a2(kv[1])):
    a=[x[0] for x in v if x[0] is not None]; fe=len(v)-len(a)
    m=f"{st.mean(a):9.2f} {st.median(a):8.1f} {sum(1 for x in a if x==0):3}/{len(a):<2}" if a else f"{'—':>9} {'—':>8} {'—':>6}"
    print(f"{t:26} {len(v):3} {fe:9} {m} {sum(x[1] for x in v):3}/{len(v)}")
if skipped: print('pulados:', dict(skipped))
