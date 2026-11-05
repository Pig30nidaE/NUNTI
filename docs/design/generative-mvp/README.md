# 여정에서 생성하는 동반자 v2

이 문서는 이전 v2 통합 실험 기록이다. 사용자 담당인 목적지·경로 기반 생성의 최신 구현은 [아바타 생성기 v3](../avatar-generator/README.md)와 [직접 시험 안내](../avatar-generator/TESTING.ko.md)를 따른다. 전체 제품 목표는 운전습관 개선을 돕는 눈티이며 [제품 기준](../../product/2026-hmg-app-challenge.md)의 역할 구분을 유지한다.

**눈티의 제품 목표는 운전습관 개선을 돕는 아바타 동반자다.** 이 시험본은 사용자 담당인 **목적지·내비게이션 경로 기반 아바타 생성 기능**의 이미지·음성 연결을 다룬다. 생성된 정체성과 미디어를 주행 이벤트에 따른 감정·음성 피드백 모듈에서 이어서 사용한다. [제품 목표·담당 범위·공모전 기준](../../product/2026-hmg-app-challenge.md)을 따른다. 현재 입력은 직접 그린 선이며 실제 내비/경로 이미지 입력은 아직 없다.

아래는 이미지·음성을 묶은 기존 서버·Android 연결 구현이다. 같은 캐릭터는 보관 후에도 저장한 음성 ID로 새 대사를 합성한다. 현재 실행 모드는 기존 미디어를 사용하는 `OFFLINE_FIXTURE`다. API 계정·새 이미지·새 음색의 실측 품질은 아직 검증하지 않았다. 현 키 세 개 요구를 제품의 필수조건으로 일반화하지 않는다.

사용자 실행은 [시험 안내](TESTING.ko.md), 실제 계정 연결은 [API 키 설정](API-SETUP.ko.md), 완료·미구현·미검증 구분은 [검증 보고](test-report.md), wire 형식은 [v2 계약](../../../contracts/v2/README.md), 모델 비교와 블라인드 평가는 [벤치마크 안내](benchmark/README.ko.md)를 따른다. 이전 절차적 외형·로컬 Sohee 생성 시험본은 [route-birth 기록](../route-birth/IMPLEMENTATION.md)에 보존한다.

## 생성 모델의 역할

기본 파이프라인 `OPENAI_ELEVEN`은 `gpt-6.1-sol`로 캐릭터 설정을 생성하고, `gpt-image-2.5-flare`에 스타일 기준 이미지와 입력 경로 그림을 전달한다. 이미지 출력은 1024×1024, medium, 투명 PNG 2후보다. `eleven_ttv_v3`가 새 음색 preview 3개를 만들고, 일반 `gemini-3.8-flash`가 이미지와 오디오를 함께 비교한다. 선정한 preview를 저장한 뒤 `eleven_v4`가 초기 대사를 합성한다.

비교 파이프라인 `GOOGLE_COMPARE`은 Gemini 기획·Nano Banana 2.1 이미지와 Gemini 3.8 Flash TTS를 사용한다. Google 이미지의 배경 투명도는 보장되지 않으므로 선정한 한 장을 Recraft에서 배경 제거한 후 RGBA를 검증한다. Google는 저장 음색의 미선정 후보가 슬롯을 계속 차지하지 않도록 신규 음색 1개를 설계한다. ElevenLabs의 3개 임시 preview와 후보 수가 다르므로 품질과 비용을 함께 비교한다.

| 항목 | 공개 가격 또는 비용 상태 |
|---|---|
| Sol 기획 | 입력 $2/M, 출력 $10/M 토큰 |
| Flare 이미지 | 텍스트 입력 $5/M, 이미지 입력 $8/M, 이미지 출력 $30/M 토큰. 장당 금액 미실측 |
| Eleven v4 | $0.08/1,000 청구자. Voice Design의 계정별 설계 비용은 별도 확인 |
| Nano Banana 2.1 | 1K 이미지 출력 $0.0336/장, 입력·thinking 별도 |
| Recraft 배경 제거 | 선정 이미지 $0.01/장 |
| Gemini Flash TTS | 2026-12-31까지 입력 $0.50/M, 오디오 출력 $9/M 토큰. 설계·대사 사용량 별도 |

가격 기준은 2026-11-03 USD다. Google 일반 Flash와 Flash TTS의 2027-01-01 인상은 계정 가격 확인에 포함한다. 구독에 포함된 사용량, 공개 단가 환산액, 실제 추가 청구액을 중복 합산하지 않는다. 여정당 $0.10–0.30은 운영 변동비 목표이며 달성 검증 결과가 아니다.

