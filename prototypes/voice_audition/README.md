# Nunti 목소리 듣기

현재 선호 음성은 ElevenLabs Anna Kim이다. 사용자는 실제 상용 원음 비교에서 "Anna가 가장 가까움"이라고 답했다. "지금은 계정 없이 진행" 결정에 따라 공식 데모와 로컬 청취를 사용한다. 정확한 API 모델·설정과 제품 연결은 미검증이다.

## 지금 테스트하기

[최신 청취 페이지](round2-listen.html)를 연 뒤 Anna의 새 여행 대사를 재생한다. macOS에서는 다음 명령을 실행한다.

```sh
open /Users/pig30nidae/NUNTI/prototypes/voice_audition/round2-listen.html
```

계정·서버·모델 설치 없이 저장된 MP3와 WAV를 듣는다. 출발·동행·도착을 이어 읽은 Anna 새 대사와 정확히 같은 원문의 Sohee 두 버전을 비교한다. Sohee는 기존 한국어 프리셋으로 로컬에서 새로 합성했으며 Anna 음원을 참조·학습 입력으로 사용하지 않았다. 이전 Anna·Stella 비교 원음도 있다. 원음 음량·속도 차이는 남아 있다.

이 페이지는 새 문장을 자동 합성하지 않는다. 직접 다른 문장을 시험하려면 [ElevenLabs 한국어 공식 데모](https://elevenlabs.io/text-to-speech/korean)에서 Anna Kim을 선택하고 원문을 입력해 재생한다. 공개 데모의 제공 범위는 서비스 상태에 따른다.

## 결과와 남은 범위

[selected-voice.json](selected-voice.json)은 Anna 선호와 계정 연결 보류를 기록한다. Android나 과거 캐릭터의 음성 바인딩을 바꾸는 설정 파일은 아니다. 정확한 사용자 응답과 해당 오디오 해시는 [user-feedback.json](user-feedback.json)에 있다.

기존 Supertonic3 v2와 Qwen VoiceDesign→Base 후속 대사는 사용자 청취에서 탈락했다. 이전 Qwen A가 Chatterbox B보다 자연스럽다는 답변은 상대 비교 기록으로만 남긴다. [이전 두 엔진 비교](listen.html)와 [Qwen 후속 대사](../journey_voice_v3/identity/listen.html)는 과거 실험이다.

[공식 원음 기록](commercial/README.md)은 다운로드 경로·원문·모델 미노출과 이용 범위를 설명한다. [PM 선정 보고](../../docs/design/journey-characters/tts-model-selection.md)는 공급자 조사와 미검증 항목을 취합한다. API 연결을 재개할 때는 [준비 도구](../elevenlabs_voice/README.md)를 따른다.

## 파일 확인하기

다음 명령은 네트워크와 모델 추론 없이 최신 청취 파일과 기록의 정합성을 검사한다.

```sh
python3 prototypes/voice_audition/verify_round2.py
```

[독립 ASR](asr/README.md)은 오독·누락 후보를 찾는 보조 검사다. 파일 검증과 자동 전사는 자연스러움·귀여움·운전습관 개선을 증명하지 않는다. Anna의 매 여행 자동 합성·새 모델의 Android 연결·장기 청취 평가는 남아 있다.
