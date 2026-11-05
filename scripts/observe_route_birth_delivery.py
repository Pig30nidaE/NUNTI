#!/usr/bin/env python3
"""Read installed APK bytes and actual foreground/selection state; leave app and bridge open."""
import hashlib
import json
from pathlib import Path
import subprocess
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
ADB=[str(ROOT/'.local/pm-tools/sdk/platform-tools/adb'),'-s','emulator-5554']
PACKAGE='ai.nunti.avatar.demo'
def command(*args):return subprocess.run(ADB+list(args),check=True,capture_output=True).stdout

def main():
    target=ROOT/'prototypes/route_birth';delivery=json.loads((target/'delivered-apk.json').read_text());gesture=json.loads((target/'gesture-runtime-01/verification.json').read_text())
    path=command('shell','pm','path','--user','10',PACKAGE).decode().strip().removeprefix('package:')
    assert path.startswith('/data/app/') and path.endswith('/base.apk') and '\n' not in path
    installed=command('exec-out','cat',path);actual=hashlib.sha256(installed).hexdigest();assert actual==delivery['apkSha256']
    state=json.loads(command('exec-out','run-as',PACKAGE,'--user','10','cat','files/route-birth/state.json'))
    request=gesture['requestId'];assert state['selected']==request and state['records'][request]['arrived'] and state['records'][request]['collected']
    events=[json.loads(x) for x in command('exec-out','run-as',PACKAGE,'--user','10','cat','files/route-born-events.jsonl').splitlines() if x]
    restored=next(v for v in reversed(events) if v['kind']=='RB_RESTORED');gate=next(v for v in reversed(events) if v['kind']=='RB_GATE')
    assert restored['requestId']==request and restored['characterId']==gesture['characterId']
    assert gate['foreground'] and gate['visible'] and not gate['quietConfirmed']
    activities=command('shell','dumpsys','activity','activities').decode()
    resumed=[x.strip() for x in activities.splitlines() if any(k in x.lower() for k in ('topresumedactivity=','resumedactivity:','mresumedactivity:'))]
    assert any('ai.nunti.app.routebirth.RouteBirthActivity' in x for x in resumed)
    automatic=any(v['kind']=='RB_SPEECH' and v.get('status')=='STARTED' for v in events[events.index(restored)+1:]);assert not automatic
    (target/'user-ready.png').write_bytes(command('exec-out','screencap','-p'))
    report={'status':'PASS_INSTALLED_FINAL_APK_LAUNCHER_AND_USER_STATE','at':datetime.now(timezone.utc).isoformat(),
        'apkSha256':actual,'installedApkBytes':len(installed),'resumed':resumed,'restored':restored,'gate':gate,
        'localCollectionCount':sum(v['collected'] for v in state['records'].values()),'automaticSpeechAfterRestore':automatic}
    (target/'user-ready-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(report['status'])

if __name__=='__main__':main()
