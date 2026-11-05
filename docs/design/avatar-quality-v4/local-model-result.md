# 무료 로컬 이미지 모델 실험 결과

2026-11-03. Apple M4 16GB에서 FLUX.2-klein-4B의 4비트 MLX 변환 모델로 초기 참조 이미지 편집 3회, 앱용 어댑터를 통한 정원 1회, 실제 Android 앱의 HTTP 요청 1회에 성공했다. 총 로컬 추론은 5회다. 유료 API 호출, 로그인, 키 사용은 0회다. 새 AI 원화를 로컬에서 생성할 수 있다는 실행 증거이며, 제품 품질과 경로 보존이 검증됐다는 뜻은 아니다.

현재 사용자 선호는 불투명 파스텔 색면과 얕은 매트 2.5D 일러스트다. 초기의 반투명 재질 요구보다 최신 피드백을 우선했다. 이 실험은 목적지·경로 기반 생성 기능만 다룬다. 운전습관 개선 효과와 음성 품질은 평가하지 않았다.

## 실행한 환경과 모델

| 항목 | 확인 결과 |
| --- | --- |
| 하드웨어 | Apple M4, 통합 메모리 16GiB |
| 운영체제 | macOS 26.4 |
| 실행 도구 | 공식 PyPI `mflux==0.24.0`, MLX Metal |
| 원본 모델 | `black-forest-labs/FLUX.2-klein-4B` |
| 실제 사용 가중치 | MLX Community 변환 `mlx-community/FLUX.2-Klein-4B-4bit` |
| 고정 revision | `1cebb9b45c21ece14a42615b16bf5fa4de9b56da` |
| 접근 조건 | 공개, gated 아님, 로그인 없이 다운로드 완료 |
| 모델 파일 합계 | 4,619,702,270 bytes, 약 4.62GB |
| 다운로드 시간 | 86.76초 |
| 출력 조건 | 512×512, 4 steps, `--low-ram`, 참조 이미지 2장 |
| 독립 환경 | `.local/avatar-quality-v4/local-image/venv` |

도구의 코드는 MIT이며 원본 가중치는 Apache-2.0이다. 실제 받은 MLX Community 변환 모델에도 Apache-2.0 표기가 있다. **BFL가 직접 배포한 양자화 파일이라고 표시하지 않는다.** 원본 전체 저장소는 이번 용량 범위를 넘기므로 받지 않았다. 모델 외 설치 패키지의 개별 라이선스는 배포 전에 별도로 점검해야 한다.

