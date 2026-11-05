#!/usr/bin/env python3
"""Finish the one actual UI-created journey, capture guest speaker, save and cold restore."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from verify_character_voice_runtime import Recording
from verify_catalog_pcm import compare

PACKAGE='ai.nunti.avatar.demo';PREFIX=[str(ROOT/'.local/pm-tools/sdk/platform-tools/adb'),'-s','emulator-5554']

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--gesture-dir',type=Path,required=True);args=p.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=False);args.serial='emulator-5554';args.record_python=str(ROOT/'.local/voice-runtime/venv/bin/python')
    result={'status':'FAIL','at':datetime.now(timezone.utc).isoformat(),'scope':'Final APK, existing UI-created fifth journey. Native common/arrival completion, authenticated guest speaker, collection/cold restore and Android boundary checks.'}
    a=json.loads((args.gesture_dir/'ready.json').read_text())['artifact'];request_id=a['journeyId'];recording=None
    def adb(*v,binary=False):
        r=subprocess.run(PREFIX+list(v),capture_output=True,check=True,timeout=30);return r.stdout if binary else r.stdout.decode()
    def events():return [json.loads(line) for line in adb('exec-out','run-as',PACKAGE,'--user','10','cat','files/route-born-events.jsonl').splitlines() if line]
    def wait(pred):
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            rows=events()[offset:]
            value=next((v for v in rows if pred(v)),None)
            if value:return value
            if any(v['kind']=='RB_ERROR' for v in rows):raise AssertionError('Native error')
            time.sleep(.15)
        raise AssertionError('Native event timed out')
    def tree():
        adb('shell','uiautomator','dump','/sdcard/route-born-final-ui.xml')
        return ET.fromstring(adb('exec-out','cat','/sdcard/route-born-final-ui.xml'))
    def button(label):return next(n for n in tree().iter('node') if n.attrib.get('text')==label)
    def tap(node):
        x1,y1,x2,y2=map(int,re.findall(r'\d+',node.attrib['bounds']));adb('shell','input','tap',str((x1+x2)//2),str((y1+y2)//2))
    def screenshot(name):(args.output_dir/(name+'.png')).write_bytes(adb('exec-out','screencap','-p',binary=True))
    def completed():
        request=wait(lambda v:v['kind']=='RB_SPEECH_REQUEST' and v['tripId']==request_id)
        terminal=wait(lambda v:v['kind']=='RB_SPEECH' and v['requestId']==request['requestId'] and v['status'] in ('COMPLETED','CANCELLED','FAILED','REJECTED'))
        assert terminal['status']=='COMPLETED',terminal
        return {'request':request,'terminal':terminal}
    try:
        offset=len(events());tap(button('응원 듣기'));common=completed()
        tap(button('도착했어요'));wait(lambda v:v['kind']=='RB_ARRIVED' and v['requestId']==request_id)
        arrival_button=button('도착 대사')
        clip=next(c for c in a['voiceManifest']['clips'] if c['clipId'].endswith('-arrival'))
        recording=Recording(args,clip);offset=len(events());tap(arrival_button);arrival=completed();capture=recording.finish();recording=None
        source_path=args.output_dir/'source-arrival.wav'
        source_path.write_bytes(adb('exec-out','run-as',PACKAGE,'--user','10','cat',f"files/route-birth/{request_id}/voice/{clip['audioPath']}",binary=True))
        assert hashlib.sha256(source_path.read_bytes()).hexdigest()==clip['audioSha256']
        measurement=compare(source_path,Path(capture['captureSummary']['wav']),True)
        offset=len(events());tap(button('동반자 보관'));saved=wait(lambda v:v['kind']=='RB_SAVED' and v['requestId']==request_id)
        adb('shell','am','start','-W','--user','10','-n',PACKAGE+'/ai.nunti.app.routebirth.RouteBirthActivity','--es','rb_action','verify_boundaries')
        boundaries=wait(lambda v:v['kind']=='RB_BOUNDARIES');assert boundaries['passed']==9
        offset=len(events());adb('shell','am','force-stop','--user','10',PACKAGE)
        adb('shell','am','start','-W','--user','10','-n',PACKAGE+'/ai.nunti.app.MainActivity')
        restored=wait(lambda v:v['kind']=='RB_RESTORED' and v['requestId']==request_id)
        ready=wait(lambda v:v['kind']=='RB_READY' and v['requestId']==request_id)
        assert restored['characterId']==a['characterId'] and restored['arrived'] and restored['collected']==1
        time.sleep(2);after=events()[offset:]
        assert not any(v['kind']=='RB_SPEECH' and v.get('status')=='STARTED' for v in after)
        assert any(v['kind']=='RB_GATE' and not v['quietConfirmed'] and v['foreground'] and v['visible'] for v in after)
        screenshot('ready-to-test')
        result.update(status='PASS_FINAL_NATIVE_AUDIO_COLLECTION_COLD_RESTORE',requestId=request_id,characterId=a['characterId'],common=common,arrival=arrival,capture=capture,measurement=measurement,
            saved=saved,boundaries=boundaries,restored=restored,ready=ready,returnAutomaticSpeech=False,quietConsentRestored=False,
            humanListeningOrVoiceQualityApproved=False,calibratedAcousticIdentityVerdict=False)
    except Exception as e:result['error']=str(e)
    finally:
        if recording is not None:recording.abort()
        try:(args.output_dir/'runtime-events.jsonl').write_text(''.join(json.dumps(v,ensure_ascii=False)+'\n' for v in events()))
        except Exception:pass
        (args.output_dir/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({k:result.get(k) for k in ('status','error','requestId','characterId')},ensure_ascii=False))
    return 0 if result['status'].startswith('PASS_') else 1

if __name__=='__main__':raise SystemExit(main())
