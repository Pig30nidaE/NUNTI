# NUNTI 공개 TTS 후보 조사

확인일은 2026-11-02다. 모델 제작자의 저장소, 모델 카드, 라이선스, 설치 문서만 조사했다. 이 문서는 후보 선택 근거다. 합성 성공이나 한국어 자연스러움의 청취 검증 결과는 포함하지 않는다. 기존 Supertonic WAV와 캐릭터 바인딩은 수정하지 않았다.

## 우선 실험할 두 모델

첫 후보는 **Qwen3-TTS 1.7B VoiceDesign**이다. 사람의 녹음 없이 캐릭터 설명으로 새 목소리를 만들 수 있어 NUNTI의 여행별 생성과 맞는다. 같은 계열의 CustomVoice `Sohee`를 한국어 기준 음성으로 함께 비교한다. 두 번째는 **Chatterbox Multilingual V3**다. 한국어를 지원하고 공식 구현에 Apple MPS 경로가 있다. 다만 자유로운 목소리 설계 기능은 없으므로, 기본 화자를 기준으로 비교하거나 Qwen이 만든 합성 레퍼런스를 사용한다. 이는 기능과 현재 환경을 기준으로 한 실험 순서이며, 음질 순위는 아니다. [Qwen 공식 사용법](https://github.com/QwenLM/Qwen3-TTS), [Chatterbox 공식 사용법](https://github.com/resemble-ai/chatterbox)

| 후보 | 한국어와 표현 조절 | 레퍼런스 필요 여부 | 상업 적용 조건 | Apple Silicon 판단 |
| --- | --- | --- | --- | --- |
| Qwen3-TTS 12Hz 1.7B VoiceDesign | 한국어 포함 10개 언어. 자연어 `instruct`로 음색·감정·운율 설계 | 최초 설계에는 녹음 불필요 | 코드와 공개 모델 Apache-2.0 | 공식 예제는 CUDA·BF16·FlashAttention2. MPS 성공·속도는 현 기기에서 실험해야 함 |
| Qwen3-TTS 12Hz 1.7B CustomVoice | 한국어 원어 화자 `Sohee`, 감정·말투 지시 | 제공 화자 사용에는 녹음 불필요 | Apache-2.0 | VoiceDesign과 동일하게 실측 필요 |
| Chatterbox Multilingual V3 | 500M, 한국어 `ko` 포함 23개 언어. `exaggeration`, `cfg_weight` 조절 | 기본 조건 음성을 제공. 고유 화자로 바꾸려면 음성 프롬프트 사용 | 코드·모델 MIT. 기본 PerTh 워터마크 포함 | 공식 예제의 `device="mps"` 및 구현 경로 확인. 실제 한국어 합성은 미검증 |
| Fish Audio S2-Pro | 4B Slow AR + 400M Fast AR. 한국어는 공식 Tier 2. 자유로운 inline 표현 태그 | 레퍼런스 사용 가능. CLI는 무작위 음색이면 레퍼런스 단계 생략 허용 | 가중치 Research License. 상업 목적에는 별도 서면 라이선스 필요 | 공식 설치 표는 Linux·WSL, NVIDIA 또는 CPU. Mac MPS 성공 근거 없음. 우선 로컬 실험에서 제외 |
| Fish Audio Drama 3 | 35B 전체·토큰당 3B 활성. 다중 캐릭터·자연어 제어 | 공식 예제는 레퍼런스 복제 | 현재 LICENSE 본문은 Community License. 모델 카드 상단에는 Research 태그가 남아 있어 실제 배포 전 적용 버전 확인 필요 | NVIDIA 전용, FP8 최소 48GB. CPU·MPS 미지원. 현 Mac 로컬 후보에서 제외 |

표의 Qwen 근거는 [VoiceDesign 모델 카드](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign)와 [공식 추론 코드](https://github.com/QwenLM/Qwen3-TTS/blob/022e286b98fbec7e1e916cb940cdf532cd9f488e/qwen_tts/inference/qwen3_tts_model.py)다. Chatterbox 근거는 [모델 카드](https://huggingface.co/ResembleAI/chatterbox)와 [MPS·기본 조건 로딩 코드](https://github.com/resemble-ai/chatterbox/blob/5de7a54aa4e5e2baadb0182dde554908b48b85c2/src/chatterbox/mtl_tts.py)다. Fish 근거는 [S2-Pro 모델 카드](https://huggingface.co/fishaudio/s2-pro), [S2-Pro 고정 라이선스](https://huggingface.co/fishaudio/s2-pro/blob/1de9996b6be38b745688de084d87a5633f714e4e/LICENSE.md), [Drama 3 모델 카드](https://huggingface.co/fishaudio/drama-3), [설치 요구사항](https://speech.fish.audio/install/), [레퍼런스 생략 조건](https://speech.fish.audio/inference/)이다.

## Qwen이 여행별 목소리 생성에 맞는 이유

공식 `Voice Design then Clone` 예제는 VoiceDesign으로 짧은 음성을 만든 뒤, 1.7B-Base의 `create_voice_clone_prompt`에 넣어 재사용한다. NUNTI에서는 여행 시작에 고유 음성을 한 번 만들고, 같은 캐릭터의 후속 대사에는 저장한 합성 레퍼런스를 재사용하는 방식에 해당한다. 실제 사람의 목소리가 없어도 이 경로를 시험할 수 있다. 재시도 때마다 VoiceDesign을 새로 호출하면 동일 캐릭터의 음색이 바뀔 수 있으므로, 설계 결과와 모델 버전·설명·시드·오디오 해시를 함께 보존해야 한다. 마지막 문장은 NUNTI의 일관성 요구에서 도출한 구현 판단이다. [공식 Voice Design then Clone 예제](https://github.com/QwenLM/Qwen3-TTS#voice-design-then-clone)

첫 실험의 설계 지시는 성인 한국어 화자의 자연스러운 대화, 작고 가벼운 공명, 짧은 미소, 과하지 않은 호기심을 대상으로 한다. 아기 흉내나 과장된 애니메이션 연기, 높은 음정만으로 귀여움을 만드는 지시는 제외한다. 오디오는 모델이 만든 원음을 유지한다. 이전의 +3 semitone 후처리는 이번 후보 평가에 사용하지 않는다. 이 지시는 제품의 원하는 연기 방향이며, 아직 모델의 수행 능력을 입증하지 않는다.

CustomVoice `Sohee`는 새 캐릭터 음색을 자유롭게 만드는 모델과 역할이 다르다. 한국어 원어 화자를 먼저 비교하면 설계 지시의 문제와 모델의 한국어 발음 문제를 나눠 판단할 수 있다. 공식 문서는 원어에 맞는 화자를 권장한다. [공식 CustomVoice 화자 목록](https://github.com/QwenLM/Qwen3-TTS#custom-voice-generate)

## 라이선스 구분

Fish의 최신 코드가 Community License로 바뀌어도 S2-Pro 가중치가 함께 바뀐 것은 아니다. 현재 코드 라이선스는 S2-Pro 가중치를 적용 대상에서 명시적으로 제외한다. Community License는 연 매출 USD 500,000 미만의 일부 상업 사용을 허용하지만, 별도 정의한 Hosted Service는 추가 계약이 필요하다. NUNTI에 실제 적용할 때는 사용할 가중치와 코드에 각각 붙은 라이선스를 확인해야 한다. [고정 Community License 본문, III 및 V](https://github.com/fishaudio/fish-speech/blob/0f8a12e8a651062fdee9c33a894bdccd3a8513f1/LICENSE)

S2-Pro의 고정 `LICENSE.md`는 상업 목적의 사용에 별도 서면 계약을 요구한다. 따라서 무료 공개 가중치라는 이유로 상용 앱에 바로 배포할 수 있는 후보로 분류하지 않는다. [S2-Pro Research License, III](https://huggingface.co/fishaudio/s2-pro/blob/1de9996b6be38b745688de084d87a5633f714e4e/LICENSE.md)

## 재현용 버전과 실제 파일 크기

다음 SHA는 조사 시점 공식 GitHub commits API와 Hugging Face models API에서 읽었다. `main`이나 `master`는 설치 버전으로 사용하지 않는다. 메타데이터 조회만 수행했으며 가중치는 다운로드하지 않았다.

| 대상 | 고정 revision | 공식 확인 위치 |
| --- | --- | --- |
| Qwen 코드 | `022e286b98fbec7e1e916cb940cdf532cd9f488e` | [GitHub commit](https://github.com/QwenLM/Qwen3-TTS/commit/022e286b98fbec7e1e916cb940cdf532cd9f488e) |
| Qwen VoiceDesign | `5ecdb67327fd37bb2e042aab12ff7391903235d3` | [HF tree](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign/tree/5ecdb67327fd37bb2e042aab12ff7391903235d3) |
| Qwen CustomVoice | `0c0e3051f131929182e2c023b9537f8b1c68adfe` | [HF tree](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice/tree/0c0e3051f131929182e2c023b9537f8b1c68adfe) |
| Qwen Base | `fd4b254389122332181a7c3db7f27e918eec64e3` | [HF tree](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base/tree/fd4b254389122332181a7c3db7f27e918eec64e3) |
| Chatterbox 코드 | `5de7a54aa4e5e2baadb0182dde554908b48b85c2` | [GitHub commit](https://github.com/resemble-ai/chatterbox/commit/5de7a54aa4e5e2baadb0182dde554908b48b85c2) |
| Chatterbox 모델 저장소 | `5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18` | [HF tree](https://huggingface.co/ResembleAI/chatterbox/tree/5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18) |
| Fish 코드 | `0f8a12e8a651062fdee9c33a894bdccd3a8513f1` | [GitHub commit](https://github.com/fishaudio/fish-speech/commit/0f8a12e8a651062fdee9c33a894bdccd3a8513f1) |
| Fish S2-Pro | `1de9996b6be38b745688de084d87a5633f714e4e` | [HF tree](https://huggingface.co/fishaudio/s2-pro/tree/1de9996b6be38b745688de084d87a5633f714e4e) |
| Fish Drama 3 | `78e5ab79e49aa9a25abe8799eff2c4d73a1c3216` | [HF tree](https://huggingface.co/fishaudio/drama-3/tree/78e5ab79e49aa9a25abe8799eff2c4d73a1c3216) |

Qwen VoiceDesign과 CustomVoice는 각각 주 가중치 3,833,402,552 bytes와 내부 speech tokenizer 가중치 682,293,092 bytes다. 합계는 약 4.516GB이며 Python 환경과 실행 중 메모리는 별도다. HF API의 `usedStorage`는 현재 파일을 모두 받는 데 필요한 크기와 같다고 가정하지 않았다. [VoiceDesign 고정 파일 목록 API](https://huggingface.co/api/models/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign/tree/5ecdb67327fd37bb2e042aab12ff7391903235d3?recursive=true), [CustomVoice 고정 파일 목록 API](https://huggingface.co/api/models/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice/tree/0c0e3051f131929182e2c023b9537f8b1c68adfe?recursive=true)

Chatterbox V3의 공식 로더는 `t3_mtl23ls_v3.safetensors`, `s3gen.pt`, `ve.pt`, `conds.pt`, 두 JSON 자원을 선택한다. 주요 세 가중치 합계는 약 3.207GB다. 전체 모델 저장소의 다른 세대 중복 파일을 전부 받을 필요는 없다. 현재 코드의 `from_pretrained`는 revision 인자를 노출하지 않으므로, 실험 도구는 위 SHA로 선택 파일을 먼저 내려받고 `from_local(..., t3_model="v3")`로 로딩하는 방식이 재현에 맞다. [공식 로더](https://github.com/resemble-ai/chatterbox/blob/5de7a54aa4e5e2baadb0182dde554908b48b85c2/src/chatterbox/mtl_tts.py), [고정 파일 목록 API](https://huggingface.co/api/models/ResembleAI/chatterbox/tree/5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18?recursive=true)

## 선택을 확정하는 데 필요한 증거

현재 증거는 한국어 지원·기능·조건·실험 가능성을 입증한다. NUNTI에 가장 자연스럽고 귀여운 음성이라는 결론은 아직 입증하지 않는다. 같은 한국어 대사와 음량으로 원음을 비교하고, 발음 누락·억양·문장 끝·숨·연기 과장·캐릭터 일관성을 따로 확인해야 한다. 여행마다 생성할 음색의 다양성도 단일 샘플의 성공으로 대신할 수 없다. 실제 합성 결과와 사용자 청취 선택이 생긴 뒤 최종 모델을 정한다.
