#!/usr/bin/env python3
"""Offline recheck of actual route-born APK, model artifacts and saved native evidence. No model/device/network."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
import wave

ROOT=Path(__file__).resolve().parents[1]
HERE=ROOT/'prototypes/route_birth'
sys.path.insert(0,str(HERE))
from generator import canonical,digest,make_plan

def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def require(value,message):
    if not value:raise ValueError(message)
def sealed(path):
    value=read(path);require(value['sha256']==digest(value['body']),'Sealed JSON changed: '+str(path));return value['body']

def main():
    report={'status':'FAIL','at':datetime.now(timezone.utc).isoformat(),'scope':'Saved files/raw events only; no new generation, device interaction or human taste evaluation.'}
    evidence=[HERE/'qa-evidence-01.json',HERE/'gesture-runtime-01/verification.json',HERE/'final-native-01/verification.json',HERE/'restart-01/verification.json',HERE/'delivered-apk.json',HERE/'user-ready-verification.json']
    try:
        qa,gesture,final,restart,delivery,user_ready=map(read,evidence)
        require(qa['status']=='PASS_INDEPENDENT_FOUR_JOURNEY_ROUTE_BIRTH_EVIDENCE','Independent QA not passed')
        require(gesture['status']=='PASS_REAL_TEXT_GESTURE_BUTTON_GENERATION_AND_GREETING','Actual gesture path not passed')
        require(final['status']=='PASS_FINAL_NATIVE_AUDIO_COLLECTION_COLD_RESTORE','Final native proof not passed')
        require(restart['status'].startswith('PASS'),'Actual worker restart not passed')
        require(sha(Path(delivery['apk']))==delivery['apkSha256'],'Delivered APK changed')
        require(user_ready['status']=='PASS_INSTALLED_FINAL_APK_LAUNCHER_AND_USER_STATE' and user_ready['apkSha256']==delivery['apkSha256'] and user_ready['automaticSpeechAfterRestore'] is False,'Final installed artifact observation missing')
        for path,expected in delivery['sourceFileSha256'].items():require(sha(ROOT/path)==expected,'Native source changed: '+path)
        for path,expected in qa['evidenceSha256'].items():require(sha(HERE/path)==expected,'Independent evidence changed: '+path)
        artifacts=[];clips={}
        tested_ids={read(p)['requestId'] for p in (HERE/'synthesis-01').glob('case-*-request.json')}
        tested_ids.add(qa['checks'][3]['freshNativeRequestId']);tested_ids.add(gesture['requestId'])
        require(len(tested_ids)==5,'Recorded sample identities differ')
        jobs=ROOT/'.local/route-birth/jobs'
        for directory in [jobs/request_id for request_id in sorted(tested_ids)]:
            require(directory.is_dir() and not directory.is_symlink(),'Unexpected job entry')
            plan=sealed(directory/'plan.json');artifact=sealed(directory/'result.json')
            require(plan==make_plan(plan['request'],plan['engineFingerprint'],plan['engineIdentity']),'Current rule/committed plan differs')
            require(artifact==dict(plan['artifact'],voiceManifest=artifact['voiceManifest']),'READY changed initial identity/visual/voice')
            require(json.loads(artifact['inputCanonical'])==plan['request'] and hashlib.sha256(artifact['inputCanonical'].encode()).hexdigest()==artifact['inputSha256'],'Input join changed')
            for clip in artifact['voiceManifest']['clips']:
                category=clip['clipId'].rsplit('-',1)[1];path=directory/'clips'/category/'audio.wav'
                require(sha(path)==clip['audioSha256'],'Source WAV hash changed')
                metadata=sealed(path.parent/'metadata.json')
                require(metadata['source']==clip['source'] and metadata['characterId']==artifact['characterId'] and metadata['text']==clip['text'],'WAV source join changed')
                require(clip['source']['bindingId']==artifact['voice']['bindingId'] and clip['profileId']==artifact['voice']['profileId'],'Voice binding changed')
                require(clip['source']['directionSha256']==hashlib.sha256(artifact['voice']['direction'].encode()).hexdigest(),'Direction changed')
                with wave.open(str(path),'rb') as wav:
                    require((wav.getnchannels(),wav.getsampwidth(),wav.getframerate())==(1,2,24000),'Wrong PCM format')
                    require(any(wav.readframes(wav.getnframes())),'Silent WAV')
                clips[clip['clipId']]=clip
            artifacts.append(artifact)
        require(len(artifacts)==5 and len(clips)==15,'Actual delivered sample count differs from recorded scope')
        require(len({canonical(a['visual']) for a in artifacts})==5,'Actual visuals are not distinct')
        require(gesture['characterId']==final['characterId'],'Final restored identity differs')
        rows=[]
        for path in (HERE/'native-runtime-02/runtime-events.jsonl',HERE/'native-runtime-03/runtime-events.jsonl',HERE/'gesture-runtime-01/runtime-events.jsonl',HERE/'final-native-01/runtime-events.jsonl'):
            rows.extend(json.loads(line) for line in path.read_text().splitlines() if line)
        requests={v['requestId']:v for v in rows if v['kind']=='RB_SPEECH_REQUEST'}
        completed=set()
        for row in rows:
            if row['kind']=='RB_SPEECH' and row.get('status')=='COMPLETED':
                req=requests[row['requestId']];clip=clips[req['clipId']]
                require(req['characterId']==clip['characterId'] and req['profileId']==clip['profileId'] and req['audioSha256']==clip['audioSha256'],'Native completed source differs')
                completed.add(req['clipId'])
        require(len(completed)>=11,'Expected actual unique native completions missing')
        require(final['boundaries']['passed']==9 and final['returnAutomaticSpeech'] is False and final['quietConsentRestored'] is False,'Final lifecycle proof differs')
        require('BUILD SUCCESSFUL' in (HERE/'android-build-final-delivery.log').read_text(),'Final build missing')
        report.update(status='PASS_ROUTE_BIRTH_DELIVERY_EVIDENCE',newJourneys=5,newActualWavClips=15,
            distinctSampledVisuals=5,additionalJobsOutsideRecordedScope=sum(p.is_dir() and p.name not in tested_ids for p in jobs.iterdir()),uniqueNativeCompletedClips=len(completed),finalApkSha256=delivery['apkSha256'],
            genuineUiCreatedRequestId=gesture['requestId'],androidBoundaryChecks=9,
            originalNativeWholeRunStatus=read(HERE/'native-runtime-02/verification.json')['status'],
            nativeQaApk=read(HERE/'native-qa-tested-apk.json')['apkSha256'],
            finalApkRetestScope='Direct fields/touch/Create, trace/morph/reveal, all three fifth-journey clips, guest-speaker PCM, collection/cold restore and nine native boundaries. Prior policy suite APK differs only in two UI texts and feet reveal timing.',
            evidenceSha256={str(p.relative_to(ROOT)):sha(p) for p in evidence},
            notVerified=['Human cuteness/collectibility/voice naturalness or fit','Global perceptual uniqueness','New-host actual D/P transition or physical vehicle','Map routing/GPS journey feed','Android model inference or unique speaker cloning'])
    except Exception as e:report['error']=str(e)
    (HERE/'delivery-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report.get(k) for k in ('status','error','newJourneys','newActualWavClips','uniqueNativeCompletedClips')},ensure_ascii=False))
    return 0 if report['status'].startswith('PASS_') else 1

if __name__=='__main__':raise SystemExit(main())
