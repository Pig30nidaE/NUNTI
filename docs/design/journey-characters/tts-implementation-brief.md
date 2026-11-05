# 여정 캐릭터의 실제 음성 연결

2026-11-02 사용자가 "TTS까지는 이어서 진행해주세요"라고 요청했다. 이전 proposal-only 범위에서 이어서 실제 음성 합성·파일·재생 연결을 구현한다. 목적지·경로·목적의 창작 의미와 기존 도로·운전 사실의 분리는 유지한다. 외부 feed 협의·점수 생성·운영 배포는 포함하지 않는다.

## 구현 형태와 선택

호출자는 저장된 캐릭터 레시피와 승인된 원문을 준다. 로컬 합성 도구가 처음 정한 화자·리듬 binding을 보존하고 정확한 원문에 대한 WAV를 만든다. Android는 검증한 파일만 기존 단일 정책·큐·포커스·lifecycle 경로로 재생한다.

| 대안 | 이번 판단 |
| --- | --- |
| 기존 Pleos 화자 메서드만 연결 | 허용 speaker 문자열과 한국어 품질이 미확인. 임의 문자열로 고유 음색을 구현했다고 보고하지 않음 |
| 별도 유료 클라우드 합성 | 자격 증명·사용 계정·실제 공급 조건이 미설정. 이번 표본 생성의 선행 조건으로 두지 않음 |
| 공개 ONNX 모델로 로컬 합성 후 정확 문장 WAV 재생 | 이번 실험으로 선택. 한국어 여러 실제 화자를 만들고 보존·원문 매칭·정책을 검증. Android 내 모델 배포와 운영 공급자 선정은 별도 |

실험 모델은 공식 아카이브의 [Supertonic 3](https://huggingface.co/supertone-oss-archive/supertonic-3)다. [원본 코드](https://github.com/supertone-oss-archive/supertonic)는 유지보수가 종료됐다. 이 실험 선택은 운영 권고나 음질 승인 완료를 뜻하지 않는다. 모델·소스 revision, 실제 runtime, 화자 preset과 라이선스를 산출물에 고정한다. 유료 서비스나 음성 복제는 사용하지 않는다.

## 소유 범위

- PM의 로컬 합성 담당은 `prototypes/journey_voice/`와 ignored `.local/journey-voice/`를 소유한다. 기존 레시피 입력과 연결하고 실제 WAV·binding ledger·manifest·재현 명령을 만든다.
- 기존 TTS 채팅은 `.worktrees/tts`에서 `android/feature/tts`, `android/feature/voice`, Debug 전용 `RuntimeProbeActivity`의 최소 연결을 소유한다. 정책·큐를 복제하지 않는다. 완성 뒤 PM이 실제 diff를 읽고 루트로 취합한다.
- PM의 런타임 담당은 새 `scripts/record_emulator_audio.py`와 별도 실행 노트를 소유한다. 기존 복원 증거를 덮어쓰지 않고 새 PCM과 callback을 구분한다.
- 공통 wire v1·backend·production host·기존 아바타 엔진·Gradle은 이번에 조용히 변경하지 않는다. 최소 추가 영향이 생기면 PM이 범위를 재검토한다.

## Android 전달용 manifest

현재 전달본은 `prototypes/journey_voice/samples-v2/manifest.json`이다. 아래 v1 예시는 초기 설계 기록이며 실제 parser 필드는 [최종 구현 보고](tts-implementation.md)를 따른다. `bindingId`·`preset`·nested `binding`·catalog digest·DSP provenance를 포함한다. 선택 키에는 characterId도 포함한다. 합성 실험의 파일 경계이며 공통 wire 계약이 아니다. Debug에 복사할 때는 manifest와 참조 WAV만 포함하고 큰 모델은 포함하지 않는다.

```json
{
  "schemaVersion": 1,
  "providerId": "supertonic3-local-catalog",
  "clips": [
    {
      "clipId": "example",
      "characterId": "prototype-character-id",
      "profileId": "nunti-keepsake-calm-v1",
      "speakerId": "actual-model-speaker-id",
      "locale": "ko-KR",
      "text": "안녕하세요. 오늘의 여행도 함께할게요.",
      "textSha256": "actual-utf8-sha256",
      "audioPath": "example.wav",
      "audioSha256": "actual-file-sha256",
      "sampleRateHz": 44100,
      "channels": 1,
      "durationMs": 5000,
      "sourceModelRevision": "actual-pinned-revision"
    }
  ]
}
```

수치·ID는 형식 예시이며 실제 산출물로 채운다. 세 비교 profile은 해안 휴식 `nunti-keepsake-calm-v1`, 산악 캠핑 `nunti-keepsake-curious-v1`, 전시 `nunti-keepsake-clear-v1`다. 같은 문장으로 실제 화자 차이를 비교한 뒤 각자의 인사를 추가한다. 화자는 합성 가능 여부를 확인한 청취 후보이며 귀여움·자연스러움이 사용자 평가를 통과했다는 뜻은 아니다.

선택 키는 profile·speaker·정확한 원문 UTF-8 digest다. 파일 digest·형식도 검증한다. 일치하는 자산이 없거나 손상되면 명시적으로 실패하며 다른 목소리로 읽지 않는다. 같은 캐릭터의 재시도·reroute·재시작은 저장 binding을 사용한다. 아카이브 모델의 새 실행이 같은 파형을 만든다고 약속하지 않고 이미 생성한 실제 WAV를 보존한다.

## 완료를 판단할 증거

완료 보고 전 실제 레시피→binding→합성 WAV→manifest 경로를 실행한다. 각 파일의 실제 파형·길이·해시와 원문을 검사하고 같은 캐릭터의 복원·새 문장·없는 자산을 구분한다. Android는 실제 파일로 STARTED·COMPLETED와 중지·background·중복·주행 정책 차단을 확인한다. 가능하면 별도 인증된 에뮬레이터 PCM을 수집한다.

SDK callback 지연, 첫 가청 샘플, 취소 후 실제 무음은 서로 다른 값이다. 사람의 한국어 발음·귀여움·캐릭터 적합성 평가는 별도 미검증으로 남긴다. 기존 전역 기본 음성·메타데이터만 바꾼 상태를 실제 캐릭터별 음색 구현 완료로 보고하지 않는다.
