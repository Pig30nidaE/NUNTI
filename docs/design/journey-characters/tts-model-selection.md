# 자연스러운 아바타 목소리의 모델 선정

현재 캐스팅 기준은 **ElevenLabs Anna Kim**이다. 실제 공개 데모 MP3 두 개를 들은 사용자가 "Anna가 가장 가까움"이라고 선택했다. 공개 UI의 화자 ID는 `uyVNoMrnUku1dZyVEXwD`다. 정확한 합성 모델·설정은 공개 데모에 노출되지 않아 API 모델 선정은 미완료다. Qwen VoiceDesign→Base는 후속 대사가 부자연스럽다는 평가로 탈락했으며, 앞선 A>B 응답을 품질 승인으로 확대하지 않는다.

2026-11-02 PM 기록. 사용자는 "지금은 계정 없이 진행"을 선택했다. API 연결을 보류하고, Anna 공개 데모 원음과 로컬 청취를 사용한다. [API 준비 도구](../../../prototypes/elevenlabs_voice/README.md)는 오프라인 예제만 작성했으며 실제 API 합성은 하지 않았다.

## 먼저 듣기

- [상용 원음과 한국어 원어 프리셋의 새 비교](../../../prototypes/voice_audition/round2-listen.html)
- [선택한 Anna 원본 MP3](../../../prototypes/voice_audition/commercial/elevenlabs-anna-common-arrival.mp3)
- [Anna의 새 여행 대사 MP3](../../../prototypes/voice_audition/commercial/elevenlabs-anna-journey.mp3)
- [탈락한 Qwen A의 고정 참조 후속 대사](../../../prototypes/journey_voice_v3/identity/listen.html)
- [두 엔진·다섯 캐스팅의 동일 대사 비교](../../../prototypes/voice_audition/listen.html)
- [Qwen의 세 스타일 원음](../../../prototypes/journey_voice_v3/listen.html)

이전 v2의 단순 피치 후처리를 새 후보에 적용하지 않았다. 부드럽고 둥근 음색, 자연스러운 한국어 대화, 작은 미소, 절제된 연기를 합성 단계에서 요청했다. 높이만 올리거나 아기 흉내를 내는 방향으로 귀여움을 정의하지 않는다. 실제 음향 효과와 귀여움은 청취로 판단한다.

## 계정 없이 확인한 현재 결과

| 구분 | 상태 |
| --- | --- |
| 완료 | 공식 상용·오픈소스 조사, 로컬 경로의 WAV18개, 공식 상용 MP3 세 개 확보. 사용자가 Anna를 현재 선호로 선택 |
| 완료 | Anna의 새 출발·동행·도착 대사 약 12.75초 생성. 원음·원문·공개 화자 ID·생성 화면 보존 |
| 보류 | 사용자 결정에 따라 계정·API 연결 보류. 정확한 API 모델·설정 재현과 같은 Anna ID의 합성 권한은 미검증 |
| 미구현 | 매 여행 자동 캐스팅·합성, 새 음성의 Android 연결, 캐릭터별 저장과 제품 host 연동 |
| 미검증 | 새 대사의 사람 수용, 장기 청취 피로·귀여움, 운전습관 개선 효과, 제품 이용 권한 |

최신 테스트는 [청취 가이드](../../../prototypes/voice_audition/README.md)를 따른다. 저장된 파일 재생에는 계정·서버·모델 설치가 필요 없다. 공개 데모는 새 대사도 생성했지만, 이 경로를 제품의 자동 합성 API로 사용하지 않는다.

[최신 파일 검사](../../../prototypes/voice_audition/evidence/pm-round2-verification.json)는 상용 MP3 세 개와 Sohee WAV 네 개, 선호·계정보류 기록과 청취 페이지를 실제로 읽어 파일·기록 일치를 확인했다. [새 Anna 대사 전사](../../../prototypes/voice_audition/asr/anna-journey-summary.md)는 정규화 CER 0%이며 마지막 구절까지 포함했다. 이는 자연스러움이나 귀여움의 합격 판정이 아니다. API 준비 도구의 12개 오프라인 검사와 인수인계 보존 검사 281개도 통과했다. 새 모델로 Android를 재시험한 결과는 없다.

