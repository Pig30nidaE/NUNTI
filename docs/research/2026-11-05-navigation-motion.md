# Pleos 기본 내비 이동 진단

성공 기준은 기본 내비 지도 위치·남은 거리·TBT의 실제 변화다. 점수 시나리오나 별도 지도 애니메이션은 이 기준을 충족하지 않는다.

## 현재 관찰

2026-11-05 실행 중인 `Nunti_Restore_2_1`에서 기본 내비는 수정구 시흥동, `37.4127212, 127.094681`에 고정됐다. Android GPS와 Pleos Fused 서비스는 다른 좌표를 수신한다. 내비가 전면에 있을 때도 `GpsLocationSource`가 `NMEA checksum mismatch`를 반복한다. 내비 `navi_engine` 로그의 원본 위치 `org`와 지도 매칭 위치 `match`는 변하지 않는다.

내비 설정의 충전소·경로·사운드·버전 정보를 확인했지만 모의주행 항목은 찾지 못했다. 내비 버전은 `3.3.2-rc5-hotfix.3 - 2026.10.16`이다.

## 실행한 입력 시험

`scripts/probe_navigation_nmea.py`는 판교 출발점 옆 약 56m 도로 좌표를 초당 5m씩 보간한다. 전체 20초 중 종점 이후는 정지한다. 실제 기본 내비의 `org`가 5m 이상 바뀌는지 검사한다. Android GPS 이동이나 명령의 OK 응답만으로 통과하지 않는다.

| 시험 | Android 위치 | 기본 내비 원본 위치 |
|---|---|---|
| 정상 XOR NMEA만 입력 | 기존 위치 유지 | 고정 |
| NMEA + geo fix + 매초 Console 속도 동기화 | 경로 좌표 수신 | 고정 |
| API34 파서에 맞춘 정수 시각·자기편차 RMC + geo fix + Console 동기화 | 경로 좌표 수신 | 고정 |

실행 증거는 `.local/integration-2026-11-05/nmea-20261105T113411Z/`, `nmea-20261105T113619Z/`, `nmea-20261105T113744Z/`에 있다. `nmea-20261105T113445Z/`는 Console에 소수 속도를 보내 입력 형식 단계에서 실패한 시도이며 유효한 이동 시험이 아니다. 마지막 유효 시험 뒤 GPS 좌표와 Console D·속도0·페달0·조향52 복원을 읽어 확인했다. geo fix 시험의 위성·passiveUpdate 전체 설정 보존은 별도 미확인이다.

## 공개 소스가 보여 주는 다음 구분

공개 AOSP 호스트 `gps.cpp`는 자동 GGA/RMC에 `*47`을 붙인다. raw NMEA는 그대로 전달하지만 저장 GPS 상태를 바꾸지 않는다. 자동 갱신이 켜져 있으면 잘못된 문장이 다시 섞일 수 있다. Android14 HAL은 RMC의 정수 시각과 자기편차 필드를 엄격하게 읽는다.

- [호스트 GPS 생성](https://android.googlesource.com/platform/external/qemu/+/refs/heads/emu-master-dev/android/emu/gps/src/android/gps.cpp)
- [호스트 자동 갱신](https://android.googlesource.com/platform/external/qemu/+/refs/heads/emu-master-dev/android/emu/gps/src/android/gps/PassiveGpsUpdater.cpp)
- [호스트 GPS RPC 구현](https://android.googlesource.com/platform/external/qemu/+/refs/heads/emu-master-dev/android/android-grpc/services/emulator-controller/server/src/android/emulation/control/EmulatorService.cpp)
- [Android14 GNSS HAL 파서](https://android.googlesource.com/device/generic/goldfish/+/refs/heads/android14-release/gnss/GnssHwListener.cpp)
- [공식 geo fix·NMEA 명령](https://developer.android.com/studio/run/emulator-console#geographic-location)

공개 호스트 소스 버전은 35.6.3이고 설치 호스트는 37.2.13이다. 정확한 바이너리 소스 일치까지 확인한 것은 아니다. 정상 문장을 보냈다는 사실만으로 내비 내부가 이를 위치로 채택했다고 판단하지 않는다.

추가 검토에서 공개 `setGps` 구현은 매번 `gpsSendLoc`을 실행하며, 해당 버전은 요청의 `passiveUpdate`를 읽지 않는다는 점을 확인했다. 따라서 프레임마다 `setGps`를 호출하면 정상 문장 직전에 잘못된 문장이 다시 섞인다. 준비한 시험은 제어를 한 번 요청한 뒤 `getGps().passiveUpdate == false`를 확인하고, 3초 안정화 중에도 잘못된 NMEA 오류가 계속되면 이동 입력을 시작하지 않는다. 이후에는 raw NMEA만 보낸다. 설치 버전에서도 이 제어가 지원되는지는 아직 미검증이다.

현재 실행에는 인증된 EmulatorController가 없어 자동 위치 갱신을 끄는 `GpsState.passiveUpdate`를 조회·변경할 수 없다. 다음 명령은 **사용자의 에뮬레이터 재시작 승인 후에만** 실행한다. 기존 앱 데이터는 지우지 않는다.

설치된 37.2.13 바이너리의 `emulator -help-no-passive-gps`가 `disable passive gps updates`를 반환하는 것을 확인했다. `--navigation-only` 재시작은 이 공개 옵션을 추가하여 잘못된 자동 전송을 처음부터 끈다. 인증 RPC는 해당 상태 조회와 좌표·속도·방위 보존에 사용한다. 이 실행 구성에서는 시험 후에도 자동 전송을 끈 상태를 유지하고, 개별 입력 시험은 재시작 직후의 원본 GPS와 Console 값을 복원한다. 실제 기본 내비 이동 확인은 여전히 남아 있다.

```bash
python3 scripts/restart_navigation_emulator.py --navigation-only --run
.local/voice-runtime/venv/bin/python scripts/probe_navigation_nmea.py --run --passive-off --with-console
```

두 번째 명령은 인증된 getGps/setGps로 자동 갱신을 끌 수 있는지 검증한다. 제어가 확인된 경우에만 정상 문장과 차량 속도를 맞춰 보내며, 종료 시 원래 일곱 GPS 필드와 Console 값을 각각 복원·조회한다. 이 시험은 아직 실행하지 않았다. 성공이 보장된 해결책으로 소개하지 않는다.

공식 지원포럼의 [동일 증상 문의 #32](https://github.com/Pleos-Playground/pleos-playground-api/discussions/32)와 [시뮬레이션 문의 #29](https://github.com/Pleos-Playground/pleos-playground-api/discussions/29)에도 유사 사례가 있다. 개발자 재현 보고이며 현대의 공식 원인 확정이나 해결 답변은 아니다.
