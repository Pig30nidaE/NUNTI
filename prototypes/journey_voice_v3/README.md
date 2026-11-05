# 새로운 한국어 캐릭터 음성 실험

기존 Supertonic3와 피치 후처리 후보에 대한 사용자 피드백을 반영한 별도 실험이다. Qwen3-TTS VoiceDesign 모델이 자연어 지시를 받아 음색과 말투를 직접 생성한다. 피치·속도·음량 후처리, 실인물 음성 복제, 유료 API 호출은 사용하지 않는다.

Qwen의 [원본 모델](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign)은 한국어와 자연어 음성 설계를 지원한다. 이 실험의 실제 런타임은 [MLX-Audio](https://github.com/Blaizzy/mlx-audio)의 독립 MLX 구현이고, 실제 가중치는 [MLX-community 8bit 변환](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-8bit)이다. Qwen 공식 PyTorch 런타임과 구분한다. 모델은 Apache-2.0, MLX-Audio 코드는 MIT다. 고정 revision과 실제 파일 해시는 [model-lock.json](model-lock.json), 출처와 코드 대조는 [sources.json](sources.json)에 기록한다.

## 실행

Apple Silicon, Python 3.12.12, uv가 필요하다. 기본 실행 파일은 앞선 실험에서 설치한 읽기 전용 uv와 Python이다. `NUNTI_UV`, `NUNTI_PYTHON` 환경변수로 다른 경로를 지정할 수 있다. 패키지와 모델 캐시는 `.local/journey-voice-v3/`에만 설치한다. 기존 v1/v2 환경과 바인딩은 수정하지 않는다.

저장소 루트에서 실행한다.

```sh
bash prototypes/journey_voice_v3/setup.sh
.local/journey-voice-v3/venv/bin/python prototypes/journey_voice_v3/generate.py
.local/journey-voice-v3/venv/bin/python prototypes/journey_voice_v3/verify.py
```

최초 실행은 공개 모델 약 3.08 GB를 다운로드한다. 합성 시에는 로컬 고정 모델만 읽고 네트워크를 사용하지 않는다. 기존 샘플은 해시와 설정이 일치하면 그대로 재사용하며, 다른 설정으로 덮어쓰지 않는다. GPU 접근이 허용된 로컬 실행 환경이 필요하다. 여러 음성 모델을 동시에 로드하지 않는다.

한 후보만 생성하려면 `generate.py --style round-smile --sentence hello`를 사용한다. 생성 로그의 시간은 로컬 실측이며 서비스 지연이나 Android 기기 내 추론 성능을 의미하지 않는다.

## 비교 방법과 남은 검증

[listen.html](listen.html)은 동일한 두 문장을 세 스타일로 듣는 정적 페이지다. 둥근 미소·반짝 조약돌·포근 이끼의 지시는 [styles.json](styles.json)에 있다. 작은 캐릭터의 성인 음색, 자연스러운 미소, 명료한 한국어를 요청하고 과도한 애교와 아기 목소리를 피한다. 속도 파라미터 변경 없이 모델의 기본 발화 속도로 비교한다. 스타일 지시에 따라 실제 발화 속도는 달라질 수 있다.

두 문장은 각각 독립 VoiceDesign 추론이다. 같은 지시문과 seed가 같은 화자 정체성을 보장하지 않는다. 이 결과는 스타일 청취 후보이며, 매 여행 생성한 목소리를 영구 보존하는 완성된 파이프라인이 아니다. 최종 선정 후에는 합성된 참조 음성과 원문을 저장하고 Base 모델의 참조 음성 경로로 재사용하는 별도 검증이 필요하다.

[verification.json](verification.json)은 WAV 해시, 원문·설정 일치, PCM 형식, 길이, 최대 진폭과 클리핑 수만 검증한다. 자연스러움·귀여움·한국어 발음·문장 간 음색 일치는 사람의 청취 평가가 남아 있다. Android 앱은 이 실험으로 변경하지 않았다.
