# 공식 상용 데모 원음 확보 기록

확인일은 2026-11-02다. PM이 [ElevenLabs 한국어 공식 데모](https://elevenlabs.io/text-to-speech/korean)에서 가입·API 키 없이 아래 대사를 입력했다. Anna Kim과 Stella를 각각 선택해 생성한 뒤, 공식 **Download generated speech** 버튼으로 Downloads에 저장하고 이 폴더로 복사했다. 원본 MP3를 변환하거나 피치·속도·음량을 조정하지 않았다.

> 안녕하세요. 오늘의 여행도 함께할게요. 와, 도착했다! 여기서 어떤 기억을 만나게 될까?

사용자는 두 원음을 듣고 "Anna가 가장 가까움"이라고 선택했다. Anna를 현재 캐스팅 기준으로 삼는다. 이어 "지금은 계정 없이 진행"을 선택해 API 연결은 보류했다.

공개 UI가 정확한 합성 모델 ID를 표시하지 않아 원본 메타데이터의 `modelId`는 `null`이다. 페이지의 모델 홍보 배너만 보고 `eleven_v4` 또는 `eleven_v3`로 이름 붙이지 않는다. 정확한 API 모델 재현과 NUNTI 제품 이용 권한 확인은 남아 있다. 최초 원본 메타데이터는 수신 당시 기록으로 보존하고, 이후 사용자 평가는 [피드백 기록](../user-feedback.json)에 덧붙인다.

| 공개 화자 이름 | 받은 원음 | 실제 파일 크기 | MP3 SHA-256 |
| --- | --- | ---: | --- |
| Anna Kim - Tender, Calm and Clear | [Anna Kim 원음](elevenlabs-anna-common-arrival.mp3) | 119,580 bytes | `5b7d8821b2d714789a54c0de0ba4005d373beb7871094e64051d752ceca649fb` |
| Stella - Steady, Clear and Cheerful | [Stella 원음](elevenlabs-stella-common-arrival.mp3) | 119,580 bytes | `77052532dd52b1a6539d660dc1a516ec998d6a06144a8c0d0e2611777718dc4b` |

[Anna Kim 메타데이터](elevenlabs-anna-common-arrival.json)와 [Stella 메타데이터](elevenlabs-stella-common-arrival.json)에 원문, 텍스트 해시, 접근 방법과 원본 오디오 해시를 보존한다. 두 파일은 길이가 약 7.47초로 같지만 원본 해시는 다르다. [디코딩 비교](decoded-comparison.json)에서도 PCM이 다르고 파형 상관은 약 0.033이다. 이는 두 파일이 같은 바이트·같은 파형이 아님을 보일 뿐, 목소리의 인상이나 자연스러움 순위를 판정하지 않는다.

Stella의 공개 UI에서 선택한 radio input 값은 `1YzIw7PZ7iaD4alelyHY`였다. [UI 화자 값 기록](stella-public-voice-id.json)은 이 관측만 보존한다. API의 화자 ID로 실제 호출할 수 있는지와 정확한 합성 모델은 확인하지 않았다.

Anna의 공개 UI 값은 `uyVNoMrnUku1dZyVEXwD`다. [Anna UI 값 기록](anna-public-voice-id.json)과 [현재 선호 기록](../selected-voice.json)을 함께 보존한다.

## Anna의 새 여행 대사

같은 공식 데모에서 Anna를 선택한 채 아래 대사를 새로 생성하고 공식 다운로드 버튼으로 저장했다. 가입·API 키·유료 합성 호출은 없었다.

> 오늘은 바다 보러 가는 날이네. 같이 예쁜 기억을 모아보자. 천천히 가도 괜찮아. 나는 네 옆에 있을게. 와, 도착했다! 오늘 만난 풍경은 내가 간직할게.

[새 여행 원음](elevenlabs-anna-journey.mp3)은 204,008 bytes, 약 12.75초다. SHA-256은 `f78fb59a40136d204fcc48fda44a5428fcffaa4a6805ba2cd70868cb2b6107be`다. [메타데이터](elevenlabs-anna-journey.json)와 [생성 화면](../evidence/anna-journey-demo.png)을 보존했다. 새 대사의 사람 청취 평가는 기존 Anna 선택과 구분한다. 실제 차량·매 여행 자동 생성·정확한 API 모델 재현은 이번 파일로 검증하지 않았다.

[새 대사 전사·PCM 점검](../asr/anna-journey-summary.md)은 CER 0%와 마지막 구절의 전사를 확인했다. 자동 전사가 실제 끝 잘림이나 사람 청취 품질을 보장하지는 않는다.

## 비교 조건과 남은 평가

[두 번째 청취 페이지](../round2-listen.html)는 상용 원음 두 개와 [Qwen CustomVoice Sohee](../../qwen_sohee_audition/README.md)의 가벼운 미소 연기 두 문장을 함께 제공한다. 상용 원음은 두 문장을 이어 읽었고 Sohee는 각각 독립 합성했다. 원문은 같아도 앞뒤 맥락과 문장 연결 조건이 다르다. 음량도 원본 그대로여서 서로 차이가 있다.

이전 Qwen VoiceDesign의 A가 B보다 자연스럽다는 상대 선호는 최종 채택을 의미하지 않았다. 사용자는 이후 같은 A 레퍼런스를 쓴 Qwen Base 두 문장에 "자연스럽지 않음. 마치 Grok을 듣는듯한 느낌이 남."이라고 답했다. 해당 후보는 채택하지 않았다. Sohee의 개별 청취 평가는 아직 없다. [사용자 응답 기록](../user-feedback.json)은 별도로 보존한다.

독립 ASR 결과는 [Anna Kim을 포함한 2차 전사](../asr/round2-summary.md), [Stella 전사](../asr/stella-summary.md)에 있다. 자동 전사는 자연스러움·귀여움·화자 동일성을 증명하지 않는다.

## Typecast 공개 미리듣기

PM은 [Typecast 한국어 홈](https://typecast.ai/kr/)의 주하 목소리에 사용자 정의 대사를 넣어 재생을 세 번 실행했다. 페이지 리소스에 당일 생성된 TTS WAV 세 개가 나타나는 것을 관측했다. 저장·다운로드의 로그인 조건을 존중해 음원 주소로 파일을 추출하거나 녹음하지 않았다. 따라서 이 폴더에 Typecast 원음은 없다.

Typecast의 [공식 비로그인 기능 안내](https://typecast.ai/kr/learn/ai-voice-service-login-free-comparison/)는 홈에서 문장을 바꾸는 미리듣기와 로그인 후의 제작·저장·다운로드를 구분한다. 현재는 공식 페이지 링크로만 미리듣기를 제공한다. 이 데모의 정확한 모델 ID와 API 화자 ID도 확인하지 않았다.

## 사용 범위

이 파일은 음질을 비교하기 위해 공식 데모에서 받은 원음이다. 다운로드 성공은 제품 배포나 상업 이용 권한의 확인을 대신하지 않는다. ElevenLabs 공식 안내는 무료·비로그인 출력의 상업 이용을 허용하지 않으며, 비상업적 공개 시 출처 표기를 요구한다. 선택한 목소리를 제품에 연결하려면 해당 유료 플랜과 서비스별 조건을 확인해야 한다. [ElevenLabs 상업 이용 안내](https://elevenlabs.io/docs/help-center/legal/can-i-publish-the-content-i-generate-on-the-platform)

추가로 [이용약관 1(c)·4(a)](https://elevenlabs.io/terms-of-use)와 [금지정책 12](https://elevenlabs.io/use-policy)를 확인했다. 다운로드한 출력의 외부 사용도 약관·정책의 적용을 받으며, 별도 허용 없는 AI 모델·서비스 개발에 대한 제한이 있다. 내부 Android 개발 시험에 이 원음을 넣는 행위의 허용 범위는 확인하지 못했다. 이는 문서 범위에 대한 판단이며, 모든 내부 재생이 금지됐다는 법률 결론은 아니다. Anna는 청취 기준으로 보존하고 앱 자산·복제 참조·학습 데이터에는 추가하지 않았다. [코드 경계와 조사 결과](../evidence/android-integration-assessment.json)를 따른다.

청취 페이지에는 ElevenLabs 출처를 표시한다. HTML은 로컬 오디오 파일을 참조하며 외부 스크립트·자동 재생·서버·업로드를 사용하지 않는다.
