# Anna API 접근 확인과 오프라인 요청 준비

사용자가 실제 공개 데모에서 고른 Anna의 voice ID는 `uyVNoMrnUku1dZyVEXwD`다. 이 값은 공식 UI에서 관측한 선택값이며, 현재 계정의 API 사용 권한이나 공개 데모의 정확한 합성 모델·설정을 입증하지 않는다. 기존 Anna MP3와 메타데이터는 수정하지 않는다.

이 도구는 Python 표준 라이브러리만 사용한다. 읽기 전용 메타데이터 확인과 오프라인 요청 파일 작성만 구현한다. 음성을 생성하는 POST 함수, 가입·결제·보이스 추가·Android 변경 기능은 없다.

현재 결정은 `accountDeferredByUser: true`다. 사용자가 "지금은 계정 없이 진행"을 선택했으므로 계정 연결과 API 인증 확인을 보류한다. 추가 가입·API 호출·유료 합성을 진행하지 않는다. 아래 API 명령은 나중에 사용자가 계정 연결 작업을 다시 요청했을 때 사용할 준비 절차다. 지금 검증한 범위는 키 부재 처리와 오프라인 요청·가짜 응답 테스트까지다.

## 계정 연결 후 최소 조회

API 키는 현재 프로세스의 `ELEVENLABS_API_KEY` 환경변수로만 전달한다. 키를 채팅·요청 JSON·명령행 인수에 넣지 않는다. 키가 제공된 환경에서 다음 명령을 실행한다.

```sh
python3.12 prototypes/elevenlabs_voice/prepare.py --check-access
```

키가 없으면 `MISSING_API_KEY`, `networkRequests: 0`을 출력하고 exit 2로 종료한다. 키가 있을 때 허용하는 네트워크 경로는 다음 두 GET뿐이다.

| 경로 | 출력하는 정보 |
| --- | --- |
| `GET https://api.elevenlabs.io/v1/models` | v4·v3·Multilingual v2의 목록 포함 여부와 TTS·alpha 관련 불리언 |
| `GET https://api.elevenlabs.io/v1/voices/uyVNoMrnUku1dZyVEXwD` | 요청한 단일 voice ID의 메타데이터 수신 여부 |

전체 보이스 목록은 조회하지 않는다. 보이스의 소유자·이메일·공유 정보·녹음·샘플 URL·이름 등 응답 필드를 출력하거나 저장하지 않는다. 리다이렉트는 따르지 않으며 오류 본문·헤더·예외 문자열도 출력하지 않는다.

공식 [모델 목록 API](https://elevenlabs.io/docs/api-reference/models/list)는 모델 ID와 TTS 지원 플래그를 반환한다. [단일 보이스 API](https://elevenlabs.io/docs/api-reference/voices/get)는 지정한 보이스의 메타데이터를 반환한다. 이 GET들이 성공해도 합성 권한·크레딧·요금제·해당 모델과 Anna 조합의 실제 생성 성공은 별도로 확인해야 한다. 도구는 성공 시에도 `synthesisAccessVerified: false`를 유지한다.

## 원문을 그대로 담은 요청 파일

다음은 네트워크를 사용하지 않는 준비 명령이다. 모델·voice ID·작업·출력 형식을 모두 명시해야 한다. 기존 출력 파일은 덮어쓰지 않는다.

```sh
python3.12 prototypes/elevenlabs_voice/prepare.py \
  --write-request /private/tmp/anna-request.json \
  --text-file prototypes/elevenlabs_voice/anna-audition-text.txt \
  --model-id eleven_v4 \
  --voice-id uyVNoMrnUku1dZyVEXwD \
  --operation create-speech \
  --output-format mp3_44100_128
```

`anna-v4-request.json`은 위와 같은 방식으로 작성한 오프라인 예제다. 공개 데모에서 실제 사용한 두 문장의 원문을 그대로 담았다. 입력 파일의 UTF-8 바이트와 요청 본문의 `text`를 다시 UTF-8로 인코딩한 SHA-256이 같음을 확인한다. 앞뒤 공백·CRLF·개행·문장부호를 정리하지 않으며, 지시 태그도 추가하지 않는다.

준비 파일에는 `POST /v1/text-to-speech/{voice_id}`, 명시한 모델 ID, 출력 형식 query, 원문, 키를 전달할 환경변수의 이름만 들어간다. 키 값은 포함하지 않는다. 지원하는 형식은 `mp3_44100_128`과 `pcm_24000`이다. 후자는 WAV 컨테이너가 아닌 PCM 요청이다. 형식의 계정별 사용 가능성은 아직 확인하지 않았다. [공식 Create speech API](https://elevenlabs.io/docs/api-reference/text-to-speech/convert)

현재 [공식 제품 가이드](https://elevenlabs.io/docs/eleven-creative/playground/text-to-speech)는 `eleven_v4` 및 `eleven_v3`를 Create speech와 Stream speech에 사용할 수 있다고 설명하고, [공식 API 소개](https://elevenlabs.io/docs/overview/intro)도 `text_to_speech.convert`에 `eleven_v4`를 전달하는 예제를 제공한다. 여러 화자의 Text to Dialogue는 별도 API다. 이 문서 근거를 계정의 실제 접근 성공으로 바꾸어 주장하지 않는다. 도구는 Text to Dialogue endpoint를 추측하거나 호출하지 않는다.

## 검증 상태

현재 키를 연결하지 않은 상태에서 실제 `--check-access` 실행은 `MISSING_API_KEY`와 네트워크 0건으로 끝났다. `missing-key-check.json`에 결과가 있다. 오프라인 예제의 원문 해시는 기존 공개 Anna 데모의 원문 해시와 동일하다.

```sh
python3.12 prototypes/elevenlabs_voice/test_prepare.py
```

12개 검증은 가짜 transport만 사용했다. 키 부재 시 네트워크 생성 금지, 두 GET 경로 제한, 비공개 필드·오류 본문·실수로 전달한 명령행 키의 비출력, 리다이렉트 차단, CRLF와 공백 보존, 출력 파일 덮어쓰기 거부를 확인했다. 실제 제공자 요청과 합성 호출은 모두 0건이다. `tests.log`, `verification.json`, `sources.json`에서 근거를 확인한다. 계정 연결 후 실제 GET 접근과 유료 합성·음질 검증은 남아 있다.