공식 근거: [OpenAI 모델과 가격](https://developers.openai.com/api/docs/models/gpt-image-2.5-flare), [투명 이미지](https://developers.openai.com/api/docs/guides/image-generation#transparent-backgrounds), [ElevenLabs Voice Design](https://elevenlabs.io/docs/api-reference/text-to-voice/design), [ElevenLabs 가격](https://elevenlabs.io/pricing/api), [Google 가격](https://ai.google.dev/gemini-api/docs/pricing), [Recraft 배경 제거](https://www.recraft.ai/docs/api-reference/tools/remove-background).

## 캐릭터의 정체성과 소장품

새 여정 UUID와 입력을 기획 요청에 포함한다. 모델은 경로의 형태와 목적지에서 일관된 외형·성격·음색 설명을 생성한다. 이미지와 음성은 같은 `specHash`에 귀속된다. 공급자 이미지 생성의 seed 재현에 의존하지 않고 실제 확정 파일을 보관한다.

`GenerationJob`은 진행 상태다. `CharacterArtifactV2`는 모든 미디어 검증이 끝난 후 한 번만 확정한다. 후속 대사는 별도 불변 manifest로 추가한다. 동일 캐릭터의 같은 본문은 기존 clip과 오디오를 재사용한다. 재시도·복원·추가 대사가 원래 외형·음색을 바꾸지 않는다.

새 여정마다 실제 새 생성 요청을 보내는 API 구조다. 초기 20개 입력과 내부 이미지·음성 후보 수는 시험 수량이다. 전 세계의 시각적 유일성이나 사람의 귀여움 판단을 UUID 또는 모델 점수만으로 보증하지 않는다.

캐릭터 저장소는 v1 여행 기록의 만료·삭제와 분리한다. 원래 PNG, 공급자 원응답·원본 오디오, 검증한 재생 WAV와 SHA를 서버에 저장한다. 미디어는 owner 인증을 거친 같은 서버에서 제공하며 앱은 파일 크기·형식·해시·캐릭터와 음성 바인딩을 검증한다.

## Android의 표시와 발화

완성 PNG에는 얼굴이 포함된다. 앱은 실제 경로의 같은 점을 이미지 알파 폭에 맞춘 일곱 겹 리본으로 변형하고, 그 리본의 붓에서 원본 표면을 공개한다. 준비 계산이 끝난 뒤 연출을 시작하며, 그림 전체의 착지·호흡·둥실거림·기울기·접지 그림자를 표현한다. [탄생 연출 구현과 검증](route-formation.md)에 비교 시안과 실제 앱 검사 근거가 있다. 독립적인 눈·입 애니메이션이나 완전한 3D 리깅은 포함하지 않는다.

기존 주차·화면 사용 허가·foreground·quiet 확인과 재생 큐를 사용한다. 준비·복원·새 대사 추가는 자동 발화하지 않는다. 검증한 catalog를 확장해도 현재 queue와 반복 발화 억제 기록을 유지한다. 중지는 현재 음성과 대기 음성을 모두 취소한다.

## 계정과 비용의 경계

API 키는 서버 환경변수에만 있다. Android에 전달하는 로컬 owner 토큰은 공급자 API 키가 아니며 앱 전용 파일에 저장한다. 실행 도구의 fixture 모드는 공급자 키를 자식 프로세스 환경에서도 제거한다.

API 모드는 키와 파이프라인 전체 가격 설정이 검증돼야 첫 외부 호출을 시작한다. 단계별 비용 예약과 실제 청구액은 별개다. 실청구액이 불명확하면 null을 유지한다. 중간 응답 유실이나 프로세스 종료로 외부 결과가 불명확하면 `RESULT_UNKNOWN`으로 남기고 유료 POST를 자동 반복하지 않는다.

보관 음색은 자동 삭제하거나 다른 공급자로 교체하지 않는다. 매 생성 전에 실제 잔여 슬롯을 조회하고 부족하면 새 생성을 중단한다. 초기 20개를 시작하기 전에는 계정 한도도 확인한다. ElevenLabs Creator의 공개 한도는 30개다. Google 저장 음색은 프로젝트당 200개이며 1년 미사용 만료 조건이 있으므로 장기 운영 시 유지 작업이 필요하다. 공급자가 기존 음색을 제공하지 못해도 보관된 WAV는 재생하고 새 문장 합성은 명확히 실패한다. [음성 슬롯](https://elevenlabs.io/docs/help-center/account/general/how-many-voice-slots-do-i-get-per-tier-and-how-can-i-increase-it), [Google 음성 수명](https://ai.google.dev/gemini-api/docs/voice-design#manage-your-voices).

Google 음성 만료 점검과 월별 유지 작업 제출 CLI, 실제 영수증에 따른 비용 확정 CLI를 구현했다. [서버 운영 안내](../../../backend/README.md#저장-google-음성-만료-점검)를 따른다. 자동 스케줄은 등록하지 않았으며 실제 계정의 TTL 연장·청구는 미검증이다.