[Android 연결 조사](../../../prototypes/voice_audition/evidence/android-integration-assessment.json)에서 기존 catalog가 PCM16 WAV와 합성 모델·설정을 요구하는 점을 확인했다. Anna의 미공개 값을 임의로 채우거나 기존 캐릭터 음성을 교체하지 않는다. 공개 데모 원음의 앱 개발 이용 범위도 확인되지 않아 자산 추가는 보류했다. [공식 문서와 판단 범위](../../../prototypes/voice_audition/commercial/README.md#사용-범위)를 함께 읽는다.

[같은 여행 원문의 Sohee 추가 실험](../../../prototypes/qwen_sohee_audition/journey/README.md)은 기본 연기 19.76초, 미소 연기 16.88초의 실제 WAV 두 개를 생성했다. 기존 모델·환경만 재사용했고 Anna 음원은 입력하지 않았다. 원문과 sampling 설정을 고정한 두 조건이며 피치·속도·음량 후처리는 없다. ASR은 모두 마지막 구절을 인식했고 반복·누락 후보는 없었지만 `네→내` 한 글자 차이를 보였다. 이 후보의 사람 청취 수용은 아직 없다.

## 조사와 선택 근거

| 후보 | 확인한 기능과 이번 판단 | 실제 실행 범위 |
| --- | --- | --- |
| Qwen3-TTS 1.7B VoiceDesign + Base | 설명 기반 설계·합성 참조 재사용 경로는 작동. 후속 대사의 사용자 청취에서 탈락 | MLX-community 8bit로 실제 VoiceDesign6개·Base2개 생성. A>B의 상대 선호 후 새 대사는 부자연스럽다고 평가 |
| Chatterbox Multilingual V3 | 한국어·MPS·MIT, 참조 음성 사용 가능. 다른 엔진 비교 기준 | 기본 음색2개·Qwen 합성 참조2개 생성. 제시한 B보다 A를 사용자가 선호 |
| Typecast SSFM 3.1 | 한국어 캐릭터 캐스팅의 상용 우선 비교 후보. 모델 ID `ssfm-v31`, 감정 프리셋·Smart Emotion 유지 | 공식 문서 조사. 계정·API 합성 없음 |
| ElevenLabs v4 / v3 + Voice Design | 공식 모델 기능은 조사했고 실제 청취는 공개 한국어 데모로 별도 수행 | Anna·Stella의 동일 대사 MP3를 정식 다운로드 버튼으로 확보. 정확한 모델 ID·설정은 공개 UI에 없어 버전별 benchmark로 부르지 않음 |
| Inworld TTS-2 | 저장 Voice Design과 한국어 연기 지시를 검토할 후보. Flash는 연출 제어가 다름 | 공식 문서 조사. 계정·API 합성 없음 |

후속으로 Qwen CustomVoice의 한국어 원어 프리셋 Sohee도 기본·가벼운 미소 조건에서4개를 실제 합성했다. VoiceDesign·Base 참조 복제는 사용하지 않았다. [원어 프리셋 보고](../../../prototypes/qwen_sohee_audition/README.md)에 고정 모델과 실제 호출을 기록했다. 새 상용 MP3 두 개와 Sohee 네 개는 같은 Whisper-small로 전사했을 때 공백·구두점 제외 CER0이었다. [후속 ASR](../../../prototypes/voice_audition/asr/round2-summary.md), [Stella 전사](../../../prototypes/voice_audition/asr/stella-summary.md)에 실제 결과가 있으며, 이 수치로 자연스러움이나 귀여움을 판정하지 않았다.

Anna는 공식 데모에서 입력 대사를 생성한 뒤 제공된 Download 버튼으로 받은 원음이다. 파일 SHA는 `5b7d8821b2d714789a54c0de0ba4005d373beb7871094e64051d752ceca649fb`, 길이는7.471초다. 모델 ID를 `eleven_v4`로 추정해 적지 않았다. [원음 획득·비교 조건](../../../prototypes/voice_audition/commercial/README.md)과 [선택 근거](../../../prototypes/voice_audition/selected-voice.json)를 따른다. API 계정 연결 후 접근 가능한 모델을 조회하고 같은 화자·같은 대사로 재현한 뒤 제품용 모델을 정해야 한다.

상용 기능·가격·계정별 이용 조건과 출처는 [상용 조사](tts-research-commercial.md), 공개 모델·라이선스·고정 upstream revision은 [공개 모델 조사](tts-research-opensource.md)에 기록했다. 지원 종료된 Supertone Play/API와 종료 예정인 Hume TTS는 새 공급자 후보에서 제외했다. Fish 가중치의 상업 조건과 큰 하드웨어 요구도 구분했다. 이 제외 판단을 기존 오픈 가중치의 실행 가능 여부와 혼동하지 않는다.

공식 자료에서 한국어 지원이나 감정 조절을 확인한 것은 품질 우열의 증거가 아니다. 영어 홍보 샘플·공급자 순위·주장 지연을 한국어 NUNTI의 측정치로 쓰지 않았다. 상용 계정은 사용자가 "사용 가능한 계정 없음"이라고 답했으며 새 가입·결제·녹음 업로드는 하지 않았다.

## 실제 만든 목소리

공통 문장은 "안녕하세요. 오늘의 여행도 함께할게요."와 "천천히 가도 괜찮아. 나는 네 옆에 있을게."다. [평가 대사와 기준](../../../prototypes/voice_audition/corpus.json)을 따르고 원문을 변형하지 않았다.

VoiceDesign은 둥근 미소·반짝 조약돌·포근 이끼를 각각 독립 설계해 총6개를 생성했다. 실제 모델은 `mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-8bit`, revision `f90d617701d9f7f4ca499291e0b57f2b3c2fd2ee`다. 이는 Qwen의 공식 PyTorch 런타임과 다른 MLX 변환·구현이다. [모델 lock](../../../prototypes/journey_voice_v3/model-lock.json)과 코드·라이선스를 보존했다.

Chatterbox는 고정된 공식 코드와 `t3_model="v3"`를 사용했다. 기본 조건과 Qwen의 합성 참조 조건에서 총4개를 생성했다. 모델의 기본 PerTh 워터마크는 유지했다. 실제 사람의 녹음을 복제하지 않았다. [실행 보고](../../../prototypes/chatterbox_audition/README.md)에 선택 파일·hash·고정 revision·명령을 기록했다.

사용자에게 제시한 A는 Qwen의 `round-smile-hello.wav`, B는 같은 합성 참조를 사용한 Chatterbox의 `qwen-reference-hello.wav`다. 사용자는 "A가 더 자연스러움"이라고 답했다. [사용자 피드백](../../../prototypes/voice_audition/user-feedback.json)은 두 실제 WAV의 hash와 연결한다. 이 응답을 모든 문장·모든 상용 모델·장기 피로까지의 승인으로 확대하지 않는다.

## 이전 Qwen 음색의 후속 대사 실험

선택한 A의 실제 파형과 정확한 참조 원문을 저장하고 Qwen Base의 ICL 참조 입력으로 전달했다. 같은 VoiceDesign 프롬프트를 문장마다 다시 실행하지 않는다.

- 참조 WAV SHA-256은 `f502f95d03b8ab40dbcaec0528557934f088d798133183b7d35b3109e1f946d4`다.
- Base 모델은 `mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit`, revision `e7dd0585652209fa0d7783659aad4e8a324de11c`다.
- preview binding은 `qvi-d3fdedd7b320e564917b4df1137a8f62`다. [실제 binding](../../../prototypes/journey_voice_v3/identity/binding.json)에 참조·정확한 전사·두 모델·runtime·설정을 함께 보존한다.
- 새 동행 대사5.68초와 "와, 도착했다! 여기서 어떤 기억을 만나게 될까?"5.92초를 실제 합성했다. 피치·속도 후처리는 없다.

프로세스 재실행에서 완료된2개 WAV를 캐시로 재사용하고 모델을 로드하지 않았다. 참조·전사·설정 변경은 모델 로드 전 거부한다. 별도 복사본에서 같은 binding ID를 유지한 채 metadata·WAV를 변조한22건도 실제 캐시 경로에서 거부했다. 원본7파일은 그대로다. 이 검사는 설정·참조·실제 바이트 보존의 증거다. 청각적으로 같은 화자임을 자동으로 보증하지 않는다. [실행·복원 가이드](../../../prototypes/journey_voice_v3/identity/README.md), [검증 기록](../../../prototypes/journey_voice_v3/identity/verification.json), [출처 변조22건](../../../prototypes/journey_voice_v3/identity/cache-provenance-verification.json)을 따른다.

새 설계는 `nunti-round-smile-preview-v3`라는 별도 실험이다. 기존 v1/v2 캐릭터 바인딩이나 Android 자산을 몰래 바꾸지 않았다. 제품에서는 여정마다 설계해 확정한 참조를 캐릭터에 귀속하고 재시도·reroute·재시작에는 그대로 재사용해야 한다. 현재 이 문서의 예제 하나로 매 여행 자동 캐스팅이 완성됐다고 주장하지 않는다.

## 검증 범위

| 검사 | 실제 결과 | 한계 |
| --- | --- | --- |
| 생성 파일 | 새 WAV12개 모두24kHz·mono·PCM16, 원문 metadata·파일 hash·프레임 길이 확인, full-scale clipping0 | 파형 검사로 발음·자연스러움·귀여움을 판정하지 않음 |
| 사용자 청취 | 초기 A>B 상대 선호 이후 새 Qwen Base 대사는 부자연스럽다는 평가로 탈락 | 현재 캐스팅 기준은 후속 상용 비교에서 선택한 Anna |
| 독립 ASR | 최초10개 중 인사5개 원문 일치, 동행5개는 `네→내`1음절 차이. 새 Base 도착 대사도 일치, 동행은 같은 차이 | 두 엔진에서 동일해 ASR 혼동 가능. 누락 후보는 없으나 실제 발음 확정 아님. [10개 결과](../../../prototypes/voice_audition/asr/summary.md), [추가2개](../../../prototypes/voice_audition/asr/identity-summary.md) |
| 지속성 | 선택 참조·binding·완료 파일의 재사용, 변경 요청 거부 | 참조와 설정 보존이 장기 청취 일관성의 충분조건은 아님 |
| 실제 실행 | Apple Silicon16GB에서 각 모델을 순차 실행하고 종료 | Android 기기 내 모델 추론·실차 지연이 아님 |

PM도 실제12개 WAV·원문 hash·PCM과 선택 binding을 직접 재확인했고, 보존된 인수인계281개 검사를 통과했다. [PM 취합 결과](../../../prototypes/voice_audition/evidence/pm-final-verification.json)에 확인 범위와 미검증을 함께 남겼다.

Qwen VoiceDesign의 첫 모델 로드는16.26초, 문장별 합성은2.29~5.52초였다. Base의 새 두 문장 합성은5.30/4.14초다. Chatterbox는 문장별5.11~24.72초였다. 각각 다른 cache/cold 조건이 있어 정밀 성능 benchmark로 비교하지 않는다. 주행 중 즉시 모델을 실행하는 설계 대신 허용 시점에 미리 준비한 오디오를 기존 단일 큐로 전달하는 제품 경계를 유지한다.

## 재현

로컬 청취에는 개발 환경이 필요 없다. 비교 페이지를 연다.

```sh
cd /Users/pig30nidae/NUNTI
open prototypes/journey_voice_v3/identity/listen.html
open prototypes/voice_audition/round2-listen.html
```

파일·비교 보드와 선택 binding은 다음으로 재검사한다. 큰 모델을 재합성하지 않고 현재 결과를 읽는다.

```sh
python3 prototypes/voice_audition/build_comparison.py
.local/journey-voice-v3/venv/bin/python prototypes/journey_voice_v3/verify.py
.local/chatterbox-audition/venv/bin/python prototypes/chatterbox_audition/verify.py
.local/journey-voice-v3/venv/bin/python prototypes/journey_voice_v3/identity/verify.py
.local/voice-audition-asr/venv/bin/python prototypes/voice_audition/asr/summarize.py
```

실제 새 합성에는 Apple GPU 접근이 필요하며 각 디렉터리의 setup/README를 따른다. 서로 다른 모델을 동시에 로드하지 않는다. 모델·패키지·원문·WAV를 로컬에 보존했고 비공개 경로·운전 데이터나 실인물 녹음을 외부 합성 서비스로 전송하지 않았다. 커밋·푸시는 하지 않았다.

완료한 것은 공급자 조사, 실제 로컬 엔진 합성, 공식 상용 데모 생성과 Anna 선호 확인이다. 상용 API의 정확한 모델 비교, 새 대사의 사람 수용, 제품의 매 여행 자동 생성·Android 새 자산 연결·차량 소리 경합·취소 후 무음 측정은 별도다. 기존 [Android TTS 구현 보고](tts-result.md)의 검증을 새 모델의 런타임 결과로 옮겨 적지 않는다.
