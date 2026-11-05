# 실제 로컬 AI 30개 생성 검증

사용자 요청에 따라 실제 AI 검증 범위를 30개로 줄였다. `ai-cases-30.json`이 `.local/avatar-v6/matrix/voice-input.json`의 200개 캐릭터 플랜 가운데 실제로 생성할 30개를 지정한다. 200개 전체 AI 생성은 실행하지 않는다. 기존 절차형 렌더 200장과 실제 TTS 200개 검증은 유지한다.

선정한 30개의 입력 플랜은 20개 목적지를 모두 포함한다. 시험에 사용한 방문 목적 10종을 각각 3번, 동물형 몸 12종을 각각 2~3번 지정한다. 모델이 실제로 그린 종의 충실도는 별도 시각 검토 항목이며 입력 범위와 같다고 가정하지 않는다. 서울역과 수원역은 출장·수영·데이트, 을왕리는 출장·수영·휴식을 대조한다. 시험 매니페스트에 없는 STUDY·FOOD·EXPLORE 역할을 검증했다고 보고하지 않는다.

실제 FLUX.2 Klein 4B 4bit에 각 시점의 production prompt·512px 의상/장소 구조 참조·256px 얼굴/질감 참조·512px 결과·4step·cutout-v2를 적용했다. 기존 캐릭터의 이름과 음성은 유지한다. 새 HTTP 요청 30회를 제출하는 검증과는 구분한다.

첫 30회 결과는 원본 30장, 투명 이미지 29장이었다. AI 담당 2명이 실제 결과를 나누어 확인했을 때 목적 의상은 30개 모두 읽혔지만, 목적지 상징은 6개에서 약해지거나 누락됐다. 그중 `07-night`는 실제 밤하늘 배경을 생성해 `BACKGROUND_NOT_FLAT`으로 올바르게 거절됐다. 첫 결과는 `.local/avatar-v6/ai-matrix-final/`에 실패까지 보존한다.

공통 production prompt를 `local-journey-character-7`로 개선해 같은 입력·캐릭터 플랜·seed·모델 설정으로 실패 6개를 다시 생성했다. 큰 목적지 가방의 외곽과 평면 배경 지시를 명시했고, 6개 모두 목적 의상과 장소 상징이 복구됐다. `10-art`의 분리된 붓은 원본 구조 참조의 손/소품 위치 불일치를 추가로 발견한 사례다. 의미 검토와 모든 세부 소품·손의 완성도를 구분하여 기록한다. 재시도 이미지는 `.local/avatar-v6/ai-matrix-repair-1/`에 보존한다.

그립 좌표를 고친 뒤 `10-art` 1개를 `.local/avatar-v6/ai-matrix-repair-2/`에서 다시 생성했다. 붓과 손이 맞물리고 추가 손처럼 보이던 돌출이 사라진 것을 두 AI 담당이 실제 PNG에서 확인했다. 최종 갤러리는 **`.local/avatar-v6/ai-matrix-selected/index.html`**이다. 선택된 30개 모두 실제 RGBA·핵심 의상·목적지 상징·같은 캐릭터의 실음원 연결을 확인했다. 이 행렬 실험의 총 모델 시도는 **37회(30+6+1)**이며, 다른 초기 모델 비교 실험이나 별도 앱 통합 시험은 이 수에 합산하지 않는다.

핵심 의미 통과는 세부 완성도의 전부가 아니다. 선택본의 활동 부소품은 명료 16개·일부 누락/약화 9개·누락 5개, 동물종 충실도는 명료 26개·불명확 4개였다. 지각 유사도 기준에 걸린 후보는 0개지만 이는 미적 고유성을 증명하지 않는다. `final-audit.json`과 case별 리뷰에 한계를 남겼으며 사람의 미적 승인·전체 음성 청취를 수행했다고 보고하지 않는다.

## 준비와 실행

