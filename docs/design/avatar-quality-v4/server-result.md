# v4 이미지 API 입력·승인 경계 개선

2026-11-03. 전체 목표는 운전습관 개선을 돕는 눈티이며 이번 범위는 목적지·경로 기반 생성 기능의 서버 경계다. [공통 계약](IMPLEMENTATION-CONTRACT.md)에 따라 `api.py`, `image_api.py`와 관련 테스트만 변경했다. renderer·모션 파일과 기존 v2 소장품은 변경하지 않았다. 유료 생성 API 호출, 실제 키 읽기·출력, 이미지 모델 설치·다운로드·추론, 녹화·녹음은 하지 않았다.

기존의 완성 PIL PNG와 경로 그림을 함께 넣는 방식에서, 다음 세 참조를 분리했다. 공개 `render_api_image(settings, value, local_png, design)` 시그니처와 v3 입력 계약은 유지한다. `local_png`를 기존 몸체와 스타일을 복사하는 기준으로 보내는 동작은 제거했다.

| 참조 | 역할과 근거 |
|---|---|
| `structure-map.png` | 새 renderer가 준 `formation.contour/spine/faceCenter`에서 무채색 구조 스케치를 만든다. `visualIntent.routeFeatures.landmarks`의 원본 점·대응 점·부위를 A/B/C로 표시한다. 최종 색 원화나 검증된 외부 결과로 취급하지 않는다. |
| `confirmed-route.png` | 원본 정규화 점과 같은 대표 점 표지를 별도 그림으로 유지한다. 화면 좌표이며 GPS·도로 종류·위험도·운전 점수의 근거가 아니다. |
| `style-board.png` | 서버가 지정한 PNG를 재질·얼굴 표현·완성도 참조로 사용한다. 그 그림의 실루엣을 복사하지 않도록 명시한다. 없으면 기존 완성 캐릭터 대신 별도의 단순 재질 가이드를 쓰고 `PROCEDURAL_MATERIAL_STUDY`로 표시한다. |

새 구조 메타데이터가 없는 기존 renderer 호출도 유지한다. 원본 점에서 얻은 큰 굴곡은 제안으로, 직선의 흐름 표본은 `FLOW_SAMPLE`로 구분한다. 없는 굴곡이나 부위 대응을 확인된 사실로 꾸미지 않는다. renderer가 준 목적지·목적 해석도 입력 근거와 창작 해석으로 나눠 프롬프트에 넣는다.

사용자의 후속 교정으로 이전 C 반투명 재질은 최신 기준에서 바뀌었다. 현재 `route-structure-2` 프롬프트는 불투명 파스텔 색면과 얕은 2.5D 일러스트인 `MATTE_ILLUSTRATED_2_5D`를 우선한다. 유리·굴절·강한 광택·투명한 몸·실사 3D 토이 표현을 제거하고 PNG alpha는 캐릭터 바깥 배경에만 쓰도록 명시한다. 오래된 참조와 renderingStyle 메타데이터가 이 최신 피드백을 덮어쓰지 않는다. 이 변경은 사용자가 형상 A/B/C를 모두 수용하면서 요청한 스타일 교정이며 새 원화의 최종 승인이나 실제 외부 출력 검증은 아니다.

큰 몸체 덩어리, 얼굴의 판독, 목적지 특성이 몸체·재질에 반영되는 방식, 방문 목적과 자세도 지정한다. 색상·작은 모자·배에 새긴 선만으로 개인화를 완료하지 않게 한다. 구조 지도·원본 경로·스타일의 보존 조건과 바꿀 수 있는 비율·표면 표현을 따로 쓴다. 실제 alpha PNG, 한 캐릭터, 여백, 배경과 문자 금지도 명시한다. 프롬프트가 경로 일치·귀여움·소장 의향을 보장한다고 보고하지 않는다.

