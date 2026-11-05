# 경로에서 태어나는 동반자: 오프라인 PC 생성기

목적지·특성·이동 목적과 사용자가 그린 경로를 받아, 그 경로에서 연속적인 72점 윤곽을 만들고 어울리는 말투로 새 음원 세 개를 합성합니다. 이전 8개 여정이나 16개 윤곽을 불러와 고르는 방식이 아닙니다.

이 구현은 **절차적 기하 생성**입니다. 그림 생성 모델이나 새 화자 복제는 사용하지 않습니다. 캐릭터 ID는 요청 UUID에 묶이고, 실루엣은 경로의 비례·길이·방향·굴곡·조화 성분과 여정별 잡음으로 달라집니다. 모든 가능한 경로 쌍이 사람에게 다르게 보인다는 보장은 하지 않습니다. 생성 음성은 캐시된 Sohee 한 화자에서, 실제 생성 외형의 비례·색감과 여정 목적에 맞춰 연기를 바꿉니다. Anna에 대한 선호는 바뀌지 않았습니다.

## 실행

저장소 루트에서 기존 환경만 사용합니다. 새 계정·외부 API·패키지 설치·모델 다운로드는 필요하지 않습니다.

```sh
.local/journey-voice-v3/venv/bin/python prototypes/route_birth/worker.py serve --workspace .local/route-birth --port 8766
```

서버는 `127.0.0.1`에만 바인딩합니다. Android 에뮬레이터는 아래 역방향 포트로 이 Mac의 작업자와 통신합니다. 모델이 Android에서 실행되는 것은 아닙니다.

```sh
.local/pm-tools/sdk/platform-tools/adb reverse tcp:8766 tcp:8766
```

앱 실행과 사용자 흐름은 [직접 시험하기](TESTING.ko.md)를 따릅니다. 이 문서는 PC 작업자의 계약과 재현 방법을 설명합니다.

## 입력과 상태

`POST /v1/journeys`에 정확히 다음 필드를 보냅니다. 좌표는 손으로 그린 경로의 로컬 정규화 좌표입니다. GPS·실제 도로·길 찾기 결과를 뜻하지 않습니다.

```json
{
  "requestId": "a96e5ac0-ec43-4cb4-9671-403a3718aa7b",
  "destination": {"name": "노을 바다", "traits": "따뜻한 노을과 바다"},
  "purpose": "휴식",
  "route": {"points": [[0.1,0.8],[0.3,0.3],[0.7,0.5],[0.9,0.1]]}
}
```

- 목적지 이름은 1..60 UTF-16 단위, 특성은 0..240, 목적은 0..120입니다. 제어 문자와 잘못된 Unicode 입력은 거절합니다.
- 경로는 유한한 0..1 좌표 2..512개이며, 전체 길이는 0보다 커야 합니다.
- 같은 `requestId`와 같은 정규화 입력을 재전송하면 같은 캐릭터·음원이 돌아옵니다. 같은 ID에 다른 입력은 `409`로 거절합니다. 새 여행에는 새 UUID를 사용합니다.
- 최초 `GENERATING` 응답에도 실제 경로·윤곽·외형·음성 설명·결합 ID가 있습니다. 합성 완료 전에는 `voiceManifest`가 없습니다.
- `GET /v1/journeys/<requestId>`로 상태를 읽습니다. `READY`에는 기존 Android `LocalVoiceManifest` schema 2의 인사·도착·공통 음원 3개가 있습니다. 실패는 `FAILED`로 표시하고 자동 음성 대체를 하지 않습니다.
- `GET /v1/journeys/<requestId>/audio/<audioPath>`는 그 요청의 최종 manifest에 확정된 WAV만 반환합니다.
- `GET /health`는 모델 작업 중에도 응답합니다. 합성 작업은 한 스레드에서 순서대로 처리합니다.

`inputCanonical`은 서버가 정규화한 요청의 정확한 JSON 문자열입니다. Android는 이 문자열의 SHA-256과 `inputSha256`를 비교하고, 다시 파싱한 값이 앱이 저장한 요청과 같은지도 확인합니다. 입력의 출처를 문자열 포맷 차이 없이 검증하기 위한 필드입니다.

## 저장과 복구

`.local/route-birth/jobs/<requestId>/`만 사용하며 이전 실험 상태는 수정하지 않습니다. 목적지·그린 경로는 이 비공개 로컬 캐시에 저장되고 HTTP 진단 로그에는 남기지 않습니다.

