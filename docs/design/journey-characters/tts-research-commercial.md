# NUNTI 상용 TTS 후보 조사

조회일은 2026-11-02 KST다. 공식 모델 문서, API 문서, 가격, 이용 조건을 확인했다. 계정 생성, 유료 호출, 녹음 업로드, 음성 다운로드는 하지 않았다. 이 문서는 공급자 선정 자료이며 동일 한국어 문장으로 실시한 청취 평가 결과가 아니다.

## 우선 비교할 세 후보

**한국어 캐스팅은 Typecast SSFM 3.1, 여행마다 새 목소리를 설계하는 기능은 ElevenLabs와 Inworld를 우선 비교한다.** 이 순서는 기능과 접근성에 따른 PM 판단이다. 한국어 자연스러움이나 귀여움의 실측 순위는 아직 없다. 특히 음높이만 올린 기존 방식의 다음 대안은 목소리의 공명, 말의 리듬, 문장 끝 처리, 감정을 합성 단계에서 함께 바꾸는 것이다.

| 후보 | 실제 모델 ID | NUNTI에서 확인할 가치 | 아직 증명하지 못한 점 |
| --- | --- | --- | --- |
| Typecast | `ssfm-v31`, 비교 기준 `ssfm-v30` | 한국어 캐릭터 보이스를 먼저 고른 뒤 약한 감정 연출을 비교할 수 있다. | 공개 API에서 텍스트 설명만으로 매번 새 화자를 만드는 기능은 확인하지 못했다. |
| ElevenLabs | `eleven_v4`, `eleven_v4_turbo`, 비교 기준 `eleven_v3`; Voice Design은 `eleven_ttv_v3` | 새 화자를 설명으로 만들고 저장한 뒤 재사용하는 흐름이 있다. | 설계한 목소리의 한국어 발음, 귀여움, v4와 v3의 실제 차이. |
| Inworld | `inworld-tts-2`; 지연 비교만 `inworld-tts-2-flash` | Voice Design, 저장한 `voiceId`, 영어 연기 지시를 한국어 대사에 적용하는 흐름이 있다. | 한국어 설계 화자의 품질과 재사용 시 인상 유지. Flash는 연기 지시를 지원하지 않는다. |

