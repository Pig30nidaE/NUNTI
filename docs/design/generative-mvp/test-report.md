# 생성 동반자 v2 구현·검증 보고

이 문서는 최초 v2 연결 검증의 기록이다. 최신 탄생 연출·설치 APK·녹화 없는 최종 회귀는 [후속 연출 보고](route-formation.md)와 [현재 검증 JSON](verification.json)을 따른다. 아래 APK 해시와 캡처는 최초 검증 시점의 근거를 보존한다.

2026-11-03, Asia/Seoul. 승인된 API 기반 생성 구조를 구현하고, 기존 PNG/WAV를 사용하는 샘플 모드로 실제 Pleos Android 연결을 검증했다. 이번 실행에서 공급자 API·유료 요청·새 모델 추론은 모두 0회다. 새 이미지와 새 음색의 품질을 검증했다는 의미는 아니다.

## 완료

| 담당 | 구현과 확인 결과 |
|---|---|
| SERVER | 목적지·특성·목적·경로를 받는 v2 생성 작업, 독립 작업자, 불변 소장품, 인증 미디어, 공급자 영수증·예산·음성 슬롯 검사, 재시도/복원, 같은 본문 WAV 재사용, 같은 voiceId의 후속 대사 |
| AVATAR | 완성 RGBA 이미지의 경로 추적→빛→공개, 전체 호흡·둥실거림·기울기·그림자, 준비 전 이미지 비공개 |
| TTS | DesignedVoice/manifest3, 공급자·모델·spec·설정·voiceId 바인딩, 전체 파일 SHA/PCM 검증, 기존 재생 큐·반복 억제를 유지한 대사 추가 |
| PM·Android | 실제 목적지 입력·경로 터치·작업 조회·다운로드·표시·듣기·중지·후속 대사·도착·보관·cold restore, 실행/검증 스크립트와 테스트 안내 |
| 평가 도구 | 초기 20개 입력, 두 파이프라인 공통 6개 입력의 비교를 포함한 최대 26개 결과, 블라인드 평가·실비 비교·샘플 품질 승인 거부 |
| 운영 도구 | 실제 영수증을 반영하는 비용 확정 CLI, Google 음성 만료 dry-run·월별 유지 작업 제출, graceful worker 종료·재시작 |

API 어댑터는 주 파이프라인 Sol→Flare→ElevenLabs와 Google 비교 파이프라인을 지원한다. ElevenLabs는 임시 음색 preview 3개 중 하나를 저장하고, Google는 저장 슬롯을 낭비하지 않도록 음색 1개를 만든다. 상대 모델 평가는 사람의 품질 승인을 대신하지 않는다. [모델·정체성·비용 설계](README.md), [서버 실행/운영](../../../backend/README.md), [v2 계약](../../../contracts/v2/README.md)을 참고한다.

## 실제 검증 근거

| 검증 | 결과·범위 |
|---|---|
| 서버 | 전체 132개 통과, 이 중 신규 v2 41개. Ruff 통과. 공급자 통신은 주입 응답으로 검증 |
| TTS | 기존 core 62개·연동 8개, local 49개·실제 재사용 WAV 3개, production JSON parser 17개 통과 |
| AVATAR | 4,004 준비/공개 frame과 경로·64/128px 배치·원본 RGBA/SHA 검사 통과 |
| Android 빌드 | debug·release·lint 통과. lint 오류 0, 경고 3 |
| 실제 화면 조작 | 입력란·그리기·생성/듣기 버튼을 조작. 서버에 전달된 경로 43점 확인 |
| 실제 음성 출력 | 인증된 에뮬레이터 speaker stream에 비영점 PCM 543,088 sample 확인. 사람의 청취 판정은 수행하지 않음 |
| 실제 lifecycle | 초기 3개 WAV, 같은 음색의 후속 clip 추가·완료, 자동 발화 없음, 대사 추가 후 반복 억제 유지, 중지·background 취소, 도착·보관·cold restore 통과 |
| 경계 검사 | 실제 Android parser/store에서 잘못된 연결·이미지·음성·바인딩 등 10개 거부 확인 |
| 재시작 | 정상 종료·재시작 뒤 기존 artifact 불변, 새 샘플 작업 READY 1.859초. 공급자 호출 0회 |
| 작업자 복구 | API 서버를 유지한 상태에서 도구가 소유한 작업자만 종료한 뒤 다시 실행해 새 작업자 복구 확인 |
| 전달물 확인 | 설치 APK 해시 일치, 같은 요청 재시도 결과 불변, 인증된 자산 4개 SHA 일치, 무인증 자산 접근 차단 |

