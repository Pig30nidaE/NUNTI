#!/usr/bin/env python3
"""Generate the authorized wardrobe examples once; cached briefs never spend twice."""
import json
import sys
import urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EXAMPLES={
 'formal':{'destination':{'name':'회사','traits':'차분하고 단정한 분위기'},'purpose':'면접','mood':'calm','scenery':'city','road':'urban'},
 'medical':{'destination':{'name':'병원','traits':'따뜻하고 편안한 분위기'},'purpose':'병원 진료','mood':'calm','scenery':'city','road':'urban'},
 'football':{'destination':{'name':'축구 경기장','traits':'초록 잔디와 즐거운 응원'},'purpose':'축구 경기 관람','mood':'adventurous','scenery':'city','road':'urban'},
}
def main():
 c=json.loads((ROOT/'.local/avatar-generator/connection.json').read_text())
 headers={'Authorization':'Bearer '+c['token'],'Content-Type':'application/json'}
 out=ROOT/'artifacts/nunti-context-v4/wardrobe';out.mkdir(parents=True,exist_ok=True)
 for name in sys.argv[1:] or EXAMPLES:
  req=urllib.request.Request(c['baseUrl']+'/v3/wardrobe',data=json.dumps(EXAMPLES[name]).encode(),headers=headers)
  with urllib.request.urlopen(req,timeout=220) as r:result=json.load(r)['data']
  (out/(name+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2))
  with urllib.request.urlopen(urllib.request.Request(c['baseUrl']+result['visual']['path'],headers=headers),timeout=15) as r:(out/(name+'.png')).write_bytes(r.read())
  print(json.dumps({'status':'READY','look':name,'estimatedUsd':(result['provider']['estimatedCostMicros'] or 0)/1000000}),flush=True)
 with urllib.request.urlopen(urllib.request.Request(c['baseUrl']+'/v3/wardrobe/budget',headers=headers)) as r:budget=json.load(r)['data']
 (out/'budget.json').write_text(json.dumps(budget,indent=2));print(budget)
if __name__=='__main__': main()
