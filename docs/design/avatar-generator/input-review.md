# 경로 입력·재시도·복귀 경계 검토

2026-11-03. 소스 검토에서 발견한 네 문제를 root가 수정한 뒤 실제 Chrome으로 다시 검사했다. 검증 도구는 [verify_avatar_input_edges.mjs](../../../scripts/verify_avatar_input_edges.mjs)이다.

## 결과

`PASS_AVATAR_INPUT_EDGES`, 10개 확인 항목을 통과했다. 결과 JSON은 프로젝트의 `.local/avatar-generator/input-edge-verification/verification.json`에 있다. 네 문제 모두 이번 브라우저 회귀 범위에서 재현되지 않았다.

| 경계 | 주입·조작 | 실제 확인 |
|---|---|---|
| 늦은 추출 응답 | 합성 내비 PNG를 실제 업로드해 서버 추출 응답을 받은 뒤 브라우저 전달만 지연. 그 사이 다른 예시를 클릭하고 원래 응답을 전달 | 나중에 선택한 경로가 유지됨. 해당 경로를 확인하면 생성 버튼이 활성화되어 busy 상태도 해제됨 |
| 원본 사진 준비 | Chrome CDP에서 원본 이미지의 실제 HTTP 응답을 보류 | 사진 로드 전에는 확인 checkbox와 생성 버튼이 모두 disabled. 응답 전달 뒤 확인 가능 |
| 생성 성공 후 목록 실패 | 실제 로컬 생성 POST 성공 뒤 실제 컬렉션 GET의 응답만 1회 503으로 교체 | 성공 결과·아바타 정체성이 유지됨. 목록 재조회 안내 표시. 생성 POST와 UUID는 각각 1개 |
| 차량 gate 복귀 | 실제 탄생 도중 UI의 native gate 콜백에 false, 이어 true를 전달 | 거부 중 생성 차단. 복귀하면 같은 아바타를 완성된 정적 화면으로 복원. 추가 생성·발화 없음 |

지연과 GET 실패만 주입했다. 경로 추출과 아바타 이미지 생성은 실행 중인 `http://127.0.0.1:8768` 서버가 처리했다. 생성 모드는 `LOCAL_RENDER`로 지정했고 반환 artifact의 모드도 확인했다. API 공급자 호출, 음성 재생, 녹화·음성 녹음은 하지 않았다.

gate 회귀는 실제 브라우저에서 호스트 콜백을 호출해 UI 복구를 검사한 것이다. 실제 차량 신호·Car service·Android WebView의 gate 동작은 root의 네이티브 통합 검사 범위이며, 이 결과로 대신하지 않는다.

## 재실행

로컬 생성 서버가 실행 중이고 launcher가 `.local/avatar-generator/connection.json`을 준비한 상태에서 실행한다. Node의 내장 WebSocket을 지원하는 버전과 macOS Google Chrome을 사용한다.

```sh
node scripts/verify_avatar_input_edges.mjs
```

도구는 포트 9225와 `.local/avatar-generator/chrome-edge-qa` 전용 프로필을 사용한다. 9225가 이미 사용 중이면 기존 세션을 건드리지 않고 실패한다. 자신이 시작한 Chrome만 종료한다. root의 9223/9224 세션은 사용하지 않는다. 연결 토큰은 파일에서 읽어 `/session`에 보내며, 로그·결과 JSON에 넣지 않는다.

실행 환경의 기본 샌드박스에서는 Chrome이 exit 134로 종료됐다. 동일 검증 명령의 실행 권한을 허용한 뒤 전용 Chrome에서 전체 PASS를 확인했다. 포트와 브라우저 경계를 바꾸거나 웹 보안 설정을 해제하지 않았다.

## 소스 검토 범위

root의 `studio.js`는 추출 요청 세대와 파일·경로 버전으로 오래된 응답을 배제한다. 원본 로드 전 확인을 막고, 생성 결과와 목록 갱신 실패를 구분한다. gate 복귀에는 기존 artifact의 정적 표시를 다시 요청한다.

텍스트 입력·파일명·생성 설명은 `textContent`와 DOM 노드로 표시한다. 해당 경로에서 직접적인 스크립트 삽입 문제는 발견하지 못했다. 서버 CSP와 같은 origin 통신, Android의 고정 loopback URL 및 native 발화의 차량 상태 검사는 함께 확인했다. 이는 모든 WebView·로컬 서버 공격에 대한 보안 인증을 뜻하지 않는다.

확인한 소스 SHA-256은 다음과 같다.

```text
0dc5e76c10381af29c6db3542fcbd7c602deb010782211b77631f3f3cabe03e0  scripts/verify_avatar_input_edges.mjs
47f99ec6bb8f55c73917e23f37f97ad20956af4faf841b2a1191048aa47457ab  prototypes/avatar_generator/studio.js
dfca76e9347789f5fce0b39a981707ab4efa0400e46a4baaccb49120f6f7ce84  android/app/src/main/kotlin/ai/nunti/app/studio/AvatarStudioActivity.kt
```

## 경로 추출의 별도 증거와 한계

추출기 전용 pytest는 41개 PASS이며 `prototypes/avatar_generator/examples/navigation-tests.xml`에 기록했다. 실제 PNG/JPEG와 중심선의 양방향 오차, 여섯 색 힌트, 복수 대안·분기·폐곡선·색 도로 격자·배경·손상 파일·크기 제한·EXIF 회전을 검사했다. 원본과 추출선을 겹친 PNG 세 장, paired JSON과 재현 스크립트는 [시험자료 안내](../../../prototypes/avatar_generator/examples/README.ko.md)에 있다.

세 경로 화면은 합성 자료다. 실제 지도·GPS·NaviHelper와 연동한 경로라는 주장은 하지 않는다. 성공 추출에도 사용자 확인을 요구하며 화면 좌표를 실제 거리·지형으로 해석하지 않는다. 임의의 실제 스크린샷 추출률과 실제 현대 내비 입력은 별도 검증이 남아 있다.
