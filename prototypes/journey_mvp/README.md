# API 없는 여정 MVP 시험

[앱을 직접 시험하는 방법](TESTING.ko.md)에서 실행 파일과 화면 조작 순서를 확인한다. 아래는 PC worker의 입력·출력·복구 규칙이다.

## PC 생성 도구

여정 JSON을 기존 로컬 Sohee 모델에 연결해 캐릭터 레시피·말투·실제 WAV를 만들고, Android MVP에 전달할 불변 번들을 내보낸다. 앱 안에서 모델을 실행하지 않는다. API·계정·새 모델·새 패키지를 사용하지 않으며, 이미 설치된 `.local/journey-voice-v3/venv`와 고정 모델 캐시가 필요하다.

## 준비된 여정

| 케이스 | 목적·모티브 | 캐릭터 | 몸체 | 생성 기록 |
| --- | --- | --- | --- | --- |
| 01 | 해안 휴식 | 파도방울 | droplet | 기존 3개 WAV 재사용 |
| 02 | 산·숲 캠핑 | 이끼토리 | sprout | 기존 3개 WAV 재사용 |
| 03 | 도시 전시 | 조각몽 | pillow | 기존 3개 WAV 재사용 |
| 04 | 같은 해안 경로의 다음 여정 | 파도몽 | pebble | 기존 3개 WAV 재사용 |
| 05 | 숲 근처 방문 | 숲토리 | acorn | 새 3개 WAV 실제 합성 |
| 06 | 호수 근처 용무 | 물빛콩 | bean | 새 3개 WAV 실제 합성 |
| 07 | 도시 출퇴근 | 반짝별 | lantern | 새 3개 WAV 실제 합성 |
| 08 | 목적지·목적 미지정 | 보송몽 | cloud | 새 3개 WAV 실제 합성 |

8개 몸체·8개 캐릭터·24개 WAV를 보존했다. 정밀 위치나 실제 도로 feed를 받은 사례가 아니라 의미 태그로 구성한 시험 입력이다. 창작 태그를 운전 위험·점수 근거로 사용하지 않으며, 도로 사실은 모두 UNKNOWN이다. Anna는 사용자 음색 선호 기준으로 유지하고, 이 시험은 로컬 한국어 Sohee 한 화자의 연기를 바꾼 결과다. 모든 캐릭터가 독립된 새 화자를 갖는다는 뜻은 아니다.

기존 원본 `prototypes/journey_voice_dynamic/demo`를 바꾸지 않고 `.local/journey-mvp/state`에 바이트 검증 복사했다. 4개 신규 입력만 GPU를 한 번 로드한 단일 프로세스에서 순서대로 실행해 12개를 합성했다. 복사한 기존 12개를 새 합성 결과로 계산하지 않았다.

## 다시 실행

저장소 루트에서 실행한다. 이미 준비된 8개는 모두 캐시에 적중하므로 모델을 로드하지 않는다.

```sh
.local/journey-voice-v3/venv/bin/python prototypes/journey_mvp/worker.py generate
```

출력은 `.local/journey-mvp/bundle/bundle.json`과 `voice/`다. Android Debug assets로 전달하는 작업은 PM의 앱 실행 도구가 담당한다. 이 worker는 Android 파일을 직접 수정하지 않는다.

처음에는 `bootstrap`으로 기존 결과만 복사하거나 `plan`으로 모델을 로드하지 않고 8개 캐릭터·말투를 확인할 수 있다.

```sh
.local/journey-voice-v3/venv/bin/python prototypes/journey_mvp/worker.py bootstrap
.local/journey-voice-v3/venv/bin/python prototypes/journey_mvp/worker.py plan
```

## 내 여정 추가

