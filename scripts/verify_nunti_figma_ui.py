#!/usr/bin/env python3
"""Build a read-only Figma MCP query; verify its actual returned facts offline.

Usage:
  python3 scripts/verify_nunti_figma_ui.py --emit-reader /private/tmp/nunti-figma-audit.js
  Run that JavaScript with use_figma in the named file/session, save returned JSON.
  python3 scripts/verify_nunti_figma_ui.py --verify
This script never edits the Figma file or substitutes authoring ledgers for readback.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'docs/redesign/pleos-ui-v1'
READBACK = DOC / 'figma-structure-readback.json'
REPORT = DOC / 'figma-structure-verification.json'
ALLOWED = ['2893d38594281749383c75afa1b9636d2b84398c', '9267bd06cd286b3e692443fe30d026123d5581df']
OFFICIAL = ['18:145', '18:181', '18:153', '18:318', '18:411', '18:467']

def unwrap(data):
    return json.loads(data['content'][0]['text']) if 'content' in data else data

def spec():
    screens, actions = [], {}
    for group in ['directions', 'main', 'compact', 'support', 'flow', 'options']:
        d = unwrap(json.loads((DOC / f'figma-{group}-result.json').read_text()))
        for name, ident in d['screens'].items():
            compact = 'Compact' in name or name.split(' / ')[0] in ['Loading', 'Offline', 'MissingRoute', 'AssetFailure', 'JOURNEY_OPTIONS', 'GENERATION_OPTIONS']
            screens.append({'name': name, 'id': ident, 'expectedWidth': 830 if compact else 1682, 'expectedHeight': 1210})
        actions.update({v:k for k,v in d.get('actions', {}).items()})
    return {'fileKey':'LHLHBra8ON3OdVW0qhBnbm','pageId':'15:4','screens':screens,'actions':actions,'allowedImages':ALLOWED}

def verify():
    expected = spec()
    raw = unwrap(json.loads(READBACK.read_text()))
    checks = []
    def check(name, ok, details=None):
        checks.append({'name':name,'status':'PASS' if ok else 'FAIL','details':details})
    frames = raw['screens']
    check('exact 36 screen IDs read from Figma', len(frames)==36 and {s['id'] for s in frames}=={s['id'] for s in expected['screens']})
    by_id={s['id']:s for s in frames}
    dimension_errors=[]
    for e in expected['screens']:
        s=by_id.get(e['id'], {})
        if s.get('type')!='FRAME' or (s.get('width'),s.get('height'))!=(e['expectedWidth'],e['expectedHeight']):
            dimension_errors.append({'id':e['id'],'actual':[s.get('width'),s.get('height')],'expected':[e['expectedWidth'],e['expectedHeight']]})
    check('native screen frames have measured display dimensions',not dimension_errors,dimension_errors)
    check('each screen uses Auto Layout, native text, and instances',all(s['autoLayoutCount'] and s['textCount'] and s['instanceCount'] for s in frames))
    fonts=[{'screen':s['id'],**e} for s in frames for e in s['fontErrors']]
    check('all visible text uses Noto Sans KR',not fonts,fonts)
    images=[{'screen':s['id'],**i} for s in frames for i in s['images']]
    bad_images=[i for i in images if not i['approved'] or not i['characterAncestor']]
    check('every image is an approved character image',bool(images) and not bad_images,bad_images)
    check('both approved hashes have 768 square source data',set(raw['imageSizes'])==set(ALLOWED) and all(z=={'width':768,'height':768} for z in raw['imageSizes'].values()),raw['imageSizes'])
    touch=[{'screen':s['id'],**e} for s in frames for e in s['touchErrors']]
    check('actionable outer instances are at least 76 square',not touch,touch)
    overflow=[{'screen':s['id'],**e} for s in frames for e in s['overflow']]
    check('no unaccounted visible node outside screen bounds',not overflow,overflow)
    motion=[{'screen':s['id'],**e} for s in frames for e in s['motionNodes']]
    check('all screen nodes inspected for automatic motion',raw['motionAvailable'] and sum(s['motionCheckedNodes'] for s in frames)==sum(s['nodeCount'] for s in frames),raw['motionApiError'])
    check('all UI screens are static without animation tracks or styles',not motion,motion)
    automatic=[{'screen':s['id'],**r} for s in frames for r in s['reactions'] if r['trigger']!='ON_CLICK']
    check('prototype navigation only responds to explicit clicks',not automatic,automatic)
    driving=[s for s in frames if s['name'].startswith('DRIVING_RESTRICTED')]
    check('four restricted-driving screens have no scroll, motion, or prototype reaction',len(driving)==4 and all(not s['scrollViewports'] and not s['motionNodes'] and not s['reactions'] for s in driving))
    refs={r['id']:r for r in raw['masterRefs']}
    missing=[i for i in OFFICIAL if i not in refs]
    check('official button, field, switch, and checkbox masters remain linked',not missing,{'missing':missing,'counts':{i:refs.get(i,{}).get('count',0) for i in OFFICIAL}})
    report={'schema':'nunti-figma-ui-verification-v1','sourceReadAt':raw['readAt'],'readback':str(READBACK.relative_to(ROOT)),'status':'PASS' if all(c['status']=='PASS' for c in checks) else 'FAIL','checks':checks,'totals':{'screens':len(frames),'nodes':sum(s['nodeCount'] for s in frames),'autoLayoutNodes':sum(s['autoLayoutCount'] for s in frames),'instances':sum(s['instanceCount'] for s in frames),'visibleText':sum(s['visibleTextCount'] for s in frames),'characterImages':len(images),'intentionalParkedScrollOverflowNodes':sum(s['intentionalScrollOverflowCount'] for s in frames)},'limitations':['Read-only structure checks do not establish visual contrast, text overlap, or runtime interaction behavior.','Actual emulator driving policy currently overlays the app; Figma driving content is a conditional design proposal, not permission to override the platform.','Minimum touch check covers explicit action ledger and visible outer Action/Choice/Field/route-confirmation/motion-toggle instances; nested visual symbols are excluded.']}
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'passed':sum(c['status']=='PASS' for c in checks),'total':len(checks),'totals':report['totals'],'failures':[c for c in checks if c['status']=='FAIL']},ensure_ascii=False,indent=2))
    return 0 if report['status']=='PASS' else 1

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--emit-reader',type=Path)
    ap.add_argument('--verify',action='store_true')
    args=ap.parse_args()
    if args.emit_reader:
        args.emit_reader.write_text('const auditSpec = '+json.dumps(spec(),ensure_ascii=False)+';\n'+(DOC/'figma-audit-reader-template.js').read_text())
        print(f'Read-only query written to {args.emit_reader}')
    elif args.verify:
        raise SystemExit(verify())
    else:
        ap.print_help()
