# 목적지·경로 기반 아바타 생성 기능의 감사

이 문서는 v3 구현 전의 감사 기록이다. 이후 경로 사진·좌표 입력, 시각 결과 분리, 새 로컬 일러스트와 main 호스트를 구현했으며 최신 상태는 [생성기 v3](../design/avatar-generator/README.md)와 [통합 결과](../design/avatar-generator/test-report.md)를 따른다. 아래 소스 지적은 당시의 v2 상태다.

전체 제품 목표는 **운전습관 개선을 도와주는 아바타 눈티**다. 이 감사는 사용자 담당인 목적지·경로 기반 생성 기능과 시험 화면의 구성에 한정한다. 아래의 첫 경험·화면 배치·후순위 제안은 이 생성 화면 안에서의 순서이며 전체 제품의 감정·TTS·주행 피드백 우선순위를 정하지 않는다. 생성한 정체성과 미디어는 해당 모듈에서 이어서 사용한다. 실제 개선 효과는 미검증이다.

감사 후 PM이 [공모전 기준과 제품 범위](../product/2026-hmg-app-challenge.md)를 작성하고 README·PM 시작 지침·현황·제품 브리프의 시작점을 교정했다. 아래 문서 불일치 지적은 수정 전 상태를 보존한다. 앱·서버 코드에 대한 감사와 미구현 판정은 그대로다.

2026-11-03 소스 기준. 이번 감사는 문서와 코드만 읽었다. 외부 API, 계정, 빌드, 실행 시험, 녹화는 사용하지 않았다. 아래 재설계는 제안이며 현재 구현 사실과 구분한다.

담당 생성 기능의 첫 경험은 **목적지와 경로를 불러오면, 그 여정의 특징이 귀여운 새 아바타의 외형이 되는 것**이어야 한다. 현재 시험본은 손그림 입력, 이미지·음성의 일괄 준비, 여러 재생·보관 조작을 한 화면에 놓는다. 이 구성으로는 사용자가 경로에서 무엇을 얻는지 이해하기 어렵다. 반투명 2.5D 기념 오브젝트 방향과 같은 캐릭터의 외형·음색 보존은 유지한다.