`image_request_references(settings, value, design)`는 키·네트워크·모델 추론 없이 실제 전송할 프롬프트와 세 PNG를 준비하는 함수다. 따라서 유료 실행 전에 입력·그림·문구를 검토할 수 있다. 전송 결과에는 프롬프트 버전·SHA, 참조별 SHA, 실제 비용 미확인, 경로 대응 미검증을 기록한다.

스타일 참조는 `NUNTI_STUDIO_STYLE_REFERENCE`로 지정하며 기본 허용 디렉터리는 `docs/design/avatar-quality-v4/assets`다. 경로를 resolve한 뒤 해당 디렉터리 밖의 경로·symlink 이탈을 거절한다. PNG 형식·크기도 검사한다. HTTP 본문에서 임의 파일 경로를 받거나 서버의 절대 경로를 외부 프롬프트·artifact에 노출하지 않는다. root가 저장한 `concept-a.png`는 이 설정의 예시로 쓸 수 있으나 사용자의 원화 승인을 뜻하지 않는다. 참조 메타데이터의 `styleReferenceHumanApproved`는 false다.

외부 API 결과는 로컬 구조 좌표와 실제 픽셀의 일치를 검증하지 않았다. 새 `IMAGE_API` artifact에서는 로컬 `design.formation`을 제거하고 `formationStatus:'API_GEOMETRY_NOT_VERIFIED'`를 표시한다. `motifsVerification:'PROPOSED_NOT_VERIFIED_IN_API_IMAGE'`도 유지한다. LOCAL_RENDER의 실제 formation은 그대로 넘긴다. 이 경계는 root와 모션 담당에게 전달했다. 기존 저장 artifact는 재생성·수정하지 않는다.

유료 실행의 기본값은 꺼짐이다. `NUNTI_STUDIO_PAID_API_APPROVED=true`가 추가로 있어야 기존 enable·키·가격·예산 조건을 평가한다. 이 값이 없으면 capabilities의 `imageApiAvailable=false`, `imageApiPaidApprovalRequired=true`이고 새 IMAGE_API 요청은 403 `PAID_API_APPROVAL_REQUIRED`다. 기존 키·enable·가격 설정만으로 다시 활성화되지 않는다. 승인 또는 활성화가 없으면 `Settings.from_env()`도 `OPENAI_API_KEY`를 읽지 않는다. 어댑터 직접 호출에도 같은 승인을 검사한다.

이 환경값은 운영자가 실제 사용자 승인 범위를 반영하는 수단이다. 환경값을 넣는 것 자체가 사용자 승인을 대신하지 않는다. 이번 작업에서 해당 승인 환경을 켜지 않았다. 대역 테스트는 가짜 키와 메모리 안 설정만 사용했다. 기존의 요청·누적 예산 예약, 중복 요청 재사용, 응답 불명확 시 자동 재시도 금지, 승인 없이도 가능한 기존 소장품 조회는 보존한다.

유료 실행 범위의 단일 기준은 [실제 이미지 API 비교 실행안](PAID-EXPERIMENT-PROPOSAL.md)이다. 아래 표는 그 내용을 따른다. 현재 사용자의 답변은 원화 선택 후 결정이므로 상태는 `WAITING_FOR_ART_SELECTION`이다. 아직 실행 승인이 아니며 계정 단가·모델 접근·참조 호환성은 미검증이다.