`plan.json`에는 정규화 입력·캐릭터·윤곽·음성 방향·텍스트·고정 엔진 정보가 원자적으로 확정됩니다. 각 `clips/<category>/`는 WAV와 해시·음성 결합 메타데이터를 함께 만든 뒤 디렉터리 단위로 확정합니다. 마지막 `result.json`은 세 클립을 실제로 다시 읽어 WAV 형식·프레임·SHA·캐릭터·방향 결합을 검사한 후 확정합니다.

작업자가 재시작하면 확정된 클립은 원본 바이트를 유지하고 미완료 부분만 이어 갑니다. 아직 공개되지 않은 임시 클립은 버립니다. 확정된 파일의 삭제·변조나 엔진 핀 변경은 실패로 처리하며 자동으로 덮어쓰지 않습니다. 터미널 실패는 같은 ID 재전송으로 재합성하지 않습니다. 원인을 해결한 새 여행에는 새 UUID가 필요합니다.

## 실제 검증

[단위·충돌·복구 테스트](test_worker.py)는 테스트용 PCM 생성기를 주입합니다. 서버 실행 경로는 이 가짜 생성기를 가져오지 않습니다.

```sh
python3.12 prototypes/route_birth/test_worker.py -v
```

[형상 강화 후 결과](unit-tests-after-shape.log): 15개 테스트 통과. 10개 프로세스 중단 지점에서 실제 `os._exit(86)`를 일으킨 뒤 새 프로세스로 복구했고, 중단 전 확정한 바이트를 유지했습니다. 입력 오류·중복·충돌·최대 목적지 길이·재시작·파일 삭제/변조·모델 실패·허용되지 않은 경로도 검사합니다.

[실제 합성 실행 도구](synthesize_cases.py)는 실행 중인 로컬 서버에 새 UUID 세 개와 서로 다른 경로를 제출하고, 각 READY 응답의 WAV를 다시 내려받아 SHA를 확인합니다.

```sh
.local/journey-voice-v3/venv/bin/python prototypes/route_birth/synthesize_cases.py --output prototypes/route_birth/synthesis-new-run
```

[첫 실제 실행](synthesis-01/synthesis-result.json)은 속초 영금정·대관령 양떼목장·성수 서울숲 입력으로 9개 **새** WAV를 42.58초에 합성했습니다. 합성 중 health 43회가 응답했고 최대 관측 지연은 15.2ms였습니다. 외부 API·새 모델 다운로드·이전 음원 재사용은 없습니다. 실제 경로·윤곽·음성 결합·WAV 해시는 [입력/응답/음원 원본](synthesis-01)에 보관되어 있습니다.

3개 실루엣의 정규화 좌표 RMSE는 0.02175..0.03761입니다. 이 수치는 실제 다른 기하를 생성했다는 관측이며, 귀여움·소장 욕구·음성 자연스러움·운전 습관 개선의 합격 판정은 아닙니다. 앱의 실제 렌더링·재생·보관·주행 게이트 검증은 별도 QA 자료를 확인해야 합니다.

[실제 작업자 재시작 결과](restart-01/verification.json)는 앱이 추가로 생성한 두 여행을 포함한 5개 READY 결과를 검사했습니다. 정상 CLI의 서버 프로세스를 한 번 종료·재시작한 뒤, READY 응답 5개·WAV 15개·원본 파일 40개의 해시가 모두 같았습니다. 기존 정규화 입력 5개를 다시 제출해도 각각 `200 READY`와 같은 응답 바이트를 받았습니다. 생성기와 작업자 소스도 바뀌지 않았습니다. 모델 호출 계수는 직접 관측하지 않았습니다.

```sh
python3.12 prototypes/route_birth/audit_restart.py before --output prototypes/route_birth/restart-new-run
# 기존 정상 CLI 작업자를 종료하고 같은 명령으로 다시 실행합니다.
python3.12 prototypes/route_birth/audit_restart.py after --output prototypes/route_birth/restart-new-run
```

재시작 검사는 위 실제 5개 여행·15개 음원이 존재하는 전달 상태를 기준으로 합니다. 새 여행을 추가한 상태에서는 개수 검사를 갱신해야 합니다.

현재 전체 검증은 [새 입력5개·15새WAV·실제 사용자 조작 결과](../../docs/design/route-birth/test-report.md)를 따른다. 위 첫3개 합성 기록은 초기 PC 검증 범위로 보존한다.
