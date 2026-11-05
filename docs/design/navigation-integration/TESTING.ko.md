# 사진 없이 내비 목적지와 경로 API로 눈티 시험하기

현재 준비된 Mac과 Pleos 에뮬레이터에서 실행한다. 이번 시험의 목표는 **목적지와 실제 도로 경로를 입력해 새 눈티를 생성하고, 같은 눈티를 다시 여는 것**이다. 사진 업로드나 사진 추출은 사용하지 않는다.

현대 내비의 목적지·현재 위치·경로 상태는 공식 `NaviHelper 3.0.5`에서 가져온다. 생성에 쓰는 전체 도로 형상은 별도 `OSRM / FOSSGIS` 경로 API가 계산한다. 공개 SDK에서 전체 도로 polyline을 반환하는 API는 확인되지 않았다. `TripSummary.routePoints`는 경유지·목적지 요약이며 전체 도로 선이 아니다. **OSRM 선이 현대 내비의 선택 경로와 같다는 검증은 완료하지 않았다.** [연결 계약](IMPLEMENTATION-CONTRACT.md)에 출처와 데이터 보존 규칙을 정리했다.

2026-11-04 실행에서는 실제 Android 화면의 빠른 일러스트 생성·보관·복원 23개 검사와 UI 상태 회귀 8개를 통과했다. 세 여정의 실제 OSRM 응답을 저장했고 이후 시험은 캐시를 재사용했다. API 경로로 로컬 AI 새 그림을 생성하는 추가 시험도 44.2초에 완료했고, 같은 이미지·음성 설정을 Android에서 다시 여는 검증도 통과했다. 현재 앱에는 이 AI 결과가 열려 있다. GPS 세 점 주입·읽기·복원과 눈티 보존은 확인했지만, SDK의 중간·도착 위치 수신과 재탐색 완료는 미검증이다. 내비를 앞에 둔 16초 분리 시험에서도 SDK 위치 갱신을 확인하지 못했다. 확정 결과와 근거는 [검증 결과](RESULT.ko.md)를 확인한다.

[기존 추천 순서](../../research/2026-11-04-navigation-review/README.md)는 1번 SDK 읽기, 2번 전체 형상 확인, 3번 snapshot 반복 시험, 4번 선택 GPS 재생이었다. 요청한 1~3번 흐름은 사진 없이 API 방식으로 구현·시험했다. 2번의 도로 형상은 현대 원본을 받는 대신 출처를 밝힌 OSRM 형상을 사용한다. 추가로 실행한 4번의 SDK 위치 수신·재탐색 한계는 별도로 남아 있다.

## 앱을 실행하기

저장소 루트에서 실행한다.

```sh
cd /Users/pig30nidae/NUNTI
python3 scripts/run_avatar_generator.py --local-ai --navigation-api --restart-server
```

실행기는 로컬 생성 서버를 시작하고 Android 앱을 연다. `--local-ai`는 준비된 로컬 이미지 모델을 연결한다. `--navigation-api`는 외부 공개 경로 서버 조회를 허용한다. 이 명령은 유료 이미지 API를 승인하지 않는다.