TTS 200개 합성이 끝난 뒤 실행한다. 같은 GPU 잠금 파일을 사용하므로 다른 음성/이미지 모델이 실행 중이면 `GPU_BUSY`로 종료한다. 실제 이미지 생성을 시작한 뒤에는 배치가 끝날 때까지 잠금을 유지한다.

```sh
.worktrees/server/backend/.venv/bin/python scripts/verify_avatar_v6_ai_matrix.py --prepare --output .local/avatar-v6/ai-matrix-recheck
.worktrees/server/backend/.venv/bin/python scripts/verify_avatar_v6_ai_matrix.py --run --output .local/avatar-v6/ai-matrix-recheck
```

기본 하위집합은 `docs/design/avatar-v6/ai-cases-30.json`이다. 위 명령은 기존 증거와 분리된 새 폴더를 사용한다. `ai-matrix-final`에는 이전 production 버전의 첫 결과가 있어 현재 버전으로 덮어쓰는 실행이 거절된다. 다른 선정안을 쓰려면 `--subset <JSON>`을 지정한다. `--limit 3`은 그 하위집합 가운데 앞의 3개만 실행하는 점검 옵션이며 전체 30개 성공으로 처리하지 않는다.

중단 후 같은 명령을 실행하면 저장된 작업 fingerprint와 실제 이미지 SHA를 확인하고 이어간다. 입력·참조·prompt가 달라졌으면 기존 결과와 섞지 않고 새 `--output` 폴더를 요구한다. 배경 제거 실패는 원본을 보존한다. `--retry-failed`는 저장된 원본을 먼저 재사용하므로 모델 생성 자체를 불필요하게 반복하지 않는다.

실제 배경이나 소품을 잘못 그린 경우에는 `--retry-failed`로 해결할 수 없다. 공통 production 변경을 먼저 검증하고, 실패 case만 지정한 별도 `--subset`과 새 `--output`에서 모델을 실행한다. 같은 case의 재시도는 새로운 상황 수에 더하지 않는다. 실행별 `worker-env-*` 디렉터리를 사용하므로 중단 후 재개할 때도 사용자 계정 파일과 분리된 새 환경을 만든다.

실행 중 `--stop-after-current`를 호출하면 현재 이미지를 저장한 뒤 멈춘다. 다시 이어갈 때는 출력 폴더의 `STOP_AFTER_CURRENT` 파일을 지운다. 이 표시는 실패 결과를 삭제하거나 진행 기록을 초기화하지 않는다.

모델과 Python 패키지는 이미 설치된 로컬 환경만 사용한다. CLI에는 서로 다른 입력을 위한 `--batch` 옵션이 없어 설치된 `Flux2KleinEdit.generate_image()`를 반복 호출한다. 모델은 한 번 읽고 text encoder와 transformer를 유지하며, 호출마다 prompt와 참조 이미지를 교체한다. GPU cache는 1GB로 제한한다. 모델 변경·추가 다운로드·유료 API 호출은 하지 않는다.

얼굴 참조를 512px에서 256px로 줄이는 비교에서는 같은 seed의 출장·수영 두 사례가 각각 41.35→32.12초, 41.81→32.17초로 감소했다. 얼굴·의상·기념 가방을 직접 비교한 뒤 적용했다. 구조 참조와 결과 해상도는 그대로다. 실험 원본은 `.local/avatar-v6/ai-matrix/`, `.local/avatar-v6/ai-style256/`, 비교 자료는 `.local/avatar-v6/style-resolution-comparison.jpg`에 보존한다.

## 진행 확인과 시각 검수

```sh
.worktrees/server/backend/.venv/bin/python scripts/verify_avatar_v6_ai_matrix.py --summarize --output .local/avatar-v6/ai-matrix-selected
.worktrees/server/backend/.venv/bin/python scripts/verify_avatar_v6_ai_matrix.py --status --output .local/avatar-v6/ai-matrix-selected
```

