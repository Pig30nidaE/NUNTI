# Virtual Console 비활성 원인 조사

2026-11-02 18:15 KST 갱신, SERVER 읽기 전용 조사. `principle-fix-root-causes`를 적용해 보존 응답과 공식 문서, PM이 복원한 공식 이미지의 정적 프런트엔드, PM의 새 브라우저 접속 전후 JSON을 대조했다. SDK·AVD·앱·차량 상태는 변경하지 않았다. ADB 명령, 브라우저 실행, heartbeat·제어 API 호출도 하지 않았다.

새 환경에서는 공식 콘솔 브라우저 세션이 생기면서 DDS·gear bridge가 준비되고 Park 실제값이 나타난 것을 원본 JSON으로 확인했다. 과거와 같은 inactive 응답이 브라우저 없는 상태에서 재현됐고, 정상 브라우저 접속 후 `web-activation` 성공으로 바뀌었다. 과거 실패 원인을 단순한 DDS 설치 누락으로 해석할 근거는 없다. 이 비교의 완료 범위는 콘솔 활성화·Park 준비이며 주행 제어·UX·앱 동작은 별도다.

## 새 실행에서 확인한 변화

PM 소유 `vehicle-state-before-browser.json`과 `vehicle-state-browser-open.json`을 직접 읽었다. 원본 해시와 서버 증거 사본을 [비교 결과](console-state-comparison.json)에 보존했고 [비교 스크립트](compare_console_states.py)는 파일만 읽는다. 실행 exit 0이다.

| 값 | 브라우저 접속 전 | 공식 브라우저 접속 후 |
| --- | --- | --- |
| browser.active / clients | false / 0 | true / 1 |
| controls.emulator_active | false | true |
| controls.dds_ready.all | false | true |
| gear.bridge_ready | false | true |
| gear.actual | null | Park, source=activation |
| availability.available·attempted·strict_success·effective_success | 모두 false | 모두 true |
| availability.source | not-run | web-activation |
| direct_vhal_write | false | false |

`controls.input_active`는 접속 후에도 false다. 이 값이 false라는 이유만으로 Web 콘솔 준비 실패로 판정하면 안 된다. 새 JSON에서 브라우저 세션·DDS·gear 활성화는 별도로 확인됐다.

## 확인된 근거

- 보존된 `vehicle-state-inactive.json`은 `browser.active=false`, `clients=0`, `timeout_ms=3000`이다. 같은 응답의 `controls.emulator_active=false`, `gear.bridge_ready=false`, `controls.dds_ready.all=false`였고 `availability.attempted=false`, `source=not-run`이었다. 이 값은 브라우저가 붙지 않은 idle 상태와도 맞는다.
- PM이 복원한 공식 `vendor.img`에서 `sendBrowserHeartbeat` 함수를 직접 읽었다. 콘솔 화면은 `/browser/session`으로 즉시 POST한 다음 1,000ms마다 반복하고, pagehide·beforeunload 때 closing flag를 보낸다. JS를 실행한 결과가 아니라 배포된 정적 코드의 확인이다.
- 같은 바이너리에 `setWebSessionActive`, `browserMonitorLoop`, `updateBrowserSession`, `pruneBrowserSessions`, DDS·GearBridge의 `setWebActive`, `browser-active`·`browser-inactive`·`client_timeout` 표식이 존재한다. 정적 조사 단계에서는 연결 가능성의 근거였고, 이후 PM의 새 전후 JSON에서 `web-activation`과 DDS·gear 준비 변화가 확인됐다.
- 이미지의 Three.js·addon import map과 highway module 경로는 콘솔의 로컬 경로다. 3D 화면에는 WebGL 2 요구 메시지가 있지만, 외부 CDN이나 별도 host DDS 설치가 정상 초기화의 필수라는 근거는 찾지 못했다. 브라우저 heartbeat 유지와 3D 시각화 성공도 별도로 관찰해야 한다.

