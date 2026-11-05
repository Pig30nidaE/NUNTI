# 선택한 Qwen 목소리로 새 문장 생성

사용자가 더 자연스럽다고 선택한 Qwen `round-smile-hello.wav`를 고정 레퍼런스로 사용해, Qwen Base에서 새 한국어 두 문장을 실제 합성했다. VoiceDesign의 스타일 설명만 반복하는 방식 대신 같은 합성 오디오와 정확한 전사를 ICL 입력으로 사용한다. 실제 사람의 목소리는 사용하지 않는다.

`listen.html`에서 원본과 새 두 문장을 비교할 수 있다. 같은 참조·모델·설정이 보존됐다는 검증과, 사람이 듣기에 같은 화자라는 판단은 다르다. 새 두 음성의 자연스러움·귀여움·청각적 화자 일관성은 아직 미검증이다.

## 실제 결과

| 입력 | 길이 | 실제 합성 시간 | 메모리 |
| --- | --- | --- | --- |
| 천천히 가도 괜찮아. 나는 네 옆에 있을게. | 5.68초 | 5.30초 | MLX 관측 peak 6,353,758,501 bytes |
| 와, 도착했다! 여기서 어떤 기억을 만나게 될까? | 5.92초 | 4.14초 | MLX 관측 peak 6,428,126,444 bytes |

모델 로딩은 1.61초였고 speech tokenizer encoder가 존재함을 실제 확인했다. 기존 ASR GPU 프로세스가 종료된 뒤 이 모델만 실행했으며 합성 프로세스도 exit 0으로 끝났다. 오디오는 24kHz·모노·PCM16 WAV다. full-scale 샘플은 두 파일 모두 0개다. 음정·속도·음량 보정·노이즈 제거 후처리는 하지 않았다.

## 고정한 정체성

`binding.json`은 `nunti-round-smile-preview-v3`의 음성 미리보기 바인딩이다. 기존 v2 바인딩과 제품 캐릭터를 교체하지 않는다. 바인딩은 다음 자료를 포함한다.

- Base 모델 ID·revision·원본 Qwen revision과 모델 파일 목록의 SHA-256.
- 선택된 VoiceDesign 모델 ID·revision과 원본 메타데이터 해시.
- 원본 `round-smile-hello.wav`의 SHA-256 및 정확한 전사 `안녕하세요. 오늘의 여행도 함께할게요.`.
- Base 생성 매개변수·언어·시드와 기존 MLX 런타임의 버전·구현 파일 해시.

`reference.wav`는 선택된 오디오의 바이트 동일 복사본이다. 새 대사의 원문·원문 해시·출력 해시·바인딩 ID는 `samples/*.json`에 별도로 기록한다. 바인딩에는 개별 대사를 넣지 않아 같은 목소리의 후속 대사를 구분한다. 현재 생성 명령은 이 두 대사만을 대상으로 한 실험 도구이며, 매 여행 자동 발급 서버는 구현하지 않는다.

완성된 WAV와 메타데이터가 있으면 생성하지 않고 캐시를 사용한다. 같은 결과 경로에서 참조 오디오·참조 전사·모델·런타임·설정이 달라지면 거부한다. WAV만 있거나 JSON만 있는 중단 결과도 자동 덮어쓰지 않는다.

## 검증 결과

`verification.json`에 실제 별도 프로세스 재실행의 stdout과 결과를 보존했다. 두 대사가 모두 cache hit였고 모델을 로드하지 않았다. 바인딩·참조·모델 lock·두 WAV·두 메타데이터 등 7개 파일의 재실행 전후 해시는 동일했다.

변경된 온도, 변경된 참조 오디오, 변경된 참조 전사를 전달한 세 실행은 모두 모델 로드 전에 실패했다. 원래 Qwen 가상환경의 설치 패키지 목록과 기존 requirements lock 해시도 실행 전후 동일했다. 이 검증은 청각적 화자 동일성을 보장하지 않는다.

캐시 메타데이터의 바인딩 문자열만 맞추고 나머지 출처를 거짓으로 바꾸는 경우도 차단한다. `cached()`와 검증기는 같은 함수로 생성 설정 전체, Base·VoiceDesign 모델 ID와 revision, 참조 해시와 전사, 후처리, 원문, 오디오 경로·해시를 바인딩 및 실제 파일과 대조한다. WAV의 채널·표본율·프레임·길이 메타데이터도 실제 헤더와 대조한다.

`cache-provenance-verification.json`은 약 750KB의 별도 임시 복사본에서 22개 변조를 각각 실제 캐시 경로로 실행한 결과다. 같은 바인딩 ID를 유지한 채 온도·참조 SHA·모델 revision·후처리·원문·WAV 바이트를 바꾸는 사례를 포함한다. 모든 사례가 거부됐고, 탐색 프로세스에서 MLX 등 추론 모듈의 import를 금지해 모델 로드와 새 추론이 없음을 확인했다. 원본 7개 파일은 최초 검증 때의 SHA와 동일하다.

## 재현

저장소 루트에서 실행한다. 기존 `.local/journey-voice-v3/venv`를 사용하지만 패키지는 설치하거나 바꾸지 않는다.

```sh
python3.12 prototypes/journey_voice_v3/identity/download_model.py
.local/journey-voice-v3/venv/bin/python prototypes/journey_voice_v3/identity/generate.py
.local/journey-voice-v3/venv/bin/python prototypes/journey_voice_v3/identity/verify.py
```

완성된 증거가 존재하는 현재 상태에서 두 번째 명령은 캐시만 읽는다. 최초 GPU 추론에는 Metal 접근이 가능한 실행 환경이 필요하다. 다른 모델 프로세스와 동시에 로드하지 않는다.

캐시는 별도 `.local/journey-voice-v3-identity/`에 있다. 새 모델 다운로드는 2,421,865,696 bytes다. 기존 VoiceDesign speech tokenizer가 Base의 공식 파일 해시와 같아 682,293,092 bytes는 읽기 전용 심볼릭 링크로 재사용했다. 모델 전체 논리 크기는 3,104,158,788 bytes이며, 새로 받은 데이터는 3GB 미만이다.

## 모델·런타임·라이선스

추가 모델은 [MLX Community Qwen3-TTS 1.7B Base 8bit 고정 revision](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit/tree/e7dd0585652209fa0d7783659aad4e8a324de11c) 하나다. 모델 카드는 원본 [Qwen Base](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base)에서 MLX 형식으로 변환했음을 밝힌다. Qwen 제작자의 런타임이 아닌 MLX Community 변환본이다. Qwen의 공식 문서에도 [VoiceDesign 후 합성 참조로 복제하는 경로](https://github.com/QwenLM/Qwen3-TTS#voice-design-then-clone)가 있다.

`model-lock.json`, `model-card.md`, `source-refs.json`에 출처와 버전을 보존했다. 모델·Qwen 코드는 Apache-2.0, MLX-Audio는 MIT이며 원문을 `licenses/`에 보존한다. 실제 사용한 MLX-Audio 0.6.3·MLX 0.32.4와 나머지 관련 버전은 바인딩의 `runtime` 및 `environment-before.json`에서 확인한다.
