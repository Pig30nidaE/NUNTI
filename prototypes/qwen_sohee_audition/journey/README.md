# 같은 여행 대사로 Sohee 비교

계정 없이 새 대사를 합성할 수 있는 기존 로컬 후보를 Anna의 실제 새 대사와 같은 원문으로 비교한다. 두 Sohee 조건은 화자·샘플링 설정을 고정하고 연기 지시만 바꿨다. 기본 조건은 지시가 없고, 미소 조건은 기존의 `Native Korean conversational speech with a small smile.`을 사용했다. Anna는 원문만 같으며 합성 모델·설정은 미공개다. 품질 수용 여부는 미검증이며, 이전 VoiceDesign→Base 후보의 탈락 판단은 유지한다.

## 실제 산출물

[listen.html](listen.html)에 새 WAV 두 개가 있다. 원문은 상위 상용 데모 메타데이터의 `text`와 `textSha256`에서 읽었다. Anna MP3는 모델의 참조·학습 입력으로 사용하지 않았다. 실제 입력의 `referenceAudio`는 `null`이다. 캐릭터 조건과 sampling 설정은 상위 `config.json`을 읽기만 했다.

실제 새 음원은 기본 Sohee 19.76초, 가벼운 미소 16.88초다. 각각 합성에 12.26초, 9.90초가 걸렸다. 두 WAV 모두 24kHz 모노 PCM16이며 full-scale 샘플은 0개다. 청취 페이지에는 비교 목적으로 기존 Anna MP3도 연결했다. 이 플레이어 연결은 음성을 모델 입력으로 사용한 것이 아니다.

[model-refs.json](model-refs.json)에 모델·원본 revision·출처·설정·원문 해시를 기록했다. 실제 가중치는 `mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit`, revision `41d3337e8b7f2843a75841595fc14e4b9a7a4b96`의 기존 로컬 캐시다. 런타임도 기존 MLX-Audio 환경을 그대로 썼다. 새 모델·다운로드·패키지 설치·환경 변경은 없다. 라이선스는 상위 `licenses/`에 있는 기존 Apache-2.0 모델 및 MIT 런타임 기록을 따른다.

## 실행과 재검증

저장소 루트에서 실행한다. 최초 합성은 Apple Silicon GPU 접근이 필요하다. 실제 합성 로그는 [generation.log](generation.log)에 보존했다.

```sh
.local/journey-voice-v3/venv/bin/python prototypes/qwen_sohee_audition/journey/generate.py
.local/journey-voice-v3/venv/bin/python prototypes/qwen_sohee_audition/journey/verify.py
```

완료된 WAV와 메타데이터가 있으면 설정·해시를 검증하고 캐시를 재사용한다. 다시 합성하거나 덮어쓰지 않는다. 캐시 재시작 증거는 `cache-verification.json`과 `cache-restart.log`에 있다. 상위 기존 네 WAV·메타데이터·config·model lock·환경은 `baseline.json`으로 보존 확인한다.

독립 캐시 재시작에서 두 캐시를 재사용했고 새 WAV·메타데이터 4파일의 바이트가 그대로 유지됐다. 모델은 다시 로드하지 않았다. 기존 상위 보호 파일 13개와 패키지 목록도 그대로 유지됐다.

ASR은 합성 프로세스가 종료된 뒤 기존 Whisper-small을 재사용해 새 두 WAV를 각각 한 번 전사했다. 새 ASR 결과를 덮어쓰지 않도록 `asr.py`는 이미 결과가 있으면 종료한다.

```sh
.local/voice-audition-asr/venv/bin/python prototypes/qwen_sohee_audition/journey/asr.py
```

## 검사의 범위

피치·속도·음량·EQ·공간 효과·트리밍 후처리는 없다. WAV는 실제 원본 파형을 PCM16으로 저장한 것이다. [verification.json](verification.json)은 파일 해시·PCM 형식·길이·진폭·클리핑·상위 파일과 환경 보존·원문 일치를 확인한다.

`maxTokens`는 기존과 같은 375다. 이번 실행에서 API의 `GenerationResult.token_count`를 별도로 저장하지 않았고 직접 EOS 종료 사유도 기록하지 않았다. 토크나이저 `decode_upsample_rate=1920`과 PCM 프레임 수로 구한 상응치는 간접 자료다. 실제 토큰 수나 EOS를 직접 관찰한 것처럼 주장하지 않는다. 정확한 종료 상태를 얻기 위한 재합성은 하지 않았다.

[asr-results.json](asr-results.json)의 끝 구절·문자 편집 정렬·문장 반복 후보는 보조 자료다. ASR은 오류나 누락을 추정할 수 있고 발음·끝 잘림·귀여움·자연스러움·화자 동일성을 보증하지 않는다. Anna의 품질을 충족했다는 판정도 하지 않는다.

두 음원 모두 마지막 `오늘 만난 풍경은 내가 간직할게`까지 전사됐다. 정규화 CER는 각각 1.754%이며 원문의 `네`를 `내`로 인식한 한 음절 차이만 있었다. 문장 반복 후보는 검출되지 않았다. 이 차이는 ASR 자체의 혼동일 수도 있으므로 실제 오발음으로 확정하지 않는다. 추가 합성이나 반복 ASR로 더 나은 결과를 고르지 않았다.
