# 목적지·경로 기반 눈티 생성 구현 계약

2026-11-03. 전체 제품 목표는 운전습관 개선을 돕는 눈티. 이번 구현은 사용자의 목적지·경로 기반 생성 기능이다. 녹화·녹음 금지. 기존 변경을 되돌리거나 v2 소장품을 변경하지 않는다.

## 사용자 흐름과 선택

여정 입력 → 원본 경로와 확인된 선 → 새 눈티 탄생 → 특징 설명·목소리·보관 → 복원.

기존 v2 일괄 이미지/음성 완료와 새 생성기 분리 두 안을 비교했다. v2 소장품은 그대로 두고 별도의 `/v3` 생성기를 선택한다. 음성 실패가 시각 결과를 막지 않는다. 로컬에서는 입력과 새 여정 ID에서 실제 새 RGBA를 렌더한다. 로컬 렌더를 AI 생성으로 부르지 않는다. 외부 API는 명시적으로 선택할 때만 사용한다.

## 공통 인터페이스와 파일 소유

- root: `prototypes/avatar_generator/` HTML/CSS/JS 화면, `scripts/run_avatar_generator.py` 실행기, Android main 호스트, 최종 검증·사용 안내.
- server agent: `backend/nunti/avatar_studio/` 단 `illustration.py`, `navigation.py` 제외. 별도 FastAPI 앱 `nunti.avatar_studio.api:app` port 8768. HTTP는 loopback만. 상태 `.local/avatar-generator`. 서버는 같은 origin의 화면 제공. 데이터 JSON은 `{data: ...}`. UI GET는 공개, 모든 `/v3` API는 launcher가 만든 bearer token 인증. URL에 키/토큰을 넣지 않는다. root가 앱에 bootstrapped connection을 주며 로컬 브라우저는 session bootstrap 방식 협의.
- illustration agent: `backend/nunti/avatar_studio/illustration.py`, `backend/tests/test_avatar_illustration.py`, `docs/design/avatar-generator/illustration/`만. `render_avatar(points, destination, traits, purpose, journey_id) -> (png_bytes, design_dict)` 공개 함수. points는 0..1 좌표 list. RGBA 768x768, 실제 alpha, 고정 얼굴이미지 복사 금지. 귀여운 반투명 2.5D, 경로 motif를 몸체 안에 보존. 디자인 dict는 `displayName, personality, palette, motifs, voice` 포함. motif는 `label, source, target, detail` strings. voice는 로컬 재생용 설계 `description, rate, pitch`.
- navigation agent: `backend/nunti/avatar_studio/navigation.py`, `backend/tests/test_avatar_navigation.py`, `prototypes/avatar_generator/examples/`만. `extract_route(png_bytes, color_hint=None) -> dict` returns `points, confidence, warnings, imageWidth, imageHeight`; 이미지 전체의 0..1 좌표. 잘못된 입력/불명확한 복수 경로는 에러 또는 확인필요 경고. 스크린샷임을 표시, GPS 추정 금지. 공개 데이터/합성 내비 시험 이미지와 paired JSON 최소3개. 소스 provenance명시.

## v3 HTTP 경계, root UI가 사용할 형태

- GET `/v3/capabilities` → `{mode:'LOCAL_RENDER', ...}`
- GET `/v3/examples` → `[{id,title,destination:{name,traits},purpose,route:{points,inputOrigin:'TEST_ROUTE',sourceLabel,confirmed:true},imagePath}]`
- POST `/v3/route-extractions` `{imageBase64}` → `{extractionId,points,confidence,warnings,imagePath,inputOrigin:'NAVIGATION_SCREENSHOT'}`. 원본은 private asset로 보관. 사용자 확인 필수.
- POST `/v3/avatars` `{requestId:UUID,destination:{name,traits},purpose,route:{points,inputOrigin:'TEST_ROUTE'|'NAVIGATION_SCREENSHOT'|'ROUTE_FILE',sourceLabel,confirmed:true,extractionId?:UUID}}` → 최종 artifact. 같은requestId·같은본문 재사용, 다른본문409. 새requestId 새여정.
- artifact `{schemaVersion:3,characterId,requestId,inputSha256,displayName,destination,purpose,route,visual:{path,sha256,width,height},design:{...renderer dict},voice:{status:'DEVICE_READY',description,rate,pitch},mediaOrigin:'LOCAL_RENDER',createdAt}`. 이미지 완료와 voice상태 독립.
- GET `/v3/avatars` → list artifacts, GET `/v3/avatars/{characterId}` → artifact. 즉시보관/복원.
- GET `/v3/assets/{sha}` → same-owner immutable bytes. imagePath도 이 형태.
- GET `/` UI static. 인증: root UI fetch reads token from location-independent bootstrap. server agent chooses secure HttpOnly SameSite cookie bootstrap `/session` POST if easiest; bearer API must also work for Android launcher/probe.

## 검증 계약

같은 입력의 재시도는 SHA·identity 고정, 새여정은 새외형. 경로/목적지 변경 시 이미지와 설명 변화. 원본PNG·SHA·투명도검사. 이미지 실패를 준비완료로 표시하지 않는다. API인증·다른owner격리·잘못된파일·복수경로·空경로 검사. 실제 브라우저와Android 주차 gate에서 입력→이미지→보관→재시작복원 시험. 생성 때문에 자동발화하지 않음. 녹화없음.