앱이 표시되지 않으면 [Pleos 차량 콘솔](http://127.0.0.1:8088/)을 열고 기어 P·속도 0·차량 화면 사용 허가를 확인한다. GPS 재생 시험에서도 이 조건을 유지한다. 새 APK를 빌드해야 한다는 안내가 나오면 같은 명령에 `--build`를 추가한다.

브라우저에서 별도 경로 API만 시험하려면 다음 명령을 사용한다. 브라우저에는 Android의 `NaviHelper` 연결이 없으므로 현대 내비 목적지·상태 수신 시험은 Android 앱에서 한다.

```sh
python3 scripts/run_avatar_generator.py --browser --local-ai --navigation-api --restart-server
```

최초 연결 코드가 필요한 경우 `python3 scripts/run_avatar_generator.py --show-code`로 확인한다. 연결 코드는 로컬 서버 로그인용이며 외부 API 키가 아니다.

### 에뮬레이터 재시작 후 내비가 응답하지 않을 때

에뮬레이터를 재시작하면 현대 내비에 **경로안내 재시작** 또는 **기존 경로안내를 계속할까요** 대화상자가 남을 수 있다. 이때 SDK의 `CONNECTED`만 확인해 연결 시험을 통과시키지 않는다. 실제 목적지·현재 위치 콜백과 유효 위경도도 확인한다.

1. Pleos 홈의 내비 아이콘으로 현대 내비 앱을 연다.
2. **계속안내** 또는 **안내종료**를 선택해 초기 화면을 마친다.
3. 눈티로 돌아와 목적지를 다시 설정하고 **내비 목적지 불러오기**를 누른다.
4. 목적지와 현재 위치가 수신되는지 확인한다. 연결됨으로 표시돼도 콜백이 0개라면 수신 성공이 아니다.

이 절차 뒤 실제 콜백 32개와 `ROUTE_GUIDING`, 유효한 현재 위치·목적지·routeId를 확인한 기록은 [native-gps-ready.json](../../../.local/navigation-integration/native-gps-ready.json)에 있다.

## 내비 목적지로 눈티를 생성하기

1. Android 앱의 **내비에서 여정 가져오기**에서 연결 상태를 확인한다.
2. **현대 내비 열기**에서 목적지를 지정한다. 눈티 앱으로 돌아와 **내비 목적지 불러오기**를 누른다. 목적지·현재 위치·내비 경로 상태가 들어오는지 확인한다.
3. 목적지가 없으면 **경로 API 시험 입력**을 펼친다. **공개 장소 시험 여정**을 선택하거나 출발지·목적지 위경도를 입력한다. 시험 여정은 경로 입력 편의 기능이며 미리 생성된 캐릭터 목록이 아니다.
4. 현대 내비에도 같은 목적지를 전달하려면 **이 목적지를 현대 내비에 설정**을 누른다. **현대 경로 전체 보기**로 내비 화면을 확인할 수 있다. 이 동작만으로 현대의 전체 선이 생성기에 전달되는 것은 아니다.
5. **경로 API로 길 불러오기**를 누른다. 출발지·목적지와 도로 선, 거리·예상 시간, OSRM 출처 표시를 확인한다. 이 조회는 입력한 위경도를 외부 공개 서버로 보낸다.
6. 선이 사용할 경로와 맞으면 **표시된 선이 이번에 갈 경로가 맞아요**를 체크한다. 체크 전에는 생성할 수 없다. 목적지를 바꾸면 경로를 다시 불러와 확인한다.
7. **그곳의 느낌**과 **이번에 가는 이유**를 입력한다. **이미지 생성 방식 → 로컬 AI · 약 1분**을 선택한 뒤 **이 길에서 눈티 만나기**를 누른다. 우선 연결만 확인하려면 **빠른 일러스트 · API 없이**를 사용한다.
8. 탄생 효과·새 그림·**눈티가 품은 원래 경로**를 확인한다. 로컬 AI의 경로·목적지 반영 정도와 귀여움은 직접 평가한다. 모티브 설명만으로 그림의 의미 일치가 검증된 것은 아니다.
9. **내 눈티**에서 결과를 다시 연다. 앱을 닫고 다시 열어도 같은 외형과 음성 설정이 유지되는지 확인한다. **새 여정 만들기**는 새 캐릭터를 생성하는 별도 동작이다.

목적지 이름만 입력해 좌표를 찾는 지오코딩 기능은 없다. 현대 내비에서 장소를 검색한 뒤 가져오거나, 경로 API 시험 입력의 위경도를 직접 지정한다.

현재 v6의 목소리 듣기는 버튼을 처음 누를 때 Mac의 로컬 Qwen3-TTS로 캐릭터별 새 한국어 음원을 만든다. 이후에는 저장된 같은 음원을 재생한다. [v6 시험 안내](../avatar-v6/TESTING.ko.md)를 따른다. Anna 음색 재현을 검증한 것은 아니다. 내비 재탐색이나 GPS 변경이 기존 눈티를 자동으로 다시 생성하지 않는다.

## 저장된 경로를 다시 확인하기

**저장 경로 다시 보기**는 저장된 `planId`의 원본을 읽는다. 새 외부 도로 계산과 구분한다. 같은 원본 위경도 배열의 `rawSha256`과 정규화 좌표의 `normalizedSha256`을 유지해야 한다.

생성한 API 경로의 계획 JSON을 GPS 시험에 쓰려면 다음 명령을 실행한다. 가장 최근에 보관된 `API_ROUTE` 눈티의 계획을 읽는다. 로컬 연결 코드와 외부 API 키는 출력하지 않는다. 외부 경로 API를 새로 호출하지 않는다.

```sh
python3 - <<'PY'
import json
import os
import urllib.request
from pathlib import Path

root = Path('/Users/pig30nidae/NUNTI')
connection = json.loads((root / '.local/avatar-generator/connection.json').read_text())

def get(path):
	request = urllib.request.Request(
		connection['baseUrl'] + path,
		headers={'Authorization': 'Bearer ' + connection['token']},
	)
	with urllib.request.urlopen(request, timeout=10) as response:
		return json.load(response)['data']

saved = next(
	(item for item in get('/v3/avatars') if item['route']['inputOrigin'] == 'API_ROUTE'),
	None,
)
if saved is None:
	raise SystemExit('먼저 API 경로로 눈티를 생성하고 보관하세요.')
plan_id = saved['route']['apiPlanId']
plan = get('/v3/route-plans/' + plan_id)
output = root / '.local/navigation-integration' / ('plan-' + plan_id + '.json')
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
os.chmod(output, 0o600)
print(output)
PY
```

출력된 절대 경로를 다음 명령의 `/절대경로/plan-….json` 자리에 넣는다. `.local/avatar-generator/connection.json`, SQLite, `media`를 유지해야 같은 소유자로 저장된 경로와 눈티를 다시 열 수 있다.

## GPX를 만들고 GPS 수신을 확인하기

먼저 기기를 바꾸지 않는 검증을 실행한다.

```sh
python3 scripts/verify_navigation_integration.py --plan /절대경로/plan-….json
```

성공하면 `PASS_ROUTE_REPLAY_ARTIFACTS_ONLY`와 보고서 경로가 나온다. `.local/navigation-integration/replay/` 아래에 원본 계획, `route.gpx`, 방향 반전 진단용 GPX, 왕복 진단용 GPX가 생긴다. 원본 SHA와 정규화 좌표의 출처·방향을 확인한다. 진단용 반전·왕복 파일은 도로 API가 새로 계산한 통행 가능 경로가 아니다. 이 단계는 GPS를 변경하지 않는다.

저장된 실제 현대 목적지 사례로 원 HTTP 응답까지 대조하려면 다음 명령을 사용한다. `--provider-response`는 응답 바이트 SHA와 그 안의 좌표를 계획의 원본과 비교한다.

```sh
python3 scripts/verify_navigation_integration.py \
	--plan .local/navigation-integration/live/native-plan.json \
	--provider-response .local/navigation-integration/live/native-provider-response.json
```

실제 GPS 수신 시험 전에는 Android 앱을 앞에 열어 두고 생성된 눈티를 표시한다. 현재 준비된 Python 환경에는 `grpcio`와 `grpcio-tools`가 설치돼 있다. 에뮬레이터 serial이 다르면 `--serial`을 바꾼다.

```sh
.local/voice-runtime/venv/bin/python scripts/verify_navigation_integration.py \
	--plan /절대경로/plan-….json \
	--serial emulator-5554 --run-replay --samples 3 --interval 1.2
```

GPS 재생 중 공식 SDK 재탐색 완료와 눈티 보존도 확인하려면 위 명령에 `--run-reroute`를 추가한다. 이 옵션은 `--run-replay`와 함께 사용하며 현대 내비가 경로 안내 중이어야 한다. 재탐색 명령의 접수와 SDK 완료 콜백을 구분한다.

도구는 인증된 공식 `EmulatorController.getGps/setGps`로 출발·중간·도착 좌표를 주입하고 SDK의 현재 위치 콜백과 비교한다. `--samples`는 2~12, `--interval`은 1~5초이며 기본값은 각각 3과 1.2다. 차량 기어나 속도 상태를 조작하지 않는다. 시험 종료 시 기존 GPS 상태를 복원하고 다시 읽어 확인한다.

보고서에서 `gpsReadbackVerified`, `sdkLocationConsumptionVerified`, `gpsStateRestored`를 확인한다. 모두 확인된 경우의 상태는 `PASS_GPS_REPLAY_AND_SDK_OBSERVATION`이다. `GPS_REPLAY_SDK_CONSUMPTION_UNVERIFIED`는 에뮬레이터에 GPS를 넣었어도 SDK가 같은 위치를 소비하는지 확인하지 못한 결과다. 단순 GPX 생성 성공과 구분한다.

`artifactIdentityPreservedAcrossReplay`는 시험 전후의 캐릭터 ID·이미지 SHA·음성 설정이 같은지 확인한다. 시험 전에 결과 화면을 열지 않았다면 이 항목으로 캐릭터 보존을 입증할 수 없다. 세 점 GPS 시험은 실제 차량 주행이나 내비 전체 경로의 일치 검증이 아니다. 이 도구는 영상·음성을 녹화하지 않는다.

`--run-reroute`를 썼다면 `rerouteSdkCompletionVerified`와 `rerouteArtifactIdentityPreserved`도 확인한다. `GPS_REPLAY_PASSED_REROUTE_COMPLETION_UNVERIFIED`는 GPS 시험과 별개로 재탐색 완료를 확인하지 못했다는 뜻이다.

## API 키와 공개 서버 사용 범위를 확인하기

이번 경로 API, NaviHelper 연결, 로컬 이미지 생성과 v6의 로컬 TTS에는 외부 API 키가 필요 없다. 유료 이미지·음성 API는 사용하지 않는다.

[FOSSGIS 공개 경로 서버 사용 조건](https://routing.openstreetmap.de/about.html)은 초당 최대 1회 요청, 식별 가능한 User-Agent, OpenStreetMap 출처와 지도 수정 링크를 요구한다. 구현은 신규 요청 간격을 1.1초 이상으로 제한하고 동일 출발·도착 좌표를 캐시한다. 현재 개발용 작업공간의 외부 요청은 누적 12회로 제한한다. 요청 실패도 횟수에 포함한다. 저장 계획 재생은 이 한도를 사용하지 않는다.

공개 서버는 소량 개발 시험용이다. 제품 배포·대량 생성에는 같은 주소를 그대로 사용하지 말고 자체 OSRM 서버 또는 사용량·가용성·데이터 조건이 맞는 정식 공급자를 정한다. 이 전환과 현대 내비 원경로 획득은 완료한 상태가 아니다. [OSRM 공식 HTTP 문서](https://project-osrm.org/docs/v26.6.1/http.html)의 `overview=full`, `geometries=geojson`을 사용하며 원본은 WGS84 `[경도, 위도]` 순서로 보관한다.

`ROUTE_API_RATE_LIMIT`이면 1.1초 이상 기다린 뒤 필요한 요청만 실행한다. `ROUTE_API_DEMO_LIMIT_REACHED`이면 기존 저장 경로를 다시 보며, 한도 우회를 위해 저장소를 초기화하지 않는다. `ROUTE_PROVIDER_UNAVAILABLE`이면 네트워크와 공개 서버 상태를 확인한다. 조회 실패를 사진 추출이나 임의 선의 성공으로 대체하지 않는다.

## 검증 결과를 기록하기

이 문서는 실행 절차다. 실제 SDK 연결·외부 도로 조회·화면 생성·GPS 수신 성공은 실행 보고서로 판단한다. 최근 실행의 날짜·APK SHA·원본 계획·보고서 경로와 미검증 항목을 함께 기록한다. 상용 차량 동작, 현대 경로와 OSRM 선의 일치, 운전습관 개선 효과는 별도 검증 대상이다.