이번 제품은 2026 현대자동차 앱 공모전의 차량 앱이라는 사용자 정정을 우선한다. 자유 드로잉으로 그림을 만드는 설명만으로는 차량 안에서 써야 하는 이유와 제공 SDK의 활용을 설명하지 못한다. 첫 경험은 차량에서 선택한 오늘의 목적지·경로가 나의 동반자가 되는 과정으로 설명해야 한다. 스크린샷·시험 경로는 실제 내비 연결 전의 입력 대안이지 NaviHelper 연동의 완료 증거가 아니다. [공모전 공식 안내](https://appdevchallenge.auto-hmg.io/)의 제공 기술·심사 기준·제출 요건은 PM의 공식 자료 검토에서 확정하며, 이번 소스 감사에서는 요강을 독립 확인하지 않았다.

Gelo라고 언급된 제품은 PM이 확인하는 현대 Gleo AI 음성·LLM SDK 맥락으로 정리한다. 이를 아바타 이미지를 만드는 모델로 단정하면 안 된다. 현재 Android·backend·contracts 소스에서는 Gleo 명칭의 SDK 연결을 찾지 못했다. 현재 존재하는 Pleos TTS 어댑터와 Gleo 활용 완료도 같은 의미가 아니다.

| 현재 흐름에서 가려지는 핵심 | 소스 근거 | 가장 작은 수정 방향 |
|---|---|---|
| 실제 목적지·내비 경로 대신 사용자가 선을 새로 그린다. | [요청 구성](/Users/pig30nidae/NUNTI/android/app/src/debug/kotlin/ai/nunti/app/generated/GeneratedCompanionActivity.kt:157), [드래그 입력](/Users/pig30nidae/NUNTI/android/app/src/debug/kotlin/ai/nunti/app/generated/GeneratedCompanionActivity.kt:400), [서버 입력](/Users/pig30nidae/NUNTI/backend/nunti/characters/models.py:67)은 이름·설명·목적과 정규화된 점 목록만 받는다. 경로 이미지나 내비 출처 필드는 없다. | 첫 화면을 경로 불러오기로 바꾼다. 경로 스크린샷과 출처가 표시된 시험 경로를 먼저 제공하고 손그림은 보조 도구로 둔다. |
| 경로가 어떤 외형으로 옮겨졌는지 설명하지 않는다. | [기획 출력](/Users/pig30nidae/NUNTI/backend/nunti/characters/models.py:115)은 이름·성격·이미지 프롬프트·음성 설명·대사다. [최종 결과](/Users/pig30nidae/NUNTI/backend/nunti/characters/worker.py:239)에는 특징과 외형의 대응이 없다. 앱은 이름과 그림을 보여 준다. | 기획 결과에 입력 근거와 외형의 대응을 저장하고, 결과 옆에 실제 경로와 함께 보여 준다. 모델이 제안한 모티브와 실제 그림에서 확인한 특징을 구분한다. |
| 음성 시험과 부가 조작이 아바타의 설명보다 먼저 눈에 들어온다. | [상단 음성 시험 버튼](/Users/pig30nidae/NUNTI/android/app/src/debug/kotlin/ai/nunti/app/generated/GeneratedCompanionActivity.kt:451), [재생·도착·보관·추가 대사](/Users/pig30nidae/NUNTI/android/app/src/debug/kotlin/ai/nunti/app/generated/GeneratedCompanionActivity.kt:515)가 처음부터 같은 화면에 있다. | 아바타와 생성 근거를 먼저 배치한다. 음성은 접힌 영역에서 명시적으로 듣게 하고, 도착·보관·추가 대사는 후순위로 옮긴다. 기능과 저장 규칙은 보존한다. |
| 음성 공급자가 실패하면 이미지도 완료로 전달하지 않는다. | [작업자](/Users/pig30nidae/NUNTI/backend/nunti/characters/worker.py:119)는 기획·이미지 생성 전에 음성 슬롯을 예약한다. [초기 합성](/Users/pig30nidae/NUNTI/backend/nunti/characters/worker.py:231)에서 세 WAV를 만든 뒤 결과를 확정한다. [Android 파서](/Users/pig30nidae/NUNTI/android/app/src/debug/kotlin/ai/nunti/app/generated/GeneratedData.kt:68)도 세 clip을 필수로 요구한다. | 이미지 완료와 음성 완료를 분리하는 새 계약이 필요하다. UI만 접거나 키 검사만 없애는 변경으로는 해결되지 않는다. |
| 시험 미디어가 새 여정의 아바타처럼 느껴질 수 있다. | [샘플 기획](/Users/pig30nidae/NUNTI/backend/nunti/characters/providers.py:163)은 경로에서 생성하지 않은 기존 이미지와 Sohee 음원을 명시적으로 재사용한다. 앱의 [모드 설명](/Users/pig30nidae/NUNTI/android/app/src/debug/kotlin/ai/nunti/app/generated/GeneratedCompanionActivity.kt:457)은 제출 후 받은 모드를 사용한다. 초기값은 UNKNOWN이다. | 생성 버튼을 누르기 전부터 입력 출처와 결과 출처를 각각 표시한다. 샘플 결과에서는 개인화 생성 완료라고 말하지 않는다. |

경로와 이미지 생성의 연결이 전혀 없는 것은 아니다. [현재 이미지 어댑터](/Users/pig30nidae/NUNTI/backend/nunti/characters/providers.py:428)는 입력 점을 경로 안내 PNG로 만든다. 기본 조합은 이 그림과 스타일 기준 이미지를 이미지 모델에 함께 전달한다. 비교 조합도 경로 그림을 전달한다. [선정 단계](/Users/pig30nidae/NUNTI/backend/nunti/characters/providers.py:523)는 경로 그림과 후보를 함께 보지만, 모델의 상대적 평가이며 사람이 귀엽거나 소장하고 싶다고 평가한 결과는 아니다. 현재 탄생 애니메이션은 완성 그림을 경로에서 공개하는 연출이다. 그 연출 자체가 그림의 개인화를 증명하지는 않는다.

제안하는 첫 사용 흐름은 다음과 같다.

1. **경로 불러오기.** 내비 경로 스크린샷 또는 시험 경로 파일을 선택한다. 시험 파일은 사전에 준비한 입력 예시이며 고정 아바타 선택지가 아니다. 내비 SDK의 실시간 연결은 별도 미구현 항목으로 남긴다.
2. **이 여정 확인.** 목적지, 선택 경로, 목적을 한 카드에 보여 준다. 스크린샷에서 찾은 선을 원본 위에 표시하고 사용자가 확인한다. 경로를 못 찾으면 불확실한 결과를 확정하지 않고 다시 선택하거나 보조 입력으로 수정한다. 지도에서 도로·지형을 확인하지 못했다면 도로·지형은 UNKNOWN으로 유지한다.
3. **무엇이 외형이 되는지 보기.** 확인한 선의 굴곡은 꼬리, 목적지에 대해 사용자가 쓴 색감은 몸체의 빛처럼 대응을 보여 준다. 이는 창작 모티브의 예시이며 현재 결과에 그런 특징이 있다는 주장이 아니다. 대응에는 입력 출처, 근거가 되는 점 구간 또는 문구, 외형의 부위, 제안 또는 확인 상태를 함께 저장한다.
4. **내 여정 아바타 만나기.** 확인한 경로가 이어져 몸체가 되는 기존 연출을 사용한다. 생성된 아바타와 원래 경로를 함께 보여 주고 실제 반영 여부를 사용자가 판단할 수 있게 한다. 세계 전체의 유일성이나 UUID만으로 확인한 시각적 차별성을 보증하지 않는다.
5. **원할 때 목소리 듣기.** 음성이 준비되면 접힌 영역에서 듣는다. 음성이 아직 없거나 실패해도 완성된 아바타를 볼 수 있다. 준비·복원·대사 추가로 자동 발화하지 않는다.

경로 입력의 출처와 미디어의 출처는 다른 정보다. 예를 들어 시험 경로 파일을 넣고 실제 이미지 API로 새 그림을 만들 수도 있다. 따라서 `inputOrigin`은 내비 스크린샷·시험 파일·손그림을 구분하고, `mediaOrigin`은 실제 공급자 생성·기존 샘플 미디어를 구분해야 한다. 기존 샘플 이미지에는 개인화된 특징 설명을 새로 꾸며 붙이지 않는다.

| API 키에 대한 구분 | 현재 구현 사실 | 재설계에서의 최소 조건 |
|---|---|---|
| 기본 전체 생성 | [ApiPipeline 초기화](/Users/pig30nidae/NUNTI/backend/nunti/characters/providers.py:235)는 OpenAI·ElevenLabs·Google 키를 모두 요구한다. [설정 안내](/Users/pig30nidae/NUNTI/docs/design/generative-mvp/API-SETUP.ko.md:3)의 세 키 설명은 현 코드에는 맞다. | 제품의 필수 조건으로 일반화하지 않는다. 이미지 중심 경로를 새로 구현해야 줄일 수 있다. |
| 아바타 이미지 생성 | 코드상 OpenAI 키 하나가 기획 모델과 이미지 모델 양쪽에 사용된다. 현재 이미지 어댑터는 로컬 스타일 기준 PNG도 요구한다. | 같은 공급자에서 기획·이미지 입력·생성을 처리하거나 기획 일부를 로컬 규칙으로 처리한다면 이미지 공급자 한 곳의 키로 시작할 수 있다. 실제 계정 권한과 품질은 별도 검증 대상이다. |
| 자동 후보 비교 | 현재 Gemini 비교는 필수이며 가격 상한 검사에도 포함된다. | Google 비교를 선택 기능으로 바꿀 수 있다. 생략 시 파일·알파·해시·크기 검사와 사람의 품질 평가는 유지하고 자동 품질 평가 완료라고 보고하지 않는다. |
| 캐릭터별 새 음색 | 기본 조합은 ElevenLabs 설계·보관·합성이 필수다. | 캐릭터별 음성을 요청할 때 해당 공급자의 키와 슬롯이 필요하다. 이미지 단계를 열기 위해 반드시 있어야 하는 조건에서는 분리한다. |
| 키 없는 시험 | 기존 이미지·음원을 재사용하는 OFFLINE_FIXTURE다. | 입력·연출·저장·정책 시험용으로 유지한다. 새 AI 이미지·음색 생성으로 소개하지 않는다. |

이 표는 현재 저장소의 호출과 설계를 설명한다. 모델의 최신 제공 여부·가격·실제 품질을 이번 감사에서 재조사하거나 검증하지 않았다.

계약 변경은 기존 소장품을 보존하는 방식으로 해야 한다. 현재 v2는 음성과 세 clip을 필수로 하고 서버의 Strict 모델은 추가 필드도 거절하므로, 기존 계약을 그대로 둔 채 화면만 바꿀 수는 없다. 새로운 계약에서 입력 원본의 해시, 확인한 정규화 경로, 특징과 외형의 대응, 변경하지 않는 이미지 결과를 한 번 확정한다. 음성은 미요청·준비 중·준비 완료·실패 상태를 분리한다. 준비가 끝난 음성 바인딩은 이후 바꾸지 않는다. 기존 v2 결과와 manifest3 파서는 그대로 지원하며 새 결과를 읽는 경계를 명시한다.

유지할 불변 조건은 다음과 같다.

- 같은 요청의 재시도·복원은 같은 입력·그림·아바타를 사용한다. 재시도로 새 유료 생성을 자동 실행하지 않는다.
- 확정 PNG·원본 음원·정규화 WAV·SHA·음성 바인딩을 보존한다. 음성 실패 때문에 확정 그림을 재생성하지 않는다.
- 저장된 음성을 붙이거나 대사를 추가할 때 기존 이미지·CharacterSpec·voiceId를 교체하지 않는다. 기존 catalog의 확장과 같은 queue의 반복 억제·취소 이력을 유지한다.
- 주차·화면 사용 허가·foreground·음성 허가를 유지한다. 수집 UI를 옮겨도 이미 보관한 동반자는 계속 복원할 수 있어야 한다.
- 스크린샷 입력을 추가해도 정밀 주소·GPS 원문을 생성 프롬프트에 자동으로 포함하지 않는 제품 원칙을 유지한다. 사용자에게 확인한 경로와 필요한 창작 정보만 생성 재료로 사용한다.

차량 연결은 전부 없는 상태가 아니다. 현재 생성 화면은 [실제 차량 gate](/Users/pig30nidae/NUNTI/android/app/src/debug/kotlin/ai/nunti/app/journey/JourneyCarGate.kt:28)에서 CarUxRestrictions와 기어·속도를 읽고 [표시 허가](/Users/pig30nidae/NUNTI/android/app/src/debug/kotlin/ai/nunti/app/generated/GeneratedCompanionActivity.kt:132)를 제한한다. 다만 이 연결은 주차 중 시험 화면의 표시 경계다. 실제 내비 경로를 받아 아바타의 생성 재료로 쓰는 연결이나 주행 중 제품 경험의 완성을 뜻하지 않는다. 공모전 설명에서는 이 차이를 밝히고 내비 입력과 차량 안에서 얻는 경험을 우선 확인해야 한다.

제출 앱과 시험 앱도 다르다. [기본 리소스](/Users/pig30nidae/NUNTI/android/app/src/main/res/values/journey_mvp.xml:1)는 생성 화면 진입을 false로 두고 [debug 리소스](/Users/pig30nidae/NUNTI/android/app/src/debug/res/values/journey_mvp.xml:1)만 true로 바꾼다. 생성 Activity와 인터넷·차량 권한은 [debug manifest](/Users/pig30nidae/NUNTI/android/app/src/debug/AndroidManifest.xml:2)에만 있다. 소스상 release의 [MainActivity](/Users/pig30nidae/NUNTI/android/app/src/main/kotlin/ai/nunti/app/MainActivity.kt:32)는 차량에서는 빈 화면으로 차단하고 일반 Android에서는 이전 Mock을 연다. 따라서 현재 release APK를 새 생성 MVP의 제출물로 설명할 수 없다. release APK를 제출할 단계에는 새 production host·서버 접속·권한·차량 정책·서명·실행 검증을 별도 작업으로 해야 한다. 이번 감사에서 APK 바이너리를 재검사하거나 제출하지 않았다.

문서의 시작점도 하나로 맞춰야 한다. [pm.md](/Users/pig30nidae/NUNTI/docs/handoff/prompts/pm.md:3)와 [현황](/Users/pig30nidae/NUNTI/docs/handoff/STATUS.md:7)은 생성 동반자 v2를 최신으로 안내하지만, [제품 브리프 첫 문단](/Users/pig30nidae/NUNTI/docs/product/journey-character-brief.md:3)은 아직 이전 72점 외형·로컬 Sohee 시험본을 최신으로 소개한다. 과거 증거는 보존하되 브리프 첫 문단은 현재 경로 기반 생성 목적과 실제 완료 범위로 고쳐야 한다.

현재 완료된 것은 손그림 입력, 경로 그림을 전달하는 이미지 API 어댑터, 완성 RGBA의 탄생 연출, 샘플 미디어의 음성·보관·복원 연결이다. 경로 스크린샷 불러오기, 내비 경로 입력, 입력 근거와 외형의 대응, 이미지 단독 완료 계약은 미구현이다. 실제 공급자로 만든 새 그림·새 음색의 품질·비용·지연과 사용자의 귀여움·소장 의향은 미검증이다. 이 구분을 첫 화면과 시험 안내에서도 그대로 사용해야 한다.

이번 턴에는 공모전의 목표와 제공 기술, Nunti가 맡을 경험을 먼저 확정한다. 위 입력·화면·계약 재설계는 그 결과에 맞춰 판단하며 앱이나 서버 코드 변경은 보류한다.