| 항목 | 비교 초안 |
|---|---|
| 입력 | 서로 다른 시험 여정 3개. 각 여정의 확인한 원본 경로와 그 구간별 몸체 대응을 함께 제시한다. 실제 출발지·주소·GPS를 추가하지 않는다. |
| 스타일 | `concept-a.png` 같은 원화를 사용자가 고른 뒤 사용한다. 현재 원화 승인 미완료다. 구조·원본 경로와 별도 참조로 전달한다. |
| 모델 후보 | `gpt-image-2.5-sunburst`. 현재 서버 기본 모델은 호환성을 위해 기존 `gpt-image-2.5-flare`로 유지한다. 비교 시 명시적으로 모델 설정과 계정 접근을 확인해야 한다. |
| 출력 | 1024×1024, medium, 투명 PNG, 요청당 n=1. |
| 수량 | 시험 여정 3개 × 후보 2개, 총 최대 6회. 같은 요청의 재시도를 새 후보 생성으로 세지 않으며 자동 유료 재시도는 없다. |
| 최대 예약 | 요청당 $0.30, 누적 $1.80, 호출 수 한도 6회. 예약액은 서버의 요청 허용 경계이며 공급자 실제 청구의 하드 리밋이나 단가 실측 결과가 아니다. |
| 실행 전 조건 | 사용자 원화·실행 범위 승인, 실제 계정 단가와 참조 이미지 비용 확인, 해당 모델·편집 endpoint·alpha 접근 확인, 전체 예약 합계 검토. 모르는 단가는 임의의 작은 값으로 채우지 않는다. |

현재 예산 기본값은 요청당 최대 $0.30, 누적 $6, 최대 20회라는 기존 설정을 유지한다. 위 비교안을 실행하기로 한 경우의 더 작은 수량·총예약은 승인 후 별도로 반영해야 한다. 내장 image_gen으로 만든 개념 원화와 앱이 매 여정 유료 API를 동적으로 부르는 기능은 별개다.

| 로컬 추론 환경의 읽기 확인 | 확인 결과와 한계 |
|---|---|
| 장비 | Apple M4, 통합 메모리 16GiB, macOS 26.4. 장치 이름·메모리와 버전만 읽었다. |
| 기존 PyTorch 환경 | `.local/chatterbox-audition/venv`에 torch 2.6.0, diffusers 0.29.0, transformers 5.2.0, safetensors 0.5.3. accelerate는 없다. 음성 실험용 기존 환경이다. |
| 가속 | MPS built=true·available=true, CUDA=false를 모델 로드 없이 확인했다. sandbox 안에서는 하드웨어 접근 제한으로 false였으므로 제한 밖의 읽기 확인과 구분한다. |
| 서버 환경 | 기존 서버 venv에는 PyTorch 기반 이미지 추론 스택이 없다. `.local/journey-voice-v3/venv`에도 torch·diffusers·accelerate가 없다. |
| 가능성 판단 | Metal 가속의 출발 조건은 있으나 최신 이미지 pipeline 호환·가중치·16GiB 내 메모리·속도·그림 품질은 미검증이다. 큰 FLUX/Qwen 계열의 설치나 성공을 약속하지 않는다. 작은 모델·양자화별 실제 시험이 필요하며 이번에 시작하지 않았다. |

직접 실행한 검사는 `PYTHONPATH=backend .worktrees/server/backend/.venv/bin/python -m pytest backend/tests/test_avatar_image_prompt.py backend/tests/test_avatar_studio.py -q`의 30 passed와 v3/v4 서버 패키지·소유 테스트 Ruff 통과다. 실제 프롬프트·세 참조의 바이트·대응 점·서버 전용 스타일 참조·기존 호출·승인 전 키 미조회·유료 전송 차단·예산·중복·복원·외부 formation 오인 방지를 검사했다. 최신 무광 스타일·배경에만 alpha 적용하는 문구도 확인했다.

renderer 최종 소스가 고정된 뒤 `PYTHONPATH=backend .worktrees/server/backend/.venv/bin/python -m pytest backend/tests -q`를 실행해 전체 220 passed, 7 subtests passed를 확인했다. 기존 서버의 일반 표현 입력과 목적지 이름·특성 변경도 그대로 시험했다. 폐기 예정인 TestClient의 httpx 사용 경고 한 건 외 실패는 없다. 소유 파일 `git diff --check`도 통과했다. 공급자 전송은 대역만 사용했다. 실제 새 모델의 품질·비용·지연과 사람의 원화 승인은 미검증이다.