Typecast는 2026년 10월 공개한 `ssfm-v31`을 권장하며, 입력 충실도와 생성 안정성을 개선했다고 설명한다. 한국어와 SSFM 3.0의 Smart Emotion, 일곱 감정 프리셋을 유지한다. 따라서 v3.0만 평가 대상으로 고정하면 현행 후보를 놓친다. [Typecast 모델 문서](https://typecast.ai/docs/models)

ElevenLabs 현행 문서에는 v3보다 새 모델인 v4와 v4 Turbo가 있으며 한국어 `ko`를 지원한다. 모델의 표현력 우위는 공급자의 설명이다. [ElevenLabs 모델 문서](https://elevenlabs.io/docs/overview/models)

Inworld는 한국어 `ko-KR`를 핵심 지원 언어 목록에 둔다. [Inworld 언어 지원](https://docs.inworld.ai/tts/capabilities/multilingual)

## Typecast SSFM 3.1

- 합성 경로는 `GET /v3/voices?model=ssfm-v31`에서 호환 `voice_id`를 고른 뒤 `POST https://api.typecast.ai/v1/text-to-speech`다. `X-API-KEY`가 필요하다. 한국어는 `language: "kor"`다. 최초 비교는 `audio_pitch: 0`, `audio_tempo: 1`로 두고 `normal`, 강도 낮은 `happy`, `smart`를 비교한다. 출력은 44.1 kHz, 16-bit, mono WAV를 요청할 수 있다. [합성 API](https://typecast.ai/docs/api-reference/text-to-speech/text-to-speech)
- 보이스 목록은 나이와 모델을 필터링하고, 각 화자의 지원 모델과 감정, 미리듣기 주소를 반환한다. 작은 아바타라는 이유만으로 아동 음성을 고정하지 말고 가벼운 성인 음색도 함께 캐스팅한다. 이 캐스팅 제안은 NUNTI의 판단이다. [보이스 목록 API](https://typecast.ai/docs/api-reference/voices/list-voices)
- API 소개 페이지의 스트리밍 TTFB는 170~210 ms라는 공급자 수치다. NUNTI 앱에서 측정한 지연이 아니다. 페이지에는 한국어 Smart Emotion 공개 비교 데모가 있다. [API 소개와 공개 데모](https://typecast.ai/kr/developers/api/)
- 현재 무료 API는 월 15,000 크레딧, 동시 호출 2다. 무료 출력은 상업 이용 불가이며 공개 시 출처가 필요하다. Lite는 월 $15에 200,000자, 동시 호출 5, 커스텀 보이스 슬롯 50개다. 초과분은 $0.09/1,000자이고 $9 단위로 자동 결제된다. 스튜디오와 API 구독은 별개다. 과거 블로그의 30,000 무료 크레딧 대신 현재 가격 페이지를 기준으로 기록했다. [API 가격](https://typecast.ai/kr/pricing/api/)
- API 약관은 조건을 지킨 상업 앱 개발과 운영을 허용한다. 출력의 배타적 독창성은 보장하지 않는다. 클로닝은 사용 목적을 명시한 검증 가능한 동의가 필요하다. [Typecast API 약관, 2026-08-25](https://help.typecast.ai/ko/articles/11872662-%ED%83%80%EC%9E%85%EC%BA%90%EC%8A%A4%ED%8A%B8-api-%EC%84%9C%EB%B9%84%EC%8A%A4-%EC%9D%B4%EC%9A%A9-%EC%95%BD%EA%B4%80)

## ElevenLabs v4와 Voice Design

- Voice Design은 설명으로 세 후보를 만들고 선택한 화자를 슬롯에 저장한다. 전용 녹음 없이 시작할 수 있다. 공식 문서도 결과 편차가 있으며, 제작용 일관성은 Professional Voice Clone이 더 높다고 설명한다. [Voice Design 가이드](https://elevenlabs.io/docs/eleven-creative/voices/voice-design)
- 설계 API의 `model_id`는 `eleven_ttv_v3` 또는 `eleven_multilingual_ttv_v2`다. `seed`를 보존할 수 있다. 높은 `guidance_scale`은 인공적이거나 로봇 같은 결과를 낼 수 있다는 공식 주의가 있어, 기본값 5에서 시작하고 무리하게 올리지 않는다. 설계용 미리듣기 대사는 100~1,000자여야 하므로 아래의 짧은 공통 대사는 저장한 화자의 후속 합성에서 사용한다. [Voice Design API](https://elevenlabs.io/docs/api-reference/text-to-voice/design)
- Voice Design 목소리는 v4와 v3에서 쓸 수 있지만, 공식 도움말은 v4에서 이전 모델보다 덜 연기적으로 들릴 수 있다고 명시한다. 따라서 같은 저장 화자로 v4와 v3를 모두 듣는다. [Voice Design 호환성과 한계](https://elevenlabs.io/docs/help-center/product/voices/voice-design/what-is-voice-design)
- v4 공식 제품 페이지에는 `textToSpeech.convert`에 `modelId: "eleven_v4"`를 전달하는 예제가 있다. 실제 계정에서는 먼저 `GET /v1/models`의 `can_do_text_to_speech`와 모델 접근성을 확인해야 한다. 일반 모델 문서에는 v4의 Text to Dialogue 경로도 소개되어 있어 엔드포인트를 추정으로 고정하지 않는다. [v4 API 예제](https://elevenlabs.io/v4), [Create speech API](https://elevenlabs.io/docs/api-reference/text-to-speech/convert)
- 같은 제품 페이지의 v4 Turbo 지연은 중앙값 약 100 ms 추론, 약 150 ms first speech다. 공급자의 측정이며 한국어 차량 환경 수치가 아니다. [v4 Turbo 제품 설명](https://elevenlabs.io/v4)
- 현재 API 표시는 v4와 v3 $0.08/1,000자, v4 Turbo와 v3 Conversational $0.04/1,000자다. Starter는 월 $6다. 세금, 음성별 추가 조건, 요금제별 출력 포맷을 계약 시 확인한다. [ElevenAPI 가격](https://elevenlabs.io/pricing/api)
- 무료 출력은 상업용으로 쓸 수 없다. 유료 플랜도 Beta Services 출력의 상업 이용과 운영 환경 사용은 허용하지 않는다. Voice Design이 문서에서 experimental로 기술되므로 선택한 계정 기능에 Beta Services 조건이 적용되는지 확인해야 한다. 이를 무료로 생성한 뒤 유료로 전환하면 해결된다고 가정하지 않는다. [상업 이용과 Beta 제한](https://elevenlabs.io/docs/help-center/legal/can-i-publish-the-content-i-generate-on-the-platform)
- 한국어 공개 페이지에 직접 대사를 입력하는 UI와 한국어 화자 미리듣기가 있다. 페이지의 출력이 정확히 어떤 모델과 설정인지 저장하지 않으면 공식 데모 감상으로만 기록한다. [한국어 공개 데모](https://elevenlabs.io/text-to-speech/korean)

## Inworld Realtime TTS-2

- 공식 모델 표의 TTFB는 TTS-2 100 ms, Flash 20 ms다. P90 서버 측 측정이며 네트워크를 제외한다. 구형 TTS-1 계열은 신규 프로젝트에 권장되지 않는다. [Inworld 모델 문서](https://docs.inworld.ai/tts/tts-models)
- 저장용 Voice Design은 영어 설명과 대사로 최대 세 미리듣기를 만들고 선택한 화자를 라이브러리에 발행한다. 이후 반환된 `voiceId`를 재사용한다. 반면 ad-hoc `voiceDesign.designPrompt`는 Preview 기능이며 같은 설명을 반복해도 같은 화자를 보장하지 않는다. NUNTI의 여행 캐릭터에는 저장한 화자를 사용해야 한다. [Voice Design과 저장 API 안내](https://docs.inworld.ai/tts/voice-design)
- TTS-2는 한국어 대사 앞에 `[warm and gently playful]` 같은 영어 연기 지시를 붙일 수 있다. Flash는 이런 지시를 무시하므로 낮은 가격만 보고 대신 선택하면 요구가 달라진다. [Steering 문서](https://docs.inworld.ai/tts/capabilities/steering)
- 같은 문장 합성 경로는 `POST https://api.inworld.ai/tts/v1/voice`, `Authorization: Basic $INWORLD_API_KEY`, `modelId: "inworld-tts-2"`, 저장한 `voiceId`, `text`다. 공식 설계 페이지에 이 엔드포인트의 요청 예제가 있다. [요청 예제](https://docs.inworld.ai/tts/voice-design)
- On-Demand는 TTS-2 $25/100만자, Flash $15/100만자이며 상업 라이선스를 포함한다고 표시한다. 계정당 100 custom voices, 최대 70분 TTS 포함도 표시한다. 무료 계정의 실제 잔액과 다운로드 조건은 로그인 후 확인해야 한다. Creator는 월 $25이며 TTS-2 $20/100만자다. [가격과 기능](https://inworld.ai/pricing)
- 공개 제품 페이지에 설계 화자, 연기 변화, Korean T1 선택 데모가 있다. 한국어 데모의 잘 들리는 정도가 NUNTI의 같은 대사 결과를 증명하지는 않는다. [공개 데모](https://inworld.ai/tts)

## 예비 후보와 제외 이유

Cartesia는 `sonic-3.6`과 고정 스냅샷 `sonic-3.6-2026-08-27`에서 한국어를 지원한다. 업데이트에 따른 캐릭터 변화가 걱정되면 날짜 모델이 유리하다. [Sonic 3.6 모델 문서](https://docs.cartesia.ai/build-with-cartesia/tts-models/latest)

다만 명시적 감정 태그는 Beta이며 영어에만 지원된다고 문서에 적혀 있다. 한국어의 문맥 기반 자연스러움은 별도 청취 대상이지만, 한국어 캐릭터 연출 제어를 확인한 후보와 동등하게 취급하지 않는다. [속도와 감정 제어](https://docs.cartesia.ai/build-with-cartesia/capability-guides/volume-speed-emotion)

무료 월 20,000 크레딧, Pro 월 $5에 100,000 크레딧이며 Pro에 상업 라이선스가 포함된다. [Cartesia 가격](https://www.cartesia.ai/pricing)

한국어 페이지는 가입 없이 직접 대사를 입력하고 듣는 경로를 제공한다. API는 `POST https://api.cartesia.ai/tts/bytes`, `Cartesia-Version: 2026-08-14`, `model_id`, 선택한 한국어 `voice`, `language: "ko"`, `transcript`를 받는다. 이번 조사에서는 호출하지 않았다. [한국어 공개 데모](https://www.cartesia.ai/languages/korean), [Bytes API](https://docs.cartesia.ai/api-reference/tts/bytes)

Supertone Play, API, Voice Builder는 공식 고객지원 종료 공지상 2026-08-31 종료다. 예전 Play 요금 페이지가 검색되어도 신규 공급자로 선정하지 않는다. 공식 주소의 현재 홈페이지는 Antinode Audio로 이동하며 Clear, Air, Shift의 제품 이관을 안내한다. 이 사실은 기존에 받은 Supertonic 오픈 가중치의 로컬 실행 가능 여부와 별개다. [API 종료 공지](https://support.supertone.ai/hc/ko/articles/16535451024271-API-%EC%8B%9C%EC%9E%91%ED%95%98%EA%B8%B0-%EC%97%B0%EB%8F%99-%EB%B0%A9%EB%B2%95-%EA%B2%B0%EC%A0%9C-%ED%8A%B8%EB%9F%AC%EB%B8%94%EC%8A%88%ED%8C%85-%EA%B0%80%EC%9D%B4%EB%93%9C), [Play와 Voice Builder 종료 환불 공지](https://support.supertone.ai/hc/ko/articles/16535018342543-%EA%B2%B0%EC%A0%9C-%ED%99%98%EB%B6%88-%EC%95%88%EB%82%B4-%ED%99%98%EB%B6%88-%EC%A0%95%EC%B1%85-%EC%9D%B8%EB%B3%B4%EC%9D%B4%EC%8A%A4-%ED%99%95%EC%9D%B8-%EA%B5%AC%EB%8F%85-%EC%B7%A8%EC%86%8C), [공식 도메인의 현재 홈페이지](https://www.supertone.ai/)

Hume Octave 2는 한국어를 지원하지만 공식 문서는 TTS와 EVI API가 **2026-11-13 00:01 EST에 종료**되고 이후 계정 데이터가 영구 삭제된다고 안내한다. 한국어 새 제품의 공급자로 선정하지 않는다. [Hume TTS 공식 종료 고지](https://dev.hume.ai/voice/docs/text-to-speech-tts/overview)

## 같은 대사로 확인해야 할 것

아래 문장은 NUNTI 평가용으로 작성했다. 사용자 경로, 목적지, 개인정보를 포함하지 않는다. 계정 접근과 비용 조건이 확보된 뒤 동일 원문을 보낸다. 태그를 사용하는 결과에는 원문과 별도로 연기 지시도 남긴다.

1. "안녕하세요. 오늘의 여행도 함께할게요."
2. "안녕, 나는 파도빛이야. 오늘은 바닷바람을 만나러 가자."
3. "와, 방금 출발이 정말 부드러웠어. 나도 마음이 편안해졌어."
4. "괜찮아. 다음에는 조금 더 천천히 멈춰 보자."
5. "오늘 함께 달린 길, 오래 기억하고 싶어."

제안 캐스팅 설명은 다음과 같다. 이는 효과가 검증된 프롬프트가 아니다.

> Native Korean, standard Korean. A small, friendly, non-human glass keepsake companion with a light young-adult voice. Warm, softly rounded resonance and a small smile. Natural conversational rhythm, gentle playful inflections, clear Korean consonants, and short relaxed phrase endings. Quiet confidence rather than a presenter delivery. Clean dry studio recording.

평가에서는 최초 원음과 약한 연기만 비교한다. 기존의 +3반음 DSP를 기본으로 재사용하지 않는다. 이 변경은 기계적으로 들린다는 사용자 피드백을 해결하기 위한 가설이며, 피치 보정이 원인의 전부라고 확정한 것은 아니다.

각 후보에서 최소 두 화자, 두 연기를 만들고 모델명 대신 무작위 번호로 듣는다. 원어민 평가는 자연스러움, 귀여움, 소장 캐릭터와의 어울림, 문장 정확도, 반복 청취 피로, 같은 캐릭터로 들리는지를 각각 기록한다. 안전한 안내 문장과 칭찬 문장을 모두 사용한다. 홍보용 샘플이나 영어 벤치마크 점수만으로 한국어 최종 공급자를 결정하지 않는다.

여행 생성 시 선택한 화자를 캐릭터에 고정하고 공급자, 모델, voice ID, 설계 설명, 원문, 연기 지시, 원음 해시를 함께 보존한다. 새 요청마다 같은 설명으로 화자를 다시 설계하면 수집한 캐릭터의 목소리가 바뀔 수 있다. 저장 슬롯 한도와 서비스 종료 가능성도 장기 보관 설계에서 확인해야 한다.

완료한 범위는 공식 자료 조사와 합성 경로 확인이다. 미검증 범위는 상용 후보의 동일 대사 실합성, 한국어 블라인드 청취, 실제 NUNTI 지연, 선택한 기능의 계정별 상업 이용 조건이다.