자동 취합 결과는 [verification.json](verification.json)이다. 원본 시험 기록을 수정하지 않고 [증거 사본과 해시](evidence/manifest.json)를 남겼다.

- [서버 검사·소스 해시](../../../backend/reports/generation-v2-verification.json), [서버 pytest 원본](../../../backend/reports/generation-v2-pytest.log)
- [AVATAR 검사](../../../android/feature/avatar/reports/generated-companion-qa.md), [TTS 검사](evidence/tts/designed-schema3-verification.log), [실제 JSON parser 검사](evidence/tts/designed-parser-verification.log), [lint 원본](evidence/lint-results-debug.xml)
- [Android 미디어/lifecycle](evidence/native/verification.json), [해당 이벤트](evidence/native/events.jsonl), [복원 화면](evidence/native/cold-restored.png)
- [실제 입력/터치/스피커](evidence/touch/verification.json), [PCM 통계](evidence/touch/speaker.summary.json), [입력 화면](evidence/touch/typed-route.png), [준비 화면](evidence/touch/ready.png)
- [재시작 기록](evidence/restart-verification.json), [작업자 복구 기록](evidence/worker-recovery-verification.json), [벤치마크 도구 검증](benchmark/verification.json), [인수인계 검사](evidence/handoff-check.json)

검증 APK는 `.local/generative-mvp/Nunti-Generative-MVP-debug.apk`이며 SHA256은 `2e3b919b79476e536862454a5a042521053fc4f23ce905a40de912b81f3ecb17`이다. 원본 native 기록은 `.local/generative-mvp/native-20261102-180824/`, 실제 터치/PCM 원본은 `.local/generative-mvp/touch-20261102-180523/`에 있다. PCM 원본 파일·packet 기록은 그 로컬 폴더에 보존한다.

## 미구현·이번 범위 밖

- 지도/GPS/NaviHelper의 실제 경로 연결, 차량 상태·운전 이벤트·외부 점수/최종 코멘트 입력의 제품 통합. 사용자의 초기 단계 보류 지시를 유지한다.
- 얼굴 부위별 rig·독립 눈/입 애니메이션·완전한 3D. 이번 구현은 얼굴이 포함된 전체 이미지의 움직임이다.
- 운영 로그인·토큰 발급/회전·공개 TLS 배포·백업 운영, 실제 음성 유지 작업의 자동 스케줄. 현재 앱 진입은 Debug MVP다.

## 미검증

- 실제 계정의 모델 접근·요청 호환성·Voice Design 요금·잔여 슬롯·속도·오류 응답·실제 청구액. 어댑터 구현과 모의 응답 통과를 실계정 검증으로 확대하지 않는다.
- 매 여정 새 이미지·새 음색을 만드는 실제 API 생성, 한국어 자연스러움, 귀여움·소장 의향, Anna 선호에 부합하는 음색. 이전 로컬 음성 실험은 사용자가 부족하다고 평가한 기록을 유지한다.
- 두 API 파이프라인의 품질 승자와 여정당 $0.10–0.30 목표 달성. 20개 입력/최대 26개 출력의 실제 API 비교는 아직 실행하지 않았다.
- Google 저장 음색의 실제 TTL 연장·장기 보관, 실차·장시간·주행 중 실제 통화/내비 경합, 운전 습관 개선 효과.

샘플은 기존 해안 PNG 1개와 기존 Sohee WAV를 사용한다. PNG에 접지 그림자가 포함돼 있어 앱의 그림자와 겹치는 부분도 있다. 이 샘플의 화면 연결 통과를 새 API 디자인·알파 경계·음성 품질 승인으로 처리하지 않는다. API 모드에서 키·가격 설정이 없으면 외부 호출 전에 실패하며 샘플이나 Sohee로 자동 대체하지 않는다.

## 사용자가 시험하는 방법

복원된 Mac에서 다음 명령을 실행하면 로컬 샘플 서버·작업자와 Pleos 앱을 연다.

```sh
cd /Users/pig30nidae/NUNTI
python3 scripts/run_generative_mvp.py
```

[시험 안내](TESTING.ko.md)의 입력·듣기·후속 대사·소장품 복원 순서로 확인한다. 지금 확인할 수 있는 것은 생성 시스템의 연결과 재생·보관 경험이다. 실제 입력을 반영한 새 이미지·새 음색 생성은 계정 연결 후 같은 v2 경로로 검증한다.