[정적 검사 결과](console-static-analysis.json)에 이미지 SHA-256, 함수 byte offset·해시, 검출 항목과 과거 상태 요약을 보존했다. `vendor.img` SHA-256은 `12ff02d62d57bb8a7466be6450ebbd6e613ef99238e03283cdb0f281cc56dd67`이다. [검사 스크립트](inspect_console_image.py)는 이미지 bytes만 읽고 API·ADB·JS를 실행하지 않는다. 실행은 [console-static-analysis-final.log](console-static-analysis-final.log) 및 기존 commands.jsonl에 기록했으며 exit 0이다.

## 공식 절차와 PM의 다음 확인

공식 설치 문서는 Pleos 2.1.0/API34, cold boot, RAM 4GB를 안내한다. 현재 PM AVD의 `fastboot.forceColdBoot=yes`, `fastboot.forceFastBoot=no`, `hw.ramSize=4096`을 읽어 확인했다. [공식 설치 문서](https://document.pleos.ai/en/docs/connect/guide/getting-started/application-development/setup-connect-sdk-emulator)

공식 구성 문서는 quick boot에서는 VHAL을 사용할 수 없다고 명시한다. [공식 AVD 구성 문서](https://document.pleos.ai/en/docs/connect/guide/getting-started/application-development/configure-pleos-connect-emulator)

공식 Virtual Console 절차는 에뮬레이터를 실행하고 ADB 8088 forwarding을 설정한 뒤 PC 브라우저에서 `http://127.0.0.1:8088/`에 접속하는 순서다. 문제 해결 항목도 이미지 버전·ADB 연결·forwarding·PC 포트 충돌·브라우저 재접속을 확인하도록 한다. 별도 host daemon이나 Docker/DDS 설치 명령은 이 가이드에 없다. [공식 Virtual Console 설정](https://document.pleos.ai/en/docs/connect/guide/getting-started/application-development/use-vehicle-emulator)

공식 정상 경로와 남은 확인은 다음과 같다.

1. 부팅 완료·ADB 연결·forwarding을 확인하고 브라우저 접속 전 상태를 보존한다. PM이 완료했다.
2. 공식 콘솔 전체 화면을 PC 브라우저로 열고 탭을 유지한다. 정적 HTML을 GET만 하는 것은 heartbeat JS 실행과 다르다. PM이 접속을 수행했다.
3. browser client·active, emulator active, gear bridge·DDS ready를 비교한다. 이번 새 비교에서 모두 준비 상태로 바뀐 것을 확인했다. 향후 같은 증상이 생기면 우선 탭·heartbeat를 확인하고, 세션 활성인데도 준비되지 않을 때 서비스 로그를 조사한다.
4. PM이 공식 Emulation Controls에서 기어·속도·복귀를 조작하고 실제 Car API·UX·앱 정책 결과를 확인한다. 공식 사용자 가이드는 Motion의 Gear Selection과 도메인별 조작, 에뮬레이터·앱 결과 확인을 안내한다. [공식 사용자 가이드](https://document.pleos.ai/en/docs/pleos-only/app-test-guide/virtual-console-guide)

확인된 사실은 배포 프런트엔드의 heartbeat 구현, 새 환경의 브라우저 부재 시 inactive 재현, 접속 후 DDS·gear·Park 준비와 `web-activation` 성공이다. 과거에도 동일한 세션 부재가 inactive의 원인이었다는 해석은 이 증거로 강하게 뒷받침되지만 과거 세션의 브라우저 동작 이력을 새로 관찰한 것은 아니다. 브라우저 탭을 닫은 뒤의 3초 timeout 동작은 이번에 시험하지 않았고, D·속도·P 복귀와 실제 UX·TTS 반응도 이 비교에 포함하지 않는다. SERVER는 새 localhost endpoint에 직접 접근하지 않고 PM이 남긴 두 원본 파일만 읽었다.
