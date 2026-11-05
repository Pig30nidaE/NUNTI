# 눈티 생성기를 직접 시험하기

현재 목적지·방문 이유별 일러스트, 탄생 효과, 캐릭터별 로컬 TTS는 **[v6 직접 시험 안내](../avatar-v6/TESTING.ko.md)**를 따른다. 실행은 `python3 scripts/run_avatar_generator.py --local-ai --navigation-api --restart-server`다. 아래는 v3~v5의 당시 절차이며 사진 입력과 기존 기기 TTS 설명을 현재 기능의 제한으로 해석하지 않는다.

저장소 위치는 `/Users/pig30nidae/NUNTI`다. API 계정 없이 사용할 수 있는 로컬 생성기와 Android APK를 준비했다. PC가 켜져 있어야 하며, 앱은 PC의 로컬 생성 서버에 연결한다.

최신 외형과 탄생 효과는 [v5](../avatar-quality-v5/README.md)를 따른다. 아래의 기본 명령은 빠른 코드 렌더를 사용한다. 무료 로컬 이미지 모델을 연결하려면 현재 준비된 Mac에서 다음 명령을 실행한다.

```sh
cd /Users/pig30nidae/NUNTI
python3 scripts/run_avatar_generator.py --local-ai --restart-server
```

화면의 **생성 방식 → 로컬 AI · 약 1분**을 선택한다. 목적지·특징·목적을 입력하고 경로를 확인한 뒤 생성한다. 이 모드는 매 요청마다 실제 로컬 모델을 실행한다. 고정 원화 목록에서 고르는 방식이 아니다. 같은 요청의 재시도와 보관 복원에는 저장된 이미지를 사용한다. 모델은 공개 MLX Community FLUX.2-Klein-4B 4bit이며 API 키·유료 외부 호출이 필요 없다. 현재 Mac 한 대에서 실행하는 실험 모드다. 다른 PC의 설치 복원은 [모델·도구·경로](../avatar-quality-v4/local-model-result.md)를 확인한다.

AI 이미지는 RGB로 생성한 후 외곽 배경을 제거해 RGBA로 저장한다. 실제 alpha 외곽으로 탄생 모션을 만들지만 경로를 정확하게 닮은 정도와 귀여움은 자동 통과로 판정하지 않는다. 얼굴이나 배경 처리에 문제가 있으면 새 여정으로 비교하고 실패 결과도 보고한다. 모티브 설명은 AI에 전달한 의도이며 실제 그림에서 검증됐다는 표시가 아니다. 빠른 모드로 되돌리려면 **빠른 생성**을 선택한다. 유료 API 모드는 승인 전까지 꺼져 있다.

## Android에서 시작

```sh
cd /Users/pig30nidae/NUNTI
python3 scripts/run_avatar_generator.py
```