[MFLUX 공식 저장소](https://github.com/mflux-community/mflux), [FLUX.2 실행 문서](https://github.com/mflux-community/mflux/blob/main/src/mflux/models/flux2/README.md), [로컬 모델 로딩 문서](https://github.com/mflux-community/mflux/blob/main/src/mflux/models/common/README.md), [PyPI 배포 이력](https://pypi.org/project/mflux/), [BFL 원본 모델 카드](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B), [BFL 가중치 라이선스](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B/blob/main/LICENSE.md), [실제 사용한 MLX 변환 모델](https://huggingface.co/mlx-community/FLUX.2-Klein-4B-4bit/tree/1cebb9b45c21ece14a42615b16bf5fa4de9b56da).

설치된 패키지는 56개다. 압축된 주요 패키지 다운로드는 약 320MiB였고 모델과 합해 전송량은 6GB 이하였다. 설치 후 모델·가상환경·캐시의 디스크 점유는 약 6.63GiB였다. 전송량과 설치 후 점유는 다른 수치다. 시작 시 여유 디스크는 약 274GiB였다. 기존 음성 및 서버 가상환경은 변경하지 않았다.

샌드박스 안에서는 Metal 장치에 접근하지 못했다. 승인된 로컬 실행 권한으로 MLX를 구동했다. 이는 PyTorch MPS 추론 실험이 아니다. 생성 프로세스는 외부 모델 조회를 막은 오프라인 환경으로 실행했다. HF 캐시는 독립 디렉터리에 두고 암묵적 토큰 사용을 껐다.

## 실제 이미지 3장과 실패

생성 시간은 CLI 하위 프로세스 시작부터 출력 검사가 끝날 때까지다. 각 실행의 로그에 `Peak MLX memory: 3.49 GB`가 기록됐다. 이 수치는 MLX가 보고한 피크이며 시스템 전체 메모리 측정이 아니다.

| 실험 | 참조와 seed | 시간 | 직접 확인한 결과 |
| --- | --- | --- | --- |
| 최초 해변 | A2 스타일 + 하단 경로 inset이 있는 구조 지도, 4242 | 48.63초 | 매트 파스텔과 친근한 얼굴은 나왔지만 하단 inset을 별도 그림으로 복사했다. 실패 사례로 보존한다. |
| 해변 no-inset | A2 스타일 + 큰 회색 실루엣과 흐름선 하나만 있는 지도, 4243 | 42.52초 | 별도 inset이 사라졌다. 한 캐릭터의 파도형 몸체와 말린 꼬리가 나왔다. 매끈한 음영이 남아 있어 완전히 평면적인 색면은 아니다. |
| 정원 no-inset | C2 스타일 + 다른 경로의 실루엣과 흐름선 하나, 7373 | 42.25초 | 큰 잎과 씨앗 몸체가 해변과 다른 실루엣을 만들었다. 그러나 잎이 얼굴을 가려 눈이 하나만 보인다. 최종 원화로 채택하지 않는다. |

추가 두 실험 합계는 84.77초다. 동일 이미지의 무한 재시도가 아니라 목적지·경로·시드·스타일을 바꾼 별도 사례였다. 두 결과가 달랐다는 사실만으로 경로와 목적지 각각의 인과를 증명하지 않는다. 시드와 스타일도 함께 바뀌었으므로 인과 검증에는 입력 하나만 바꾸는 후속 비교가 필요하다.

원본은 모두 RGB다. 배경을 잘라내거나 알파를 꾸며 오류를 숨기지 않았다. 투명 배경이 필요한 앱 원화로 바로 사용할 수 있는 상태는 아니다. 정확한 경로 굽이 대응, 얼굴 가독성, 목적지 모티브 반영률도 아직 통과 판정하지 않았다.

파일은 다음 위치에 보관했다.

- 최초 원본: `.local/avatar-quality-v4/local-image/nunti-local-edit.png`
- 해변 원본: `.local/avatar-quality-v4/local-image/nunti-local-coast-no-inset-edit.png`
- 정원 원본: `.local/avatar-quality-v4/local-image/nunti-local-garden-no-inset-edit.png`
- 각 입력·프롬프트·구조 지도·참조·결과 메타데이터·로그: 같은 디렉터리의 `coast-no-inset-*`, `garden-no-inset-*`
- 모델 파일 명세: 같은 디렉터리의 `model-manifest.json`
- 설치 버전 목록: 같은 디렉터리의 `packages.txt`

| 원본 | PNG SHA-256 |
| --- | --- |
| 최초 해변 | `57cf39c85956cca5f7a30e95e98c5dcc750a2f5264db0943c6359474beaf2b37` |
| 해변 no-inset | `a098a86617ccf395eb5518b0458e7d835ba867bbdfcb1102bec5ebf38c8c218b` |
| 정원 no-inset | `7d828a6c0b30e052dcde785840ea3b82ba88d386b0656d2e32cfce0d24737b17` |

## 재현 방법과 보존 경계

[probe 스크립트](../../../scripts/probe_local_avatar_image.py)는 로컬 모델 경로만 사용한다. 설치, 모델 다운로드, API 호출, 로그인 경로가 없다. 가중치 파일 크기를 명세와 비교하고 최대 실행 시간을 제한한다. 기존 출력이 있으면 덮어쓰지 않고 `OUTPUT_EXISTS_CHOOSE_A_NEW_EXPERIMENT`로 중단한다.

이번에 완료한 명령은 다음과 같다. 저장된 결과가 있으므로 현재 그대로 다시 실행하면 보존 검사에서 중단되는 것이 정상이다.

```sh
.local/avatar-quality-v4/local-image/venv/bin/python scripts/probe_local_avatar_image.py --case coast --mode edit --timeout 150
.local/avatar-quality-v4/local-image/venv/bin/python scripts/probe_local_avatar_image.py --case garden --mode edit --timeout 150
```

프롬프트는 스타일 참조와 구조 참조의 역할을 나눴다. 실제 저장된 해변 프롬프트는 204단어, 정원은 201단어다. 해변의 저장 프롬프트는 스크립트의 마지막 문장 축약 전 버전이므로 정확한 실험 복원에는 `coast-no-inset-prompt.txt`를 사용한다. 원본 첫 실험도 당시의 `prompt.txt`와 메타데이터를 그대로 보존했다. 고정 시드만으로 다른 라이브러리 버전과 하드웨어의 PNG 해시 동일성을 보장하지 않는다.

추가 스크립트 검사는 Ruff check와 format check가 통과했다. 초기 3장 실험 단계에서는 앱과 서버의 테스트를 다시 실행하거나 런타임 통합 코드를 변경하지 않았다. 이후 연결과 검증은 다음 절에 구분한다.

## 앱 선택 모드 연결과 추가 정원 검증

`backend/nunti/avatar_studio/local_model.py`를 추가하고 `renderMode=LOCAL_MODEL`을 API에 연결했다. 기본값은 비활성이다. 기존 `LOCAL_RENDER`와 유료 `IMAGE_API`의 승인·예산 경계는 유지한다. 러너는 다음 환경변수로 설치된 모델을 연결한다.

```text
NUNTI_STUDIO_LOCAL_MODEL_ENABLED=true
NUNTI_STUDIO_LOCAL_MODEL_BINARY=<workspace>/.local/avatar-quality-v4/local-image/venv/bin/mflux-generate-flux2-edit
NUNTI_STUDIO_LOCAL_MODEL_WEIGHTS=<workspace>/.local/avatar-quality-v4/local-image/model
NUNTI_STUDIO_LOCAL_MODEL_TIMEOUT_SECONDS=150
```

바이너리와 가중치는 저장소 내부 경로만 받는다. 공개 모델의 고정 revision 및 파일 명세를 확인하고, 모델이 없으면 다운로드하거나 외부 API로 바꾸지 않는다. `capabilities.localImageModelAvailable`과 `localImageModelInfo`로 사용 가능 여부와 측정 조건을 알린다.

같은 가중치 디렉터리의 file lock으로 동시 추론을 한 건으로 제한한다. 자식도 lock FD를 이어받아 서버 재시작과 기존 추론이 겹치는 것을 막는다. `shell=False`로 실행하고, HOME·HF 캐시·TMPDIR를 실행 폴더 안에 격리한다. API 키·HF 토큰·기존 로그인 환경을 복사하지 않는다. 제한 시간을 넘기면 자식 process group을 종료한다.

입력은 A2 스타일과 inset 없는 구조 지도다. 구조 지도에는 제안된 얼굴 위치가 실제 제안 body mask 안에 들어가는지 확인한 뒤 크림 얼굴판과 양눈을 그린다. 프롬프트는 앞면 얼굴과 가리지 않은 두 눈을 요청한다. 이것은 입력 앵커이며 결과 얼굴을 자동 검증했다는 표시가 아니다.

추가 정원 1건은 46.44초, Peak MLX 3.49GB, seed `522486703`으로 완료했다. 원본 `.local/avatar-quality-v4/local-image/runtime-garden-face-1/original-rgb.png`에서 두 눈과 앞면 얼굴이 보인다. 기존 얼굴 가림은 이번 사례에서 개선됐다. 다만 회색 구조 지도 색과 굵은 잎선이 많이 남았고 음영도 입체적이다. 최종 미적 승인으로 간주하지 않는다.

이 실행의 프롬프트는 `local-matte-face-1`이다. 이후 `local-matte-face-2`에서 구조 지도의 회색을 입력 팔레트의 밝은 파스텔 색면으로 바꾸고 짙은 외곽선을 없앴다. 축선도 얇은 안내선으로 바꿨다. 본문에는 회색은 기하 안내일 뿐이라는 점, 입력 팔레트로 몸을 채울 것, 최종 그림에 construction line을 남기지 않을 것을 명시했다. 입력 팔레트·테마를 프롬프트 데이터에도 넣었다. 41개 회귀는 새 버전으로 통과했다. 추가 정원 추론은 하지 않았고 새 버전의 실제 이미지 검증은 아래 앱 HTTP 1건으로 수행했다.

`matte_cutout.py`는 이 원본에서 잘라내기 없이 외곽 배경을 제거했다. 원본 RGB 채널은 유지했고 실제 알파 경계 contour 192점과 spine 96점을 만들었다. 원본 SHA는 `00adc5896c50b044eae982571366abff07801cca3e3d0cb8967c65e077828fb5`, RGBA SHA는 `fa28e07d7786eef705d2f8d159af247d4121edc776385d32105de53a24210fd6`이다. source는 `MEASURED_ALPHA_BOUNDARY`, mapping은 `GEOMETRIC_PROJECTION_NOT_SEMANTIC`이며 faceCenter는 미확정이다. projectionOutsideAlphaSamples는 이번 출력에서 0이었다.

원본 RGB·참조·입력·프롬프트·실행 명령·모델 commit·seed·어댑터 SHA·후처리 보고를 실행 폴더에 보관한다. API는 원본과 참조를 소유자별 불변 asset으로도 저장하고 결과 artifact.provider에 연결한다. 결과의 `motifsVerification`은 `PROPOSED_NOT_VERIFIED_IN_LOCAL_MODEL_IMAGE`다. 같은 requestId·입력은 재생성하지 않고 저장 결과를 돌려준다. 생성 모드를 끈 뒤에도 소장품은 복원된다.

신규 대역 11개와 기존 서버·이미지 프롬프트 회귀를 합친 41개 검사가 통과했다. 실제 대역 자식 프로세스로 환경변수 제거, 단일 추론, 시간 초과 후 종료, 잘못된 PNG 거절을 확인했다. HTTP 대역으로 동일 요청 재사용·입력 변경 충돌·복원·원본 asset 소유권을 확인했다. Ruff와 diff check도 통과했다.

## 최종 프롬프트의 실제 Android 생성

root가 Android 앱에서 `LOCAL_MODEL`을 선택해 서버에 실제 HTTP 생성 요청을 보냈다. requestId는 `c73d3ae5-e278-49ca-8cd3-5829676b14fe`다. 프롬프트 `local-matte-face-2`, seed `2024672754`, 512×512, 4 steps로 45.01초에 완료했다. Peak MLX는 3.49GB다. `.local/avatar-generator/local-model-runs/*/c73d3ae5-e278-49ca-8cd3-5829676b14fe/metadata.json`에서 `status=GENERATED`를 확인했다.

root의 원본 육안 확인에서는 회색 큰 몸체가 사라지고 파스텔 몸체, 드러난 두 눈, 물결 형태와 꼬리가 보였다. 이 한 건의 관찰을 전체 품질 통과로 확대하지 않는다. `humanQualityApproved=false`, `routeCorrespondenceVerified=false`, `faceVisibilityVerified=false`는 유지한다.

| 매체 | SHA-256 |
| --- | --- |
| 원본 RGB | `7081ca377fabb37af7346e1011af7d99cbe03cedb8fccb8751ec91adb83506b5` |
| 후처리 RGBA | `210826fbf49424385aed103cc80399632961d9115701550ce11f1359006bbd4c` |

원본과 RGBA는 같은 실행 폴더의 `original-rgb.png`, `character-rgba.png`다. 후처리는 잘라내기 없이 RGB 채널을 보존했다. source는 실제 알파 경계, mapping은 의미 검증 없는 기하 투영이다. 이번에는 `projectionOutsideAlphaSamples=4`로 기록됐다. 따라서 모든 투영 표본이 몸 안에 들어간다거나 원본 경로가 정확히 신체 부위에 대응한다고 주장하지 않는다. 후처리도 `RGB_PRESERVED_NOT_SEMANTIC_MATTING`으로 표시한다.

첫 UI 검사 실행은 빠른 로컬 렌더용 완료 문구를 AI 모드에서도 기대한 assertion 때문에 시간 초과했다. 이미지 생성 자체는 성공했다. root가 검사 문구를 고친 뒤 같은 requestId의 저장 결과를 재사용해 모션과 소장품 복원을 확인 중이다. 이 재검사는 추가 추론이 아니며 현재 단계에서 해당 검사의 최종 통과를 보고하지 않는다. 총 추론 횟수는 5회로 유지한다.

## 다음 판단

무료 로컬 원화 생성은 실제로 작동하고 Android 앱의 실제 요청으로도 생성에 성공했다. 다만 M4 16GB 한 대의 총 5회 측정으로 동시 사용자 처리량이나 서버 운영비를 산정할 수 없다. 클라우드로 옮길 경우의 컴퓨팅 비용도 0으로 가정하면 안 된다.

구조 대응 검증과 얼굴 가림의 자동 거절 기준은 남아 있다. 실제 알파에서 얻은 윤곽과 원본 경로의 의미상 대응도 구분해야 한다. 새 모델 추가 다운로드, 배경 제거 모델 설치, magenta 실험, 유료 호출은 하지 않았다. 앱 연결의 실제 사용자 흐름은 root의 별도 통합 검증 결과를 기준으로 판단한다.

최종 통합 결과: 같은 요청을 재사용한 Android UI 검사 13개가 통과했다. 추가 추론 없이 모션·재시도·보관 복원을 확인했다. [v4 통합 검증](test-report.md)을 따른다.