두 명령은 GPU를 사용하지 않는다. 각 실행 또는 선택 출력 폴더에 다음 자료를 만든다.

- `jobs.json`: 선정한 30개 입력 fingerprint, 실제 범위 통계, 모델 revision, 정확한 prompt·참조·소스 해시.
- `cases/<id>/`: 실제 RGB 원본, RGBA 결과, 구조 참조, prompt, 배경 제거 및 생성 기록.
- `worker.log`: 실제 모델 로딩·생성 시간, 성공·실패 진행 기록.
- `index.html`, `contact-sheets/`: 실패 원본과 대기 상태까지 포함한 전체 갤러리.
- `report.json`: 실제 모델 원본 수, RGBA 성공 수, 실패 코드, 픽셀 중복과 근접 중복 후보.

알파 배경 제거 성공은 의상·소품·단일 캐릭터·장소 의미가 맞다는 증거가 아니다. 모든 결과를 실제로 보고 `visual-review.json`에 case별로 단일 캐릭터 여부, 목적 의상 가독성, 장소 소품, 얼굴 가림, 원치 않는 피부 흔적, 관계없는 의상·소품 혼입을 기록한다. 목적 의상이 맞아도 목적지 상징이 일반 가방으로 사라졌으면 핵심 의미 검토에서 실패로 남긴다. 세부 소품·손 접촉·동물종 충실도는 따로 기록한다. 데이트 코트와 꽃이 있어도 수경까지 섞였다면 검토에서 실패로 남긴다. 모델이 그리지 않은 부분을 입력 metadata가 존재한다는 이유로 통과시키지 않는다. 검토자는 AI이며 사람의 미적 승인이나 전수 청취를 대신하지 않는다.

리뷰는 실제 raw/RGBA 파일 SHA와 일치해야 유효하다. 이미지를 교체했거나 같은 case의 리뷰가 중복되면 집계에서 거부한다. 갤러리는 파일 생성 상태 `READY`와 목적 의상·장소 상징의 의미 검토를 별도로 표시한다.

검수한 재시도에서 최종 선택본을 만들 때는 `--select-from <첫 결과> <재시도 결과> ... --output <새 폴더>`를 사용한다. 도구가 같은 입력·디자인인지 대조하고, 실제 이미지 해시가 맞는 최신 핵심 의미 통과본을 선택한다. 새 모델 추론은 실행하지 않으며 원본·실패를 지우지 않는다. `selection.json`에 모든 시도, 선택 출처와 전체 모델 시도 수가 남는다. 최종 선택본의 30개와 재시도를 포함한 모델 실행 수는 서로 다른 값이다.

```sh
.worktrees/server/backend/.venv/bin/python scripts/verify_avatar_v6_ai_matrix.py \
  --select-from .local/avatar-v6/ai-matrix-final .local/avatar-v6/ai-matrix-repair-1 .local/avatar-v6/ai-matrix-repair-2 \
  --output .local/avatar-v6/ai-matrix-selected-copy
```

그립 수정 후 절차형 200장도 다시 만들었다. 8장만 픽셀이 바뀌었고 192장은 동일했다. 캐릭터 플랜·이름·입력은 전부 같으며, 바뀐 8장의 실루엣에서 파생된 `geometrySignature`와 `formation.contour`는 새 값으로 갱신했다. 기존 WAV 200개를 다시 연결해 파일 해시와 음성계획이 유지되는지 검사했다. 수정 전 전체 자료는 `matrix-before-grip/`, 비교 결과는 `matrix/grip-regression.json`에 보존한다.

절차형 렌더 200장과 AI 생성 30장은 별개 수치다. 성공한 원본 30장이라도 의상 누락·다중 캐릭터·배경 제거 실패가 있으면 해당 사례를 명시한다. 실제 음원 재생과 청취 평가는 별도이며 자동 재생하지 않는다. AI 갤러리는 선정한 같은 캐릭터의 음성 30개만 연결하고 연결 수를 실제로 계산한다.