도구가 로컬 서버를 시작하고 준비된 Pleos 에뮬레이터에 앱을 설치·실행한다. 기어 P·속도 0·차량 화면 사용 허가가 확인돼야 표시된다. 앱이 숨겨지면 [Pleos 차량 콘솔](http://127.0.0.1:8088/)을 열어 유지하고 P와 정차 상태를 확인한다. 새 APK 경로는 `.local/avatar-generator/Nunti-Avatar-Generator-debug.apk`다.

1. 아래의 시험 경로 하나를 고른다. 이것은 입력 예시이며 캐릭터 목록이 아니다.
2. 목적지·그곳의 느낌·방문 목적을 바꿔 본다.
3. 원본에 표시된 선을 확인하고 체크한다.
4. **이 길에서 눈티 만나기**를 누른다. 경로가 몸 밖의 빛과 별가루를 이끈 뒤 사라지고, 실루엣이 자라 눈티가 완성된다.
5. 입력이 외형에 어떻게 반영됐는지와 원래 경로를 살펴본다.
6. **새 여정 만들기**로 같은 길을 다시 생성해도 다른 눈티가 태어난다. 기존 눈티는 **내 눈티**에 남는다.
7. 앱을 닫았다 다시 열고 **내 눈티**에서 같은 외형·음성 설정이 복원되는지 확인한다.

목소리 버튼은 기기의 기존 한국어 화자를 사용한다. 한국어 TTS가 없는 기기는 안내를 표시한다. 이미지 생성·보관은 계속 사용할 수 있다. 새 음색 생성이나 Anna 음색 재현을 완료한 상태는 아니다.

## 내 경로 사진 넣기

**경로 사진 불러오기**에서 내비 화면의 PNG/JPG를 선택한다. 한 개의 목적지행 경로가 분명히 보이는 사진을 사용한다. 선을 못 찾으면 경로선 색상을 지정하거나 한 경로만 보이도록 자른 사진을 넣는다. 복수 경로·분기·경로를 찾을 수 없는 사진은 거절하거나 경고한다. 원본과 추출선이 맞는지 확인한 뒤 생성한다.

에뮬레이터로 시험 사진을 보내려면 다음 명령을 쓸 수 있다. Android 현재 사용자가 10인 준비된 AVD 기준이다.

```sh
.local/pm-tools/sdk/platform-tools/adb shell mkdir -p /storage/emulated/10/Download
.local/pm-tools/sdk/platform-tools/adb push prototypes/avatar_generator/examples/synthetic-coast.png /storage/emulated/10/Download/nunti-route.png
```

앱에서 사진을 고를 때 다운로드 폴더의 `nunti-route.png`를 선택한다. 이 파일은 프로젝트가 만든 합성 내비 시험 이미지다. 실제 지도·내비 SDK 연동 자료가 아니다. 직접 찍은 경로 사진도 같은 방식으로 전달할 수 있다.

좌표를 쓰려면 **좌표 파일**에서 [입력 예시](../../../prototypes/avatar_generator/examples/route-file.example.json)를 선택한다. 경로는 이미지 전체 기준의 0~1 좌표이며 2~512점이다. GPS 좌표는 그대로 넣지 않는다.

## 브라우저에서 시험

```sh
python3 scripts/run_avatar_generator.py --browser
```

브라우저가 `http://127.0.0.1:8768`을 연다. 최초 연결 코드는 다음 명령으로 확인한 뒤 열린 화면에 입력한다. 코드에는 외부 API 키가 들어 있지 않다.

```sh
python3 scripts/run_avatar_generator.py --show-code
```

브라우저에서는 컴퓨터에 저장된 경로 사진과 좌표 JSON을 바로 선택할 수 있다. 음성은 브라우저가 사용할 수 있는 한국어 화자가 있을 때 재생한다. 저장 상태는 같은 서버·연결 코드의 Android 앱과 공유한다.

## AI 이미지 모드 연결

로컬 생성에는 키가 필요 없다. 선택 기능인 AI 이미지를 사용하려면 현재 어댑터에 맞는 `OPENAI_API_KEY` 하나가 필요하다. 키는 서버 환경변수에만 설정하고 채팅·APK에 넣지 않는다. 모델 접근 권한과 가격을 계정에서 먼저 확인한다. 코드의 모델 기본값은 기존 계획의 `gpt-image-2.5-flare`이며 실제 계정 접근을 검증한 모델명이 아니다.

[서버 설정표](server-result.md)의 `NUNTI_STUDIO_IMAGE_API_ENABLED`, `NUNTI_STUDIO_IMAGE_MODEL`, 가격 검토 표시와 양의 요청 예약액을 모두 설정한 뒤 `python3 scripts/run_avatar_generator.py --restart-server`로 실행한다. 화면에 생성 방식 선택이 열리면 명시적으로 AI 이미지를 선택한다. API 모드는 유료 요청을 자동 재시도하지 않으며, 실패를 로컬 성공으로 대체하지 않는다. 새 음색 API는 v3에 연결하지 않았고 기존 v2 안내와 구분한다.

## 다시 빌드하거나 종료

```sh
python3 scripts/run_avatar_generator.py --build
python3 scripts/run_avatar_generator.py --stop
```

빌드는 준비된 로컬 JDK·Android SDK·Gradle 캐시를 쓴다. 생성 서버의 Python 환경은 `backend/uv.lock`에 따른 Python 3.12 이상과 Pillow를 사용한다. 새 환경에서는 `backend`에서 `uv sync --locked`로 복원한다. 이 작업에는 패키지 다운로드가 필요할 수 있다.

`--stop`은 이 도구가 시작한 서버만 종료한다. `.local/avatar-generator/connection.json`, SQLite와 `media` 폴더를 유지해야 기존 눈티를 같은 소유자로 다시 열 수 있다. 연결 코드와 소장품을 삭제하는 초기화는 자동으로 하지 않는다.

현재 release APK는 로컬 시험용 host가 들어간 **서명 전 파일**이다. 공모전 제출이나 원격 배포가 완료된 APK로 사용하지 않는다. 영상·스피커 녹음은 실행 도구에 포함하지 않았다.
