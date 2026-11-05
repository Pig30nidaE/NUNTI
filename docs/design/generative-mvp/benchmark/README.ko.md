# 여정별 이미지·음성 벤치마크

이 도구는 모델 호출 없이 입력과 평가 파일을 준비한다. `--run`을 명시하면 Nunti 서버에 연결한다. 이미지·TTS 공급자 API를 직접 호출하지 않는다.

20개는 시험 입력 수다. 고정 캐릭터 목록이 아니다. 6개 입력을 primary와 value 서버 설정에서 비교하고, 선정한 설정으로 새 입력 14개를 검증한다. 최대 생성 수는 26개다. 목적지 이름은 시험용이며 경로는 정규화한 선이다. 지도 경로 조회를 실행하지 않는다.

## 준비와 로컬 검증

저장소 루트에서 실행한다.

```sh
python3.12 scripts/benchmark_generative_mvp.py --prepare
python3.12 scripts/benchmark_generative_mvp.py --self-test
```

`inputs.json`에는 20개 입력이 있다. `blind-key.json`은 공급자 설정과 blindId를 연결하므로 평가자에게 숨긴다. `ratings-template.csv`에는 공급자 이름이 없다. 같은 디렉터리에서 `--prepare`를 다시 실행해도 입력 UUID와 기존 평가 파일을 덮어쓰지 않는다.

`runner-config.json`의 기본 모드는 `OFFLINE_FIXTURE`다. `tokenFile`은 Bearer 값이 들어 있는 파일을 가리킨다. JSON 연결 파일은 `tokenField: "token"`으로 읽는다. 토큰 값을 터미널·CSV·보고서·미디어에 출력하지 않는다.

로컬 연결 시험에는 별도 workspace를 쓴다.

```sh
python3.12 scripts/benchmark_generative_mvp.py --prepare \
  --workspace docs/design/generative-mvp/benchmark/offline-smoke
python3.12 scripts/benchmark_generative_mvp.py --run \
  --workspace docs/design/generative-mvp/benchmark/offline-smoke \
  --profile primary --base http://127.0.0.1:8767 --limit 1
```

실제 로컬 연결 1건에서 생성 작업의 READY, PNG와 3개 WAV의 인증 다운로드, SHA-256을 확인했다. 서버가 반환한 기존 fixture 미디어를 사용했다. 새 이미지·음색을 생성하지 않았으며 API 모드 호출은 0건이다. 이 결과는 채택 근거가 아니다.

## 계정 연결 후 비교

primary와 value의 모델 선택은 각 서버 설정에 있다. 클라이언트는 요청에 profile·model·journeyId·tags를 추가하지 않는다. `runner-config.json`에 서버 주소·기대 pipeline·mode·토큰 파일만 설정한다. 두 설정은 서로 다른 서버 주소를 사용할 수 있다.

API 서버의 capabilities가 설정과 일치해야 요청을 보낸다. 실행하려면 `--allow-api`를 추가한다. 기본 요청 한도는 1건이다. 전체 비교는 다음과 같이 명시한다.

```sh
python3.12 scripts/benchmark_generative_mvp.py --run --phase compare --limit 12 --allow-api
```

`review.html`에는 준비된 이미지와 인사·공통·도착 음성이 blindId로 표시된다. 이미지의 256px·128px·64px 보기를 함께 제공한다. `ratings.csv`에 raterId와 네 항목의 점수를 입력한다. 한 사람이 여러 캐릭터를 평가할 수 있다. 같은 blindId와 raterId의 중복은 거절한다.

각 점수는 1부터 5까지다. `cuteness`는 귀여움, `collectibility`는 소장 의향, `naturalness`는 한국어 음성의 자연스러움, `voiceFit`은 이미지·성격과 음성의 어울림이다. 여정마다 평가자 수가 달라도 각 여정의 비중은 같다.

```sh
python3.12 scripts/benchmark_generative_mvp.py --evaluate \
  docs/design/generative-mvp/benchmark/ratings.csv
```

두 설정 각각 비교 입력 6개가 모두 평가되어야 한다. 네 항목 평균이 각각 4 이상인 설정만 통과한다. 종합 평균을 먼저 비교하고, 차이가 0.2점 이하면 실측한 채택 캐릭터당 비용이 낮은 설정을 선택한다. 비용을 모르면 0으로 채우지 않으며 채택하지 않는다. 비용은 같은 설정·단계의 측정된 전체 비용을 준비 완료된 캐릭터 수로 나눈 값이다.

비교 결과는 `PROVISIONAL_PROFILE_SELECTED`다. `evaluation.json`에서 임시 선정 설정을 확인하고 새 입력 14개를 실행한다. 다음 명령의 primary는 실제 선정 설정으로 바꾼다.

```sh
python3.12 scripts/benchmark_generative_mvp.py --run --phase validation \
  --profile primary --limit 14 --allow-api
```

새 입력 14개의 네 항목 평균도 각각 4 이상이어야 최종 `ADOPTED_PROFILE_SELECTED`가 된다. `OFFLINE_FIXTURE` 행이 들어 있는 평가는 거절한다. 인간 평가나 비용이 부족하면 미채택 또는 임시 선정 상태를 유지한다.

## 비용과 재실행

운영 상한은 생성 파이프라인당 $0.30이다. 비교 실험 한도 $3.60과 새 입력 검증 한도 $4.20을 별도로 기록한다. 최대 26개 요청에 각각 $0.30을 보수적으로 예약한 값이다. 이 한도는 실제 청구 금액 추정치가 아니다.

실측 비용은 `data.cost.complete=true`이고 `actualMicros`가 정수일 때만 사용한다. 누락·null·부분 비용은 `COST_UNKNOWN`이다. API 모드에서 비용을 모르면 현재 결과를 보관하고 다음 POST를 멈춘다. fixture 서버가 명시한 실제 비용 0은 기록할 수 있으나 생성 품질 평가에는 사용할 수 없다.

각 요청은 POST 전에 로컬 ledger에 기록한다. 응답을 잃거나 중간에 종료해도 기존 요청 ID를 새 POST로 다시 보내지 않는다. 다시 실행하면 GET으로 상태를 확인한다. 결과 불명·실패·한도 초과·서버 설정 변경에서는 다음 생성을 멈춘다. 동시 실행은 workspace 잠금으로 거절한다. 공급자를 자동 변경하지 않는다.

현재 시험은 최초 이미지와 3문장을 평가한다. 후속 새 대사의 동일 음색 유지·장기 재생·실차 동작은 별도 통합 검증 항목이다. 준비 파일과 자체 단위 테스트는 실제 모델의 디자인·자연스러움 증거가 아니다.