`cases/05-forest-visit.json` 같은 입력을 복사한다. 새 출발에는 **새 `journeyId`와 `requestId`**를 주고, 목적·거리·의미 태그를 바꾼다. GPS·정밀 주소는 입력하지 않는다. 지원 태그와 목적은 기존 [레시피 입력 가이드](../journey_characters/README.md#입력과-설계축)를 따른다. 목적을 모르면 `purpose`를 생략하거나 null로 둔다.

```sh
.local/journey-voice-v3/venv/bin/python prototypes/journey_mvp/worker.py generate \
  --input /절대경로/내-여정.json \
  --label '나의 새 여정' \
  --summary '숲 모티브 · 방문'
```

한 입력에서 레시피와 실제 인사·도착·공통 문장 3개를 생성하고 번들에 추가한다. `--input` 뒤에 여러 파일을 주면 하나의 모델 인스턴스로 순서대로 만든다. `--label`과 `--summary`는 입력 하나일 때만 쓴다. 기존 8개를 다시 요청할 필요는 없다. 새 입력의 첫 합성에는 시간이 걸리며, 결과 JSON은 완료 후 출력된다. 실패했다면 오류를 확인하고 같은 요청을 다시 실행한다. 완료된 캐릭터를 삭제해 재생성하는 방식으로 해결하지 않는다.

앱과 같은 입력 한도를 합성 전에 검사한다. 이름표 `--label`은 60, 설명 `--summary`는 240, case ID는 120 UTF-16 단위까지이며 공백만 입력할 수 없다. 예를 들어 `😀`는 두 단위다. 기존 캐릭터와 요청 배치를 합쳐 서로 다른 여정은 최대 32개다. 한 여정의 재시도·reroute는 추가 캐릭터로 세지 않는다. 32캐릭터의 기본 음원은 96개이므로 앱 음성 카탈로그의 100개 한도 안에 든다. 한도를 넘는 요청은 모델 로드와 새 정체성 저장 전에 거절한다.

새 여정 생성부터 APK 갱신·실행까지 한 번에 이어가려면 다음 명령을 사용한다. 아래 예제는 [내 여정 입력 예시](my-trip.example.json)를 복사한 파일에 새 ID와 원하는 의미 태그를 적은 뒤 전달한다.

```sh
python3.12 scripts/run_journey_mvp.py --input /절대경로/내-여정.json \
  --label '나의 새 여정' --summary '숲 모티브 · 방문'
```

자동 검사는 에뮬레이터의 별도 `journey-mvp-validation` 저장 공간을 사용한다. 사용자 시험의 `journey-mvp` 선택·보관함·음원·binding을 삭제하거나 검사로 채우지 않는다.

같은 여행의 reroute라면 `journeyId`를 유지하고 새 `requestId`를 준다. 목적지·경로·목적이 바뀌어도 처음 정한 외형·이름·목소리·원음은 보존한다. `cases/05-forest-visit-reroute.json`이 그 시험 입력이다. 여덟 몸체를 모두 쓴 뒤에는 몸체가 반복될 수 있다. 유한한 레시피 구조이며 무한한 새 모델을 생성하는 도구가 아니다.

## 번들 계약과 오류

`bundle.json`은 schemaVersion 1이며 각 캐릭터에 case ID·표시 이름·정확한 visual recipe·시각 hash·원본 recipe/plan hash·binding/profile/direction hash·세 clip ID를 기록한다. `visualSha256`는 정렬한 키·공백 없는 UTF-8 JSON의 SHA-256이다. 시각 필드는 구현 브리프에 정의된 항목만 사용하며 모티브와 경로 우선순위는 기존 registry 순서를 따른다.

`voice/manifest.json`은 기존 schemaVersion 2다. 기존 `export_android.py`의 바이트 보존 내보내기 함수를 worker의 전용 출력 잠금 안에서 사용했다. 기존 exporter가 쓰는 다른 디렉터리의 lock을 만들지 않도록 함수 호출 경계에서 잠금을 소유한다. 원본 WAV를 리샘플링하거나 후처리하지 않고 라이선스도 함께 보존한다.

기존 캐릭터와 음원을 바꾸거나 삭제하는 번들은 거절한다. 원본·완료된 WAV·내보낸 WAV·manifest의 누락·손상·바인딩 불일치도 자동 교체로 숨기지 않는다. `.local/journey-mvp/state`, `bootstrap-receipt.json`, `cases.json`, `bundle-receipt.json`을 함께 보존한다. 출력 경로를 옮기려면 검증된 workspace 전체를 복사한다. 다른 GPU 생성 작업과 동시에 실행하지 않는다.

최초 복사와 번들 게시에는 일시적인 `bootstrap-pending.json`·`bundle-pending.json` journal을 사용한다. 프로세스가 파일 게시 사이에 종료되면, 다음 worker 실행이 journal에 기록한 정확한 파일 해시·원본 정체성과 일치하는 단계만 이어서 완료한다. 완료 후 journal은 제거된다. journal 없이 사라진 완료 state·manifest·receipt, 또는 기록과 다른 파일은 복구로 가장해 교체하지 않고 오류로 거부한다. pending 파일을 임의로 삭제하거나 수정하지 않는다.

## 검증

```sh
python3 prototypes/journey_mvp/test_worker.py
python3 prototypes/journey_mvp/test_crash_recovery.py
python3 prototypes/journey_mvp/verify_bundle.py --expected-characters 8 --expected-bodies 8
python3 prototypes/journey_mvp/verify_runs.py
```

`test_worker.py`의 15개 검사는 실제 원본 복사, source/visual/voice join, immutable append, 시각 manifest와 WAV 변조 거부, 새 완료 음원 손상 시 재합성 금지, 8몸체의 CPU 선택과 앱의 텍스트·캐릭터 개수 한도를 확인한다. 실제 CLI 자식 프로세스 7개로 한도 초과 입력이 엔진 구성과 상태 변경 전에 거절되는지 검사했다. 결과는 `input-boundary-verification.json`이다. 새 음성 생성 부분은 테스트 대역이며 음질 증거가 아니다.

추가 9개 중단 복구 검사는 실제 자식 프로세스 30개를 실행한다. bootstrap의 journal·state rename·receipt 게시와 최초/추가 bundle의 journal·manifest·receipt 게시 직후 `os._exit(86)`으로 종료한 뒤 재실행한다. 정확한 단계는 복구하고, 완료 파일의 누락과 pending 상태의 변조는 거부한다. `crash-recovery-verification.json`에 종료 코드와 결과를 보존했다. GPU나 새 합성은 실행하지 않는다. 전원 차단 시험을 수행한 결과는 아니다.

별도 실제 합성 결과는 `generation-result.json`과 `generation.log`다. 새로운 네 캐릭터는 캐시 적중 0개, 실제 모델 로드 true였다. `restart-result.json`은 독립 프로세스에서 8개 캐릭터 24클립을 모두 재사용하고 모델 로드 false였다. `reroute-result.json`은 변경된 입력에서도 같은 캐릭터의 3클립을 재사용했다. `restart-verification.json`과 `bundle-verification.json`이 원본 바이트·텍스트·방향·캐릭터 정합성을 검사한다.

중단 복구 수정 후에도 기존 여덟 여정을 다시 실행했다. 모델 로드 없이 24클립이 캐시에 적중했고, state의 76파일·번들의 28파일·bundle receipt의 실제 바이트와 초기 bundle ID가 그대로였다. `recovery-preservation-verification.json`과 `post-recovery-generate-result.json`이 이 결과이며 이전 실행 증거는 덮어쓰지 않았다.

사람이 새 12개 문장의 한국어 명료도·귀여움·소장 의향을 평가하지 않았다. Android 렌더링·실제 재생·이동 정책·앱 재시작은 앱 담당의 별도 검증 결과를 따른다. 운전습관 개선 효과와 실차 검증은 이 결과에 포함하지 않는다.
