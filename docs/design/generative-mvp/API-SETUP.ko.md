# Nunti 실제 생성 API 연결하기

이 문서는 이전 v2의 세 공급자 통합 실험용이다. 사용자 담당 생성 기능의 최신 v3는 [시험·API 안내](../avatar-generator/TESTING.ko.md)를 따른다. 로컬 이미지는 키 없이 새로 렌더하며 선택 AI 이미지는 서버의 OpenAI 키 하나를 사용한다. 전체 제품 목표인 운전습관 개선과 [담당 범위](../../product/2026-hmg-app-challenge.md)를 유지한다.

**눈티의 제품 목표는 운전습관 개선을 돕는 아바타 동반자**이며, 사용자 담당은 목적지·내비게이션 경로 기반 아바타 생성이다. 이 안내는 해당 기능의 **현재 이미지·음성 통합 실험 코드** 실행법이다. 공모전의 필수 키 목록이 아니다. 현대 Gleo/NaviHelper의 역할과 담당 범위는 [제품·공모전 기준](../../product/2026-hmg-app-challenge.md)을 먼저 따른다. 이미지·음성 준비 상태 분리는 아직 설계이며 키 하나만으로 작동하게 변경된 상태는 아니다. 전체 제품의 음성 피드백 역할은 유지한다.

2026-11-03 기준. 기본 조합에는 **OpenAI·ElevenLabs·Google의 키 3개**가 필요하다. Google 가성비 조합도 비교하려면 **Recraft 토큰 1개**를 추가한다. 키 발급만으로 준비가 끝나지는 않는다. 계정의 모델 접근·보관 음성 슬롯·비용 상한을 확인한 뒤 실제 생성을 시작한다.

현재까지 검증한 것은 키 없는 샘플 연결과 가짜 공급자 응답을 사용한 어댑터다. 실제 계정 접근·새 이미지/음색의 품질·청구·응답 시간은 미검증이다. 이 안내를 작성하면서 계정에 접속하거나 생성 API를 호출하지 않았다.

## 1. 키 준비하기

| 사용할 곳 | 서버 환경변수 | 현재 코드의 역할 |
|---|---|---|
| OpenAI | `OPENAI_API_KEY` | `gpt-6.1-sol` 캐릭터 기획, `gpt-image-2.5-flare` 이미지 2후보 |
| ElevenLabs | `ELEVENLABS_API_KEY` | `eleven_ttv_v3` 음색 3preview → 1개 보관 → `eleven_v4` 대사 |
| Google AI Studio | `GOOGLE_API_KEY` | `gemini-3.8-flash`가 이미지·음성 후보를 함께 비교 |
| Recraft, 선택 | `RECRAFT_API_TOKEN` | `GOOGLE_COMPARE`에서 선정한 이미지 1장의 배경 제거 |

### OpenAI

