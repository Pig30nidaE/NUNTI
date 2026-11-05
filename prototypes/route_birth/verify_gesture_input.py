#!/usr/bin/env python3
"""Actual emulator text fields, touch route and Create button. Creates one fresh local journey.

Synthetic inputs only. No submit intent or pre-generated request is used. This is a
viewport-specific UI check for the existing2560x1440 Pleos emulator; it never clears app data.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import time
from urllib.request import urlopen
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
ADB=ROOT/'.local/pm-tools/sdk/platform-tools/adb'
PACKAGE='ai.nunti.avatar.demo'
COMPONENT=PACKAGE+'/ai.nunti.app.routebirth.RouteBirthActivity'

def sha(b): return hashlib.sha256(b).hexdigest()
def now(): return datetime.now(timezone.utc).isoformat()

def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    out=args.output;out.mkdir(parents=True,exist_ok=False)
    serial='emulator-5554';user='10'; prefix=[str(ADB),'-s',serial]
    report={'status':'FAIL','startedAt':now(),'scope':'Real text/touch/button flow, synthetic UI data, current user namespace; creates one fresh local-model journey.'}
    recorder=None
    def adb(*values,binary=False):
        result=subprocess.run(prefix+list(values),check=True,capture_output=True,timeout=30)
        return result.stdout if binary else result.stdout.decode()
    def private(path): return adb('exec-out','run-as',PACKAGE,'--user',user,'cat',path,binary=True)
    def events():
        raw=private('files/route-born-events.jsonl')
        return [json.loads(x) for x in raw.splitlines() if x]
    def screenshot(name):
        raw=adb('exec-out','screencap','-p',binary=True); assert struct.unpack('>II',raw[16:24])==(2560,1440)
        (out/(name+'.png')).write_bytes(raw)
    def xml():
        adb('shell','uiautomator','dump','/sdcard/route-born-gesture-ui.xml')
        raw=adb('exec-out','cat','/sdcard/route-born-gesture-ui.xml');(out/'ui-hierarchy.xml').write_text(raw)
        return ET.fromstring(raw)
    def tap(node):
        import re
        x1,y1,x2,y2=map(int,re.findall(r'\d+',node.attrib['bounds']))
        adb('shell','input','tap',str((x1+x2)//2),str((y1+y2)//2))
    def wait(predicate,timeout=90):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            rows=events()[offset:]
            match=next((v for v in rows if predicate(v)),None)
            if match:return match
            errors=[v for v in rows if v['kind']=='RB_ERROR']
            if errors:raise AssertionError(errors[-1])
            time.sleep(.1)
        raise AssertionError('Runtime event timeout')
    try:
        assert adb('shell','am','get-current-user').strip()==user
        adb('shell','am','force-stop','--user',user,PACKAGE)
        adb('shell','am','start','-W','--user',user,'-n',COMPONENT)
        time.sleep(1)
        screenshot('input-empty-before')
        before=events(); offset=len(before)
        tree=xml();fields=[n for n in tree.iter('node') if n.attrib.get('class')=='android.widget.EditText']
        assert len(fields)==3,'Expected three actual editable input fields'
        for field,value in zip(fields,('SeoulForest','Forest','Relax')):
            tap(field);adb('shell','input','text',value);adb('shell','input','keyevent','KEYCODE_BACK')
        # The route canvas bounds come from the directly inspected native screenshot.
        points=[(910,590),(935,520),(980,480),(1020,550),(1070,590),(1115,520),(1150,470)]
        adb('shell','input','motionevent','DOWN',str(points[0][0]),str(points[0][1]))
        for x,y in points[1:]:adb('shell','input','motionevent','MOVE',str(x),str(y))
        adb('shell','input','motionevent','UP',str(points[-1][0]),str(points[-1][1]))
        screenshot('typed-fields-and-gesture-route')
        tree=xml(); create=next(n for n in tree.iter('node') if n.attrib.get('text')=='동반자 만나기')
        recorder=subprocess.Popen(prefix+['shell','screenrecord','--size','1280x720','--bit-rate','2000000','--time-limit','12','/sdcard/route-born-gesture.mp4'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        time.sleep(.5);tap(create)
        submitted=wait(lambda v:v['kind']=='RB_SUBMITTED' and v['namespace']=='route-birth')
        request_id=submitted['requestId'];report['requestId']=request_id
        visual=wait(lambda v:v['kind']=='RB_VISUAL' and v['requestId']==request_id)
        screenshot('route-trace')
        wait(lambda v:v['kind']=='RB_ANIMATION' and v.get('requestId')==request_id and v.get('stage')=='ROUTE_TO_BODY')
        time.sleep(.9);screenshot('mid-route-to-body')
        wait(lambda v:v['kind']=='RB_ANIMATION' and v.get('requestId')==request_id and v.get('stage')=='COMPLETE')
        screenshot('born-companion')
        ready=wait(lambda v:v['kind']=='RB_READY' and v['requestId']==request_id)
        screenshot('voice-ready')
        input_value=json.loads(private(f'files/route-birth/{request_id}/input.json'))
        assert input_value['destination']['name']=='SeoulForest' and input_value['destination']['traits']=='Forest' and input_value['purpose']=='Relax'
        assert 2<=len(input_value['route']['points'])<=512
        with urlopen('http://127.0.0.1:8766/v1/journeys/'+request_id,timeout=10) as response:server=json.load(response)
        artifact=server['artifact'];assert server['state']=='READY'
        assert json.loads(artifact['inputCanonical'])==input_value and sha(artifact['inputCanonical'].encode())==artifact['inputSha256']
        hashes={}
        for clip in artifact['voiceManifest']['clips']:
            raw=private(f"files/route-birth/{request_id}/voice/{clip['audioPath']}")
            assert sha(raw)==clip['audioSha256'];hashes[clip['clipId']]=sha(raw)
        (out/'input.json').write_text(json.dumps(input_value,ensure_ascii=False,indent=2)+'\n')
        (out/'ready.json').write_text(json.dumps(server,ensure_ascii=False,indent=2)+'\n')
        # Speech starts via the actual visible buttons too.
        tree=xml();tap(next(n for n in tree.iter('node') if n.attrib.get('text')=='음성 시험 시작'))
        tree=xml();tap(next(n for n in tree.iter('node') if n.attrib.get('text')=='인사 듣기'))
        request=wait(lambda v:v['kind']=='RB_SPEECH_REQUEST' and v['tripId']==request_id)
        terminal=wait(lambda v:v['kind']=='RB_SPEECH' and v['requestId']==request['requestId'] and v['status'] in ('COMPLETED','CANCELLED','FAILED','REJECTED'))
        assert terminal['status']=='COMPLETED',terminal
        screenshot('greeting-completed')
        report.update(status='PASS_REAL_TEXT_GESTURE_BUTTON_GENERATION_AND_GREETING',characterId=artifact['characterId'],
            source='actual native fields + touch path + create button; no submit intent',pointCount=len(input_value['route']['points']),
            installedWavHashes=hashes,submitted=submitted,visual=visual,ready=ready,speechRequest=request,speechTerminal=terminal,
            apkRebuiltDuringInput=False,perceptualUniquenessOrHumanVoiceFitApproved=False)
    except Exception as error:report['error']=str(error)
    finally:
        if recorder is not None:
            try:
                stdout,stderr=recorder.communicate(timeout=15)
                report['screenrecordExit']=recorder.returncode;report['screenrecordStderr']=stderr.decode(errors='replace')[-1200:]
                if recorder.returncode==0:
                    raw=adb('exec-out','cat','/sdcard/route-born-gesture.mp4',binary=True)
                    if len(raw)>1000:(out/'route-birth-real-ui.mp4').write_bytes(raw);report['videoSha256']=sha(raw)
            except Exception as e:report['videoError']=str(e)
        try:
            rows=events()[offset:];(out/'runtime-events.jsonl').write_text(''.join(json.dumps(v,ensure_ascii=False)+'\n' for v in rows))
        except Exception:pass
        report['finishedAt']=now();(out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({k:report.get(k) for k in ('status','error','requestId','characterId')},ensure_ascii=False))
    return 0 if report['status'].startswith('PASS_') else 1

if __name__=='__main__':raise SystemExit(main())
