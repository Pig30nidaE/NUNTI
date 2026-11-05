# v4 경로에서 몸체로 형성되는 모션 검증

2026-11-03. 최신 기준은 사용자가 승인한 A2/B2/C2의 불투명 파스텔·매트 2.5D 표현이다. 로컬 원화와 모션의 소장 매력은 별도 사용자 평가가 남아 있다. 이 작업의 외부 생성 API 호출·음성 재생·녹화는 모두 0이다.

## 구현 결과

`formation.js`가 `LOCAL_RENDER`의 검증된 `route-volume-2` 메타데이터를 읽는다. 입력 경로를 호길이로 표본화하고, 같은 표본 순서로 완성 몸체의 spine에 대응한다. 목표 spine의 호길이를 다시 계산해 대응 순서를 바꾸지 않는다. 외곽선의 양쪽 경계는 시작과 도착 사이를 각각 단조롭게 따라가도록 연결한다. 굽이마다 독립 최근접점을 쓰면서 생기던 넓은 가짜 다각형도 이 구조에서 없앴다.

4.8초 동안 다음 동작을 진행한다.

| 진행률 | 동작 |
| --- | --- |
| 0–.20 | 원래 경로 전체를 표시하고 펜끝이 호길이를 따라 이동 |
| .14–.26 | 작은 반대 방향 당김으로 예비동작 |
| .20–.52 | 동일 순서의 점들이 중간 자세를 거쳐 몸의 흐름으로 이동 |
| .28–.74 | 닫힌 외곽선이 실제 면적을 넓히며 몸체 형성 |
| .66–.82 | 얼굴 위 부속 형태의 작은 지연 흔들림, 얼굴은 강체 패치로 보호 |
| .82–.94 | 외곽이 완성 형상과 일치한 뒤 원본 PNG 재질로 교체 |
| .78–1 | 가로·세로 곱을 유지하는 작은 탄성 착지 |

부푸는 중간 프레임은 변화하는 닫힌 도형을 직접 채워 그린다. 완성 PNG 전체가 등장하는 시점은 외곽선이 완성 좌표에 도달한 뒤다. 얼굴 패치는 원본을 변형하지 않고 이동시키며, 부분 alpha가 두 번 겹치지 않게 합성한다. 몸체는 불투명 바탕과 옅은 아래 색면으로 표현한다. 큰 gradient·radial 광택을 제거했고, 과한 빛·굴절·별 폭발을 추가하지 않았다.

처음에는 입력 경로 전체가 보인다. 접히는 동안 같은 행렬을 연속 보간하여 완성 몸체 bbox를 화면 높이 76%, 최대 너비 78%에 맞춘다. 넓은 가로형은 비율을 유지하므로 너비 제한에 먼저 도달한다. PNG 파일을 잘라 저장하지 않으며 외곽·spine·얼굴·원본 PNG에 같은 변환을 적용한다.

이전 소장품, 잘못된 메타데이터, 형상 일치가 검증되지 않은 API 이미지는 기존 표시로 처리한다. 감소된 동작 설정과 보관함 복원은 완성 정지 그림이다. 이미지 로딩의 기존 요청 식별, 사진 확인, 차량 gate와 복귀 동작을 유지했다.

## LOCAL_MODEL 지원 경계

`#render-mode`의 `LOCAL_MODEL` 옵션은 '로컬 AI · 약 1분'이다. `caps.localImageModelAvailable`이 true면 유료 API의 활성 여부와 독립적으로 선택할 수 있다. 빠른 `LOCAL_RENDER`는 기본값으로 유지한다. 대기 화면에도 로컬 AI 생성 중임과 예상 시간을 표시한다.

LOCAL_MODEL은 `source='MEASURED_ALPHA_BOUNDARY'`와 `mapping='GEOMETRIC_PROJECTION_NOT_SEMANTIC'`를 가진 실제 alpha 측정 외곽만 수용한다. 측정 자료가 없거나 잘못되면 탄생 모션을 생략하고 그 이유와 원본 정지 그림을 표시한다. 로컬 일러스트의 원형 몸체를 AI 이미지에 있다고 가정하지 않는다.

`faceCenterVerified===true`가 아닌 AI 그림에는 얼굴 패치용 Canvas를 만들지 않는다. `faceCenter=null`과 추정 좌표를 모두 미확정으로 처리하고, 얼굴은 마지막 원본 재질 전환에서 나타난다. 초기 순수 검사에서 null/false/필드 생략/명시 true를 각각 확인했다. 알 수 없는 얼굴에 부속 형태의 지연 흔들림도 임의로 적용하지 않는다.

결과 화면은 로컬 AI의 출처, 모티브·경로 의미 일치 미검증, 측정 외곽에 대한 기하 연출, 얼굴 위치 미확정을 각각 표시한다. 외부 API 승인 상태를 이 모드의 실행 승인으로 대신하지 않는다.

실제 AI cutout은 `.local/avatar-quality-v4/cutout/nunti-local-{coast,garden}-no-inset-edit`의 PNG/JSON을 시험용 폴더에 바이트 그대로 복사해 검사했다. 두 형상 모두 미확정 얼굴 패치 0과 완성 원본 복원을 확인했다. 정원 그림은 얼굴 가림이 남아 `FACE_OCCLUSION_FAILED`로 기록했다. 외곽 모션 검사가 이 미적 실패를 품질 합격으로 바꾸지 않는다.

