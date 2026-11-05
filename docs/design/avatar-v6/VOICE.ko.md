# 눈티 v6 역할별 로컬 음성

2026-11-04. 목적·일러스트 역할을 한국어 음성 지시로 바꾸고, 캐릭터마다 실제 WAV를 생성한다. 계정·API 키·유료 요청이 없으며, 기기 TTS의 피치만 바꾸는 방식과 구분한다. 사용자가 선호한 Anna를 재현했다거나 이번 음질을 승인했다는 뜻은 아니다.

## 선택 근거

공식 [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS)는 한국어와 텍스트 지시 기반 VoiceDesign, 참조 기반 Base 합성을 제공한다. 이 Mac에는 두 1.7B 8bit 모델과 MLX 환경이 이미 있으므로 새 다운로드 없이 사용할 수 있다. [MLX-Audio의 Qwen 안내](https://github.com/Blaizzy/mlx-audio/blob/main/mlx_audio/tts/models/qwen3_tts/README.md)에 따라 VoiceDesign으로 만든 합성 발화를 Base 모델의 참조로 쓰면 후속 문장을 같은 캐릭터 음성으로 유도할 수 있다. 청감상 일관성은 별도 평가 대상이다.

[Supertonic](https://github.com/supertone-oss-archive/supertonic)은 ONNX 실행에 적합하지만 공식 저장소가 보관 상태이고, 보유한 구성은 화자 선택 위주다. [Chatterbox](https://github.com/resemble-ai/chatterbox)는 한국어를 포함한 다국어 합성 후보지만, 이번 요구인 텍스트로 새 캐릭터 음색을 설계하는 흐름은 Qwen VoiceDesign에 직접 대응한다. 이는 현재 로컬 환경과 요구에 대한 선택이며 모든 모델의 청취 품질 순위를 측정한 결과가 아니다.

새로운 연구 후보 [VoTSpeech](https://github.com/ywbn/VoTSpeech)도 확인했다. 공식 실행 조건은 Linux·CUDA이고, 공개 평가와 적응 학습은 중국어 중심이다. 현재 Mac의 한국어 MVP에 바로 적용할 근거가 부족하며 가중치는 CC BY-NC 4.0이다. [VoiceSculptor 논문](https://arxiv.org/abs/2601.10629)의 나이·감정·말속도를 분리하는 설계는 향후 비교 대상으로 남긴다. 이번 구현의 청취 품질을 이들 연구의 점수로 대신하지 않는다.

## 생성과 보존

`build_voice_design(input, design)`은 `design.characterPlan.purpose.role`을 일러스트와 공유한다. 출장에는 자신감 있는 성인 동료, 물놀이에는 장난스럽고 앳된 판타지 동반자, 휴식에는 포근한 성인 목소리를 지시한다. 실제 사람이나 어린이의 녹음을 참조하지 않는다. 역할·말투·목적지·이름·여행 seed를 묶은 `profileId`는 같은 캐릭터에서 유지된다.

나이는 활동 분류와 별도로, 방문 이유에 명시한 가상 캐릭터 지시만 읽는다. `어린 아이 캐릭터`, `어린이 캐릭터`, `초등학생 캐릭터`, `꼬마 눈티`와 공백 변형을 지원한다. 명시적인 `성인 캐릭터`·`어른 눈티`도 구분한다. 독서 역할의 어린이 캐릭터에는 성인 출장 음성 대신 앳된 판타지 독서 동반자의 지시와 책 관련 대사를 만든다. 실존 아동의 음성을 복제하지 않는다.

`아이와 데이트`처럼 동행자만 언급하거나 목적지·장소 특성에 나이 표현이 있어도 아바타 나이로 사용하지 않는다. 나이 지시가 부정되거나 서로 충돌하거나 아직 미정이면 `characterAge.resolution=UNKNOWN`과 나이를 단정하지 않는 음성 지시를 만든다. 지원하는 표현에 한정한 규칙이며 일반적인 나이·의도 이해 모델은 아니다. 명시적 지시가 없는 기존 200개 계획은 키·문자열·해시까지 그대로 유지했다.

보정 후 실제 앱에서 ‘어린이 캐릭터가 해변에서 책 읽기’로 새 VoiceDesign 음원을 합성했다. 5.92초 WAV의 인증 다운로드·해시, Android 재생 완료, 보관 복원 후 동일 음원 재생을 확인했다. 증거는 `.local/avatar-v6/live/verification.json`과 `voice.wav`다. 이는 지시 전달과 실제 합성·재생의 검증이며 청감상 연령 인상이나 자연스러움에 대한 사람의 승인은 아니다. 200개 행렬과 별도로 센 1건이다.

처음 음성 듣기를 요청하면 VoiceDesign이 인사말을 합성한다. 저장한 원문·설정·모델 revision·WAV SHA-256을 검증해 다음 요청에서 그대로 재생한다. 다른 문장은 이 캐릭터가 처음 생성한 합성 WAV와 정확한 원문을 Base 모델에 참조로 전달한다. 누락되거나 바뀐 완료 캐시는 조용히 재합성하지 않고 오류를 반환한다.

200개 실제 시험에서 드물게 끝 토큰이 나오지 않는 합성과 지나치게 긴 인사말을 발견했다. 발화문 길이에 따른 시간 상한, 끝 토큰의 제한 전 도달, 유한·비무음 PCM을 게시 전 검사한다. 처음 게시하기 전만 최대 3개의 결정적인 seed·추론 설정을 시도하고, 실패 후보와 사유를 저장한다. 한 번 수락한 WAV는 이후 요청에서 고정한다. 이미 완료된 캐시가 새 길이 기준을 어기면 덮어쓰지 않고 오류를 반환한다. 이 시간 검사는 발음·귀여움 판정이 아니다.

아바타 200개의 서로 다른 음성 binding 또는 WAV 해시는 지각적으로 서로 다른 화자 200명을 입증하지 않는다. `speakerUniquenessVerified`와 `humanListeningVerified`는 별도 청취 판정 전까지 false다. 주행 이벤트·안전 효과를 만들어내거나 자동 발화하지 않는다.

## 재현

실행 환경은 `.local/journey-voice-v3/venv/bin/python`이다. VoiceDesign revision은 `f90d617701d9f7f4ca499291e0b57f2b3c2fd2ee`, Base revision은 `e7dd0585652209fa0d7783659aad4e8a324de11c`이며 실제 추론 전에 기존 모델 lock의 모든 파일 해시를 검증한다. 모델 Apache-2.0, MLX-Audio MIT 라이선스를 따른다. 피치·속도 DSP 후처리는 없다.

```sh
.local/journey-voice-v3/venv/bin/python scripts/voice_render_studio.py --status
.local/journey-voice-v3/venv/bin/python scripts/voice_render_studio.py \
  --plan .local/avatar-generator/v6-voice-verification/business-plan.json \
  --output .local/avatar-generator/voices
```

새 대사는 같은 명령에 `--text '오늘도 서두르지 말아요.'`를 추가한다. GPU가 없는 제한 환경에서는 실행하지 못하며, Metal 접근이 가능한 Mac 터미널에서 실행해야 한다. 이미지와 음성은 `.local/avatar-quality-v4/local-image/inference.lock`을 공유해 추론을 직렬화한다. 음성 HTTP 호출을 추가할 때 같은 lock을 바깥에서 다시 잡으면 안 된다.

`scripts/voice_verify_studio.py --cases CASES --output OUTPUT --synthesize`는 `{cases:[{id,input,design}]}`를 읽고 모델 하나를 재사용해 실제 모든 WAV를 만든다. `--synthesize` 없이 실행하면 계획만 검사했다고 결과에 명시한다. `scripts/voice_transcribe_studio.py`는 기존 Whisper-small 캐시로 원문을 프롬프트에 넣지 않는 1회 전사를 수행한다. 전사 일치율은 자연스러움·귀여움·인물 구별을 증명하지 않는다.

## 현재 대표 검증

새 화자 3개(출장·물놀이·휴식)와 출장 캐릭터의 추가 문장 1개를 실제 합성했다. WAV 길이는 5.44~6.80초, 순수 추론은 4.52~7.40초였으며 24kHz 모노 PCM16이다. 세 최초 음성의 full-scale PCM sample은 0이었다. 재현 자산과 직접 듣기 페이지는 `.local/avatar-generator/v6-voice-verification/`에 있다. 13개 계약 테스트는 역할 공유·한국어 이름 조사·발화 시간·재시도·새 여행·경로 탈출을 포함한 binding 변조·WAV 변조·완료 캐시 누락을 검사했다. 별도 실제 4개 캐시 재요청도 원본 해시가 같았고 모델을 로드하지 않았다. `scripts/voice_verify_retry.py`는 가짜 생성기와 실제 PCM 파일을 사용해 게시 전 재시도·불변 캐시·3회 상한·실패 증거 보존의 5개 조건을 검사한다. 이 제어 흐름 시험을 실제 모델 품질 결과로 세지 않는다.

원문을 주지 않은 Whisper-small 전사에서 출장 인사와 추가 문장은 정규화 원문에 일치했다. 물놀이 11.1%, 휴식 3.8%의 문자 차이가 있었으며 `을왕리`, 가상 이름, `파도`가 주요 확인 대상이다. 전사기의 오류와 실제 발음 문제를 구분하는 청취 검증은 남아 있다. 이 검사 중 발견한 `콩랑` 같은 대사의 조사 문제는 새 생성기에서 `콩이랑`으로 고쳤고, 첫 대표 음원은 비교 이력으로 보존했다.

## 200개 실제 합성 결과

20개 목적지 × 10개 목적의 원본 입력을 바꾸지 않고 실제로 200개 한국어 WAV를 합성했다. 서로 다른 음성 binding·seed·WAV SHA-256이 각 200개이며, 최종 PCM full-scale sample이 있는 음원은 0개다. 길이는 4.72~12.24초, 전체 재생 시간은 1,411.44초다.

첫 실행은 18분 28초가 걸렸고, 4개가 끝 토큰 제한에 걸렸다. 추가로 2개의 인사말이 각각 21.60초·15.68초로 길었다. 이 증거는 `.local/avatar-v6/voices/`에 그대로 보존했다. 실제 생성기의 게시 전 검사와 재시도 로직을 보강한 뒤, 같은 200개 입력에 대한 검증 재실행에서 유효한 최초 음원 194개의 바이트를 유지했다. 문제가 있던 6개만 다시 합성했고 모두 두 번째 후보에서 정상 종료했다. 200개 미리 정해 둔 음원에서 골랐다는 뜻이 아니다.

최종 결과는 `.local/avatar-v6/voices-final/verification.json`, 별도의 원본 WAV 재검사는 `independent-verification.json`, 개별 입력·음성 연결은 `results.json`이다. 실제 200개는 지원하는 목적 역할 13종 중 10종을 포함하며, 음성 지시 8종으로 연결된다. `STUDY`·`FOOD`·`EXPLORE`의 매핑은 코드에 있지만 이번 200개 실제 합성에는 포함되지 않았다. 역할 지시 수와 실제 생성 음원 수, 사람이 구별할 수 있는 화자 수는 서로 다른 지표다.

Whisper-small은 원문 힌트 없이 최종 음원 200개를 모두 전사했다. 공백·문장부호를 제외한 완전 일치는 25개, 전체 문자 오류율은 8.42%였다. 검토 기준 15%를 넘은 28개는 `asr/verification.json`의 `needsListeningReview`에 원문·전사·사례 ID로 남겼다. `을왕리해수욕장`, `판교테크노밸리`, `안목해변`, `협재해수욕장`과 `누리` 계열 가상 이름이 주요 확인 대상이다. 실제 TTS 발음 문제와 소형 ASR의 고유명사 인식 오류를 구별하는 사람의 청취는 남아 있다.

따라서 완료 판정은 **실제 생성 200개·저장된 음원 무결성·시간 상한·재시도·일러스트와 역할 연결**에 한정한다. **200개의 자연스러움, 귀여움, 지각적으로 고유한 화자, Anna 수준의 품질**은 승인하지 않았다.

```sh
.local/journey-voice-v3/venv/bin/python scripts/voice_verify_studio.py \
  --cases .local/avatar-v6/matrix/voice-input.json \
  --output .local/avatar-v6/voices-recheck --synthesize \
  --seed-cache .local/avatar-v6/voices-final
.local/voice-audition-asr/venv/bin/python scripts/voice_transcribe_studio.py \
  --results .local/avatar-v6/voices-final/results.json \
  --output .local/avatar-v6/voices-asr-recheck
```