1. [OpenAI 공식 시작 안내](https://developers.openai.com/api/docs/quickstart)의 **Create an API Key**에서 사용할 프로젝트의 키를 만든다.
2. 그 프로젝트에서 API 결제·사용 가능 한도와 [Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol), [Flare](https://developers.openai.com/api/docs/models/gpt-image-2.5-flare)의 접근 가능 여부를 확인한다. 인증이나 결제 설정을 요구하면 해당 계정의 안내를 따른다.
3. 제한 키를 사용한다면 이 서버가 호출하는 **Responses 생성**과 **Images 편집**을 허용한다. 서버는 `OPENAI_API_KEY`를 Bearer 인증에 사용한다. [공식 API 인증 안내](https://developers.openai.com/api/reference/overview)를 따른다.

### ElevenLabs

1. 로그인 후 **Developers → API Keys → Create Key**에서 Nunti용 키를 만든다. 키별 제한과 credit 한도를 설정할 수 있다. [공식 키 발급 안내](https://elevenlabs.io/docs/help-center/technical/how-do-i-authorize-myself-using-an-api-key)
2. 제한 키에는 아래 기능에 대응하는 권한을 허용한다. 화면의 권한 이름은 계정에 따라 확인한다.

   | 필요한 기능 | 현재 서버의 호출 |
   |---|---|
   | 사용자 구독·잔액·슬롯 조회 | `GET /v1/user/subscription` |
   | 모델 조회 | `GET /v1/models` |
   | Voice Design 미리듣기 생성 | `POST /v1/text-to-voice/design` |
   | 고른 음성을 내 음성으로 저장 | `POST /v1/text-to-voice` |
   | 저장한 음성으로 TTS | `POST /v1/text-to-speech/{voiceId}` |

3. `eleven_ttv_v3` 설계와 `eleven_v4` 합성, 24kHz PCM 출력이 해당 계정에서 가능한지 확인한다. 초기 20개를 모두 보관하려면 현재 사용 중인 음성을 제외하고 **새 음성 20개를 유지할 슬롯**이 필요하다. 현재 코드는 구독과 모델을 먼저 조회하지만 실제 계정의 권한은 아직 확인하지 않았다. [Voice Design API](https://elevenlabs.io/docs/api-reference/text-to-voice/design) · [구독 조회 API](https://elevenlabs.io/docs/api-reference/user/subscription/get)

기존 동반자의 후속 대사는 저장한 voiceId를 사용한다. 슬롯 확보를 위해 그 음성을 삭제하면 이후 새 대사를 만들 수 없으므로 보관할 음성의 슬롯을 유지한다.

### Google

1. [Google AI Studio 키 페이지](https://aistudio.google.com/api-keys)에서 사용할 프로젝트의 키를 만든다. 기존 프로젝트가 보이지 않으면 먼저 프로젝트를 가져온다.
2. 현재 공식 안내에서 새 AI Studio 키는 서비스 계정에 연결되는 auth key이며 Gemini API로 제한된다. 오래된 unrestricted 키를 재사용하지 말고 현재 발급 안내를 따른다. [공식 키·권한 안내](https://ai.google.dev/gemini-api/docs/api-key)
3. 해당 프로젝트의 [결제·사용량 설정](https://ai.google.dev/gemini-api/docs/billing)과 `gemini-3.8-flash` 접근을 확인한다. 기본 조합에서도 이미지·음성 비교를 위해 Google 키가 필요하다.

이 저장소는 **`GOOGLE_API_KEY`만 읽는다.** 다른 예제에 나오는 `GEMINI_API_KEY`만 설정하면 연결되지 않는다.

### Recraft, Google 조합을 비교할 때

[공식 시작 안내](https://www.recraft.ai/docs/api-reference/getting-started)의 **API tokens → Create token**에서 토큰을 만들고 API unit 잔액을 확인한다. 환경변수 이름은 **`RECRAFT_API_TOKEN`**이다. 현재 Google 이미지 조합은 선정한 한 장을 [배경 제거 API](https://www.recraft.ai/docs/api-reference/tools/remove-background)에 전달한다. 기본 OpenAI·ElevenLabs 조합에서는 이 토큰이 필요하지 않다.

## 2. 이 Mac에 서버 환경파일 만들기

터미널에서 다음을 실행한다. 키를 명령줄에 직접 붙여 넣지 않고 편집기에서 환경파일을 작성한다.

```sh
cd /Users/pig30nidae/NUNTI
umask 077
mkdir -p .local/generative-mvp
touch .local/generative-mvp/server-api.env
chmod 600 .local/generative-mvp/server-api.env
open -e .local/generative-mvp/server-api.env
```

편집기에 다음 양식을 넣는다. 키 자리표시자는 실제 값으로 바꾼다. 가격을 아직 확인하지 못했다면 **false와 null을 유지**한다. 이 상태에서는 아래 실행 전 검사와 백엔드가 실제 생성을 거절한다.

```sh
OPENAI_API_KEY='__PASTE_OPENAI_KEY__'
ELEVENLABS_API_KEY='__PASTE_ELEVENLABS_KEY__'
GOOGLE_API_KEY='__PASTE_GOOGLE_KEY__'

NUNTI_GENERATION_PIPELINE='OPENAI_ELEVEN'
NUNTI_GENERATION_PRICES_VERIFIED=false
NUNTI_GENERATION_STEP_CEILINGS_MICROS='{"planning":null,"image_candidates":null,"voice_candidates":null,"selection":null,"save_voice":null,"speech":null}'
NUNTI_GENERATION_INITIAL_LIMIT=20
NUNTI_GENERATION_VOICE_CAPACITY=30
NUNTI_GENERATION_JOB_CAP_MICROS=300000
NUNTI_GENERATION_TOTAL_CAP_MICROS=6000000
```

`NUNTI_GENERATION_VOICE_CAPACITY=30`은 애플리케이션의 로컬 상한이다. 계정에 30개 슬롯을 추가해 주는 설정은 아니다. 실제 계정의 가용 슬롯은 별도로 확인한다.

키는 이 서버 환경파일에만 둔다. APK나 채팅에 붙여 넣지 않는다. 실행 도구가 Android에 전달하는 로컬 서버 접속 토큰은 공급자 API 키와 별개다.

## 3. 계정 가격을 확인해 상한 채우기

위 JSON의 null을 계정에서 검토한 **양의 정수 비용 상한**으로 바꾼다. 단위는 USD의 백만분의 1인 microdollar이며, `100000`은 `$0.10`이다. 이 숫자는 단위 설명이며 모델별 권장 가격표가 아니다.

| JSON 키 | 상한에 포함할 작업 |
|---|---|
| `planning` | 캐릭터 설정 기획 1회 |
| `image_candidates` | 이미지 2후보 전체 |
| `voice_candidates` | ElevenLabs preview 3개를 만드는 설계 1회 |
| `selection` | 이미지·오디오 입력을 포함한 Gemini 비교 1회 |
| `save_voice` | 고른 화자를 보관하는 단계 |
| `speech` | 짧은 대사 합성 1회. 초기 생성에는 3회 사용 |

다음 합계가 여정당 예약 상한 `$0.30` 이하여야 한다.

```text
planning + image_candidates + voice_candidates + selection + save_voice + 3 × speech
```

단가·credit 환산·선정/보관 비용을 모르면 null을 남긴다. 현재 코드는 모든 필수 단계에 양의 상한을 요구하므로, 실제 과금이 없는 단계라도 검토한 작은 양의 예약 상한을 지정해야 한다. **작은 임의 숫자로 검사를 통과시키면 안 된다.** 확인을 마친 뒤에만 `NUNTI_GENERATION_PRICES_VERIFIED=true`로 바꾼다.

공식 가격과 계정의 실제 조건을 함께 확인한다. [OpenAI 가격](https://developers.openai.com/api/docs/pricing) · [ElevenLabs API 가격](https://elevenlabs.io/pricing/api) · [Gemini 가격](https://ai.google.dev/gemini-api/docs/pricing)

예약액은 실제 청구액이 아니다. 토큰 사용·설계 credit의 계정별 환산을 검증하지 않은 채 `$0.10–0.30`에 들어온다고 확정할 수 없다. 프로그램은 저장소의 예약액에 여정당 `$0.30`, 초기 총 `$6` 상한을 적용한다. 실제 공급자 청구가 예약을 넘으면 영수증으로 실비를 반영해야 한다. 구독료는 별도이며, [실비 정산·운영 절차](../../../backend/README.md)를 따른다.

## 4. 환경을 불러오고 실행하기

**`.env` 자동 로드는 없다.** 현재 백엔드와 실행 도구는 터미널에서 상속받은 환경변수를 사용한다. 파일을 저장한 것만으로 연결되지 않는다. 같은 터미널에서 다음을 실행한다.

```sh
cd /Users/pig30nidae/NUNTI
set -a
source .local/generative-mvp/server-api.env
set +a
```

이어 다음 블록 전체를 실행한다. 로컬 검사에 성공했을 때만 실행 도구를 호출한다. 검사는 네트워크를 사용하지 않으며 키 내용은 출력하지 않는다.

```sh
if python3 - <<'PY'
import json
import os
from pathlib import Path

def require(ok, message):
    if not ok:
        raise SystemExit(message)

path = Path('.local/generative-mvp/server-api.env')
require(path.stat().st_mode & 0o077 == 0, '환경파일 권한을 chmod 600으로 설정하세요.')
pipeline = os.getenv('NUNTI_GENERATION_PIPELINE', 'OPENAI_ELEVEN')
require(pipeline in {'OPENAI_ELEVEN', 'GOOGLE_COMPARE'}, '파이프라인 설정을 확인하세요.')
names = ('GOOGLE_API_KEY', 'RECRAFT_API_TOKEN') if pipeline == 'GOOGLE_COMPARE' else (
    'OPENAI_API_KEY', 'ELEVENLABS_API_KEY', 'GOOGLE_API_KEY')
for name in names:
    value = os.getenv(name, '').strip()
    require(len(value) >= 20 and '__PASTE_' not in value
            and not value.startswith(('YOUR_', 'REPLACE_'))
            and not any(c.isspace() for c in value), name + ': 실제 키를 환경파일에 입력하세요.')
require(os.getenv('NUNTI_GENERATION_PRICES_VERIFIED') == 'true',
        '계정의 비용 상한을 확인하기 전에는 실제 생성을 시작할 수 없습니다.')
try:
    prices = json.loads(os.getenv('NUNTI_GENERATION_STEP_CEILINGS_MICROS', '{}'))
except (ValueError, TypeError):
    raise SystemExit('비용 상한 JSON을 확인하세요.') from None
steps = {'planning', 'image_candidates', 'voice_candidates', 'selection', 'save_voice', 'speech'}
if pipeline == 'GOOGLE_COMPARE':
    steps.add('remove_background')
require(isinstance(prices, dict) and all(type(prices.get(k)) is int and prices[k] > 0 for k in steps),
        '모든 필수 단계의 null/자리표시자를 확인한 양의 정수 상한으로 바꾸세요.')
estimate = sum(prices[k] for k in steps) + 2 * prices['speech']
cap = int(os.getenv('NUNTI_GENERATION_JOB_CAP_MICROS', '300000'))
require(0 < cap <= 300000 and estimate <= cap, '계획한 단계별 예약 합계가 여정 상한을 넘습니다.')
print('자리표시자·가격 설정의 로컬 검사를 통과했습니다. 실제 키 권한은 아직 검증하지 않았습니다.')
PY
then
  python3 scripts/run_generative_mvp.py --mode api --restart-server
fi
```

이 검사는 키 형식의 기초 검사일 뿐 유효한 계정·모델 권한을 증명하지 않는다. 실제 키와 비용 설정을 넣기 전에는 통과하지 않는다. 현재 코드에는 별도 placeholder 검출 helper가 없으므로 위 검사 블록을 함께 사용한다.

실행 도구는 자신의 로컬 서버·작업자를 재시작하고 현재 환경을 두 프로세스에 전달한다. 내부 접속 토큰과 저장소 경로는 도구가 설정하므로 `NUNTI_AUTH_TOKENS`를 수동으로 만들 필요가 없다. 키나 가격을 바꿨을 때도 같은 터미널에서 source 후 `--restart-server`로 다시 시작한다.

**API 저장소에 이전 대기 작업이 있으면 작업자가 재시작 직후 이어서 처리할 수 있다.** 최초 연결에서는 앱에서 새 여정 1개로 시작해 이미지·한국어 음성·실제 비용을 확인한다. 계정 연결만으로 20개 비교를 한꺼번에 실행하지 않는다. 자동 비교는 [벤치마크 안내](benchmark/README.ko.md)를 따른다.

## 5. Google 가성비 조합을 비교하려면

같은 환경파일에서 다음을 변경하고 Recraft 토큰과 가격 상한을 채운다.

```sh
NUNTI_GENERATION_PIPELINE='GOOGLE_COMPARE'
RECRAFT_API_TOKEN='__PASTE_RECRAFT_TOKEN__'
```

가격 JSON에는 `remove_background`를 추가하고, `planning/image_candidates/voice_candidates/selection/speech`를 Google 조합 기준으로 다시 검토한다. 현재 Google 조합은 `gemini-nano-banana-2.1` 이미지 2후보, `gemini-3.8-flash-tts` 저장 음성 1후보, Gemini 비교와 Recraft 배경 제거를 사용한다. Google 프로젝트에 이미지·저장 Voice Design·TTS 접근과 잔액이 필요하다. 기본 조합의 비용값을 그대로 재사용하지 않는다.

이후 4단계의 source·검사·재시작을 반복한다. 기존 ElevenLabs 동반자의 후속 대사에는 원래 ElevenLabs 키가 계속 필요하다. 기본 파이프라인을 바꿔도 보관한 동반자의 음색을 새 공급자로 바꾸지 않는다.

현재 실행 도구는 API 저장소 경로를 고정하므로 파이프라인 변경만으로 별도 벤치마크 저장소가 생기지 않는다. 두 조합을 정식 비교할 때는 벤치마크 안내에 따라 서버·저장소를 분리하고 두 쪽 비용을 합산한다.

## 문제가 생겼을 때

| 표시 | 확인할 항목 |
|---|---|
| `MISSING_PROVIDER_CREDENTIALS` | 같은 터미널에서 source했는지, 필요한 변수 이름이 정확한지 |
| `ACCOUNT_PRICE_CONFIGURATION_REQUIRED` | 가격 검증 flag, 누락/null/0 단계, 계정별 상한 |
| `BUDGET_ESTIMATE_EXCEEDS_CAP` / `BUDGET_CAP_REACHED` | 초기 3대사를 포함한 예약 합계, 누적 예약·확정 실비 |
| `VOICE_SLOT_CAP_REACHED` | ElevenLabs/Google 계정의 실제 보관 슬롯과 로컬 상한 |
| `SYNTHESIS_MODEL_UNAVAILABLE` | ElevenLabs 계정에서 `eleven_v4`를 사용할 수 있는지 |
| `PROVIDER_HTTP_401` / `PROVIDER_HTTP_403` | 키 유효성·scope·프로젝트/모델 권한·결제 상태 |
| `RESULT_UNKNOWN` | 공급자 결과가 불명확한 상태. 같은 유료 생성을 새 요청으로 반복하기 전에 계정 요청 기록 확인 |
| 서버 모드·인증이 다르다는 실행 오류 | 현재 작업을 마친 뒤 `--mode api --restart-server`로 자신의 서버 재시작 |

프로세스가 생성 중이면 종료가 지연될 수 있다. 잠시 후 같은 실행 명령을 다시 사용한다. `.local/generative-mvp/server.log`와 `worker.log`를 로컬에서 확인하되 키나 환경파일 전체를 공유하지 않는다. [샘플 모드 사용법](TESTING.ko.md) · [현재 검증 결과](test-report.md)