## 실제 적용한 스킬

LottieFiles가 발행한 MIT [motion-design SKILL.md](https://github.com/LottieFiles/motion-design-skill/blob/main/skills/motion-design/SKILL.md) 원문과 [감정·서사·동작 설계](https://github.com/LottieFiles/motion-design-skill/blob/main/skills/motion-design/director/core-philosophy.md), [애니메이션 원칙](https://github.com/LottieFiles/motion-design-skill/blob/main/skills/motion-design/director/disney-principles.md)을 읽고 적용했다. 라이선스는 [공식 LICENSE](https://github.com/LottieFiles/motion-design-skill/blob/main/LICENSE)에서 확인했다.

감정 목표를 '내 경로에서 작은 생명이 태어남'으로 정하고, 외곽의 성장을 주 동작으로 삼았다. 예비동작·중간 자세·감속·지연된 부속 형태·접지 그림자를 구현했다. 중요한 상태 변화를 opacity만으로 처리하지 않았고, 얼굴과 원본 비율을 지켰다. 4.8초는 일반 UI 전환의 권장 시간보다 긴 다단계 탄생 장면으로 정한 값이다. Rive나 Lottie 런타임을 설치하거나 사용하지 않았으며 구현은 Canvas 2D다.

## 검증과 재실행

```sh
node prototypes/avatar_generator/formation.test.mjs
node prototypes/avatar_generator/verify_formation.mjs
node scripts/verify_avatar_input_edges.mjs
```

두 번째 검사는 로컬 8768 서버가 필요하다. 전용 Chrome 9227에서 실제 Canvas와 renderer가 만든 8개 PNG/JSON을 사용한다. 세 번째 검사는 별도 Chrome 9225와 로컬 연결 파일을 사용하며 토큰을 출력하지 않는다. 기존 9223/9224 세션에 접근하지 않는다.

| 검사 | 결과 | 증거 |
| --- | --- | --- |
| 순수 기하 | 3개 경로 + 실제 10개 형상, 13,013프레임 PASS | `.local/avatar-quality-v4/motion-qa/geometry-verification.json`. 원본 호길이 대응, 외곽·화면 fit 연속성, 처음 전체 경로, 마지막 외곽, 얼굴 고정, 원본 불변 |
| 실제 Chrome 픽셀 | 10개 × 5개 정지 자세 PASS | `.local/avatar-quality-v4/motion-qa/verification.json`. 로컬 일러스트 8개와 실제 AI cutout 2개 |
| 형상과 실제 PNG 외곽 | 일러스트 IoU .9933–.9953, AI coast .9895/garden .9892 | 동일 보고서의 `contourAlphaIou` |
| 완성 원본 그림 | 불투명 픽셀 차이 0 | `opaqueChangedPixels=0` |
| 부분 alpha 가장자리 | 최대 1/255 차이 | premultiplied-alpha 재표본화 양자화 허용. 원본 PNG SHA와 논리 외곽은 불변 |
| 실제 브라우저 기능 경계 | 10개 PASS | `.local/avatar-generator/input-edge-verification/verification.json` |
| 생성 방식 UI | capability 3조합 PASS | 실제 Chrome UI에 capability 응답만 대역. 로컬 AI on/API off, 반대 조합, 둘 다 off. 생성 POST 없음 |
| 실제 AI 그림의 UI 경계 | coast/garden 각 유효·잘못된 formation PASS | 출처 문자열 유지, 얼굴 미확정 안내, 모티브 미검증 안내, 잘못된 source의 원본 정지 표시. 앱 UI의 메타데이터는 시험용이며 생성 POST 없음 |

브라우저 기능 검사는 늦은 추출 결과가 새 선택을 덮지 않음, 원본 이미지 로딩 전 확인 금지, 목록 GET 실패 후 생성 결과 보존과 중복 UUID 제출 방지, 차량 gate 복귀를 실제 로컬 HTTP 통신으로 확인했다. 지연과 GET 실패만 주입했다.

정지 자세는 `.local/avatar-quality-v4/motion-qa/keyposes-{1,2,3}.jpg`와 AI coast의 개별 `.75/1` PNG에서 직접 확인했다. 가로·세로·역방향 경로가 서로 다른 중간 몸체를 만들며 확인된 얼굴의 좌우와 비율을 지킨다. 최신 Canvas 50개 정지 자세의 관측 최대 처리 시간은 약 3.3ms였다. 실제 차량 기기의 연속 프레임 성능 측정은 이 수치에 포함되지 않는다.

## 소스 고정

`formation.js` SHA-256: `67fa1d1892a70654bd123d8d8becde2a6442de67db28d9172d319d0f9c8a3d03`.

`studio.js` SHA-256: `c4cfdaa6ec33b430081b516f52d11324aea4d331bc6cf0cfb8a240e121d2c41c`.

API 이미지의 실제 실루엣 검증, 얼굴을 포함한 AI 이미지의 리깅, 실제 차량 성능과 사용자 미적 평가는 완료로 표시하지 않는다. 최신 스타일 참조 원화를 매번 새로 생성된 runtime 캐릭터처럼 재사용하지 않는다.
