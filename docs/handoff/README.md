# Nunti 세션 인수인계

현재 기준은 [눈티 v6](../design/avatar-v6/README.md)와 [완료·미구현·미검증 보고](../design/avatar-v6/RESULT.ko.md)다. 실제 AI 30상황·빠른 일러스트200·캐릭터별 실제 음원200·Android 생성/재생/복원을 검증했다. [시험 안내](../design/avatar-v6/TESTING.ko.md)에서 앱과 결과 갤러리를 열 수 있다. 아래 문서는 과거 단계의 기록이며 새 음성·내비 연결 완료 여부를 현재 기준보다 우선하지 않는다.

2026-11-04 최신: 운전습관 개선을 돕는 눈티 안의 사용자 담당은 목적지·경로 기반 생성이며 [제품 기준](../product/2026-hmg-app-challenge.md)을 유지한다. 결과 표시와 보관함 갱신 사이에서 사진 업로드가 유실되는 버그를 [재현·수정](../design/avatar-quality-v5/PHOTO-UPLOAD-FIX.md)했다. 전체 7단계 직접 실행 완료: 경계15·Chrome15·Android15·저장AI14·실제Canvas7개35자세 통과. 추가AI추론·유료호출·녹화0. 이전 승인 검토 장애는 화면 검사에 대해 해소됐으며 아래 미실행 설명은 당시 기록이다. 정원 추가AI와 미적 최종승인은 별도다.

최신 작업은 [v5](../design/avatar-quality-v5/README.md)다. 운전습관 개선을 돕는 눈티의 사용자 담당은 목적지·경로 기반 생성이며 [제품 기준](../product/2026-hmg-app-challenge.md)을 유지한다. 경로의 흉터·얼룩 인상을 줄인 깨끗한 표면과 오로라 탄생 효과를 반영했다. 실제 무료 AI 해변 생성은 확인했고 최신 화면 회귀·추가 정원은 자동 승인 검토 인프라 실패로 미실행이다. 최종 승인을 완료로 취급하지 않는다. 아래 v4·v2·복원 기록은 이력이다.

현재 작업은 [v4 원화·형상·탄생 효과](../design/avatar-quality-v4/README.md)다. 운전습관 개선을 돕는 눈티 안의 사용자 담당은 목적지·경로 기반 생성이며 [제품 기준](../product/2026-hmg-app-challenge.md)을 유지한다. 사용자는 A2/B2/C2의 불투명 파스텔·얕은 매트 표현을 적절하다고 평가했다. 무료 로컬 AI를 실제 Android에 연결했고 45.01초 생성·모션·보관 복원을 확인했다. 유료 API는 보류·호출 0회, 최종 생성물 미적 승인·새 음색·습관 개선 효과는 남았다. 아래 v3·v2와 복원 설명은 과거 기록이다.

최신 작업은 [생성 동반자 v2](../design/generative-mvp/README.md), [시험 안내](../design/generative-mvp/TESTING.ko.md), [현재 상태](STATUS.md)를 따른다. API 키 없이 기존 미디어로 Android 전체 연결을 검증하는 실행본을 제공한다. 실제 API의 새 이미지·음색·한국어 품질·단가는 아직 검증하지 않았다. 아래 문서는 이전 복원과 구현 이력을 보존한 기록이다.

작성 기준은 2026-11-02, Asia/Seoul이다. PM이 기존 TTS·AVATAR·SERVER 세션에 현황 보고를 요청하고, 통합 저장소 및 보존된 검증 증거와 대조했다.

최신 사용자 요구는 [여정 캐릭터 브리프](../product/journey-character-brief.md)와 [C 방향 통합 설계](../design/journey-characters/README.md)를 따른다. 매 여행 새 캐릭터와 성격에 맞는 음성을 만들고 한 캐릭터 안에서는 정체성을 보존한다. 전역 고정 몸체·음성은 기존 MVP의 선택이며 새 제품 방향의 제약이 아니다. 레시피 실험·시안에 이어 실제 로컬 TTS 합성과 Android Debug 파일 재생을 구현했다. [최신 음성·시험 보고](../design/journey-characters/tts-result.md)를 먼저 읽는다. 새 2.5D 시각·매 여행 자동 합성·제품 host·사용자 품질 평가는 남았다. 외부 입력 payload·담당 조율은 사용자 지시로 보류한다.

새 로컬의 실제 재실행 결과는 [2026-11-02 PM 복원 보고](restoration/2026-11-02/PM.md)를 따른다. 원격 main `ebde902`에서 담당별 독립 worktree를 만들고 SERVER91·AVATAR58+1,000·TTS62+8·새 Kotlin/API·Android 빌드를 재검증했다. 공식 Console 브라우저 세션을 유지해 Pleos의 P→D·속도→P와 화면 차단·복귀, D 전환의 TTS 취소도 확인했다. 이 복원 당시 새 PCM은 수집하지 않았다. 후속 v2 TTS에서 인증 speaker PCM3개를 새로 수집했다. 한국어 사람 청취·정확한 가청 지연·실차·제품 E2E는 미검증이다.

저장소: [Pig30nidaE/NUNTI](https://github.com/Pig30nidaE/NUNTI)

구현 기준 커밋은 `bc0a9483d4baaefee397635dd3dc01fe2b7f4b3e`다. 이 문서가 추가된 커밋은 그 이후이며, 새 로컬은 원격 `main`의 인수인계 문서를 포함한 최신 커밋에서 시작한다.

| 읽을 문서 | 용도 |
| --- | --- |
| [전체 구현·작업 상태](STATUS.md) | 완료 범위, 미구현 연결, 검증 수준, 역할과 다음 우선순위 |
| [새 로컬 복원 절차](RELOCATION.md) | clone, 환경 설치, 검사, 독립 worktree 구성 |
| [이관 검증 결과](verification.json) | 문서·보존 증거 검사 결과. 신규 기능 테스트와 구분 |
| [PM 프롬프트](prompts/pm.md) | PM 세션에 그대로 붙여넣을 시작 지시 |
| [TTS 프롬프트](prompts/tts.md) | TTS 세션에 그대로 붙여넣을 시작 지시 |
| [AVATAR 프롬프트](prompts/avatar.md) | 아바타 세션에 그대로 붙여넣을 시작 지시 |
| [SERVER 프롬프트](prompts/server.md) | 서버 세션에 그대로 붙여넣을 시작 지시 |
| [TTS 담당 보고](reports/tts.md) | 기존 담당 세션의 직접 보고 |
| [AVATAR 담당 보고](reports/avatar.md) | 기존 담당 세션의 직접 보고 |
| [SERVER 담당 보고](reports/server.md) | 기존 담당 세션의 직접 보고 |

현재 상태는 합성 입력 기반의 통합 MVP다. 11월 1일에는 공식 Pleos 에뮬레이터에서 주차 아바타와 ON_DEVICE PCM 출력을 확인했다. 11월 2일 초기 복원에서는 오디오를 끄고 SDK 이벤트·차량 상태 전환을 확인했다. 후속 TTS에서는 오디오를 켜고 v2 파일 재생·인증 speaker PCM·D 취소 이벤트를 확인했다. 실제 경로·운전 이벤트 수신, Android 서버 동기화, 최종 점수·코멘트 생성은 완료되지 않았다.

이관 파일·과거 증거의 무결성 검사는 루트에서 실행한다.

```sh
python3 scripts/verify_handoff.py
```

이 검사는 과거 로그·오디오 및 문서 보존 여부를 검사한다. 새 로컬에서 앱이나 서버를 실행한 결과는 [복원 절차](RELOCATION.md)에 따라 별도로 확인한다.
