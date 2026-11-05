"""Read official vendor image bytes without executing code or contacting the emulator."""

from datetime import datetime
import hashlib
import json
import mmap
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[5]
IMAGE = Path("/Users/pig30nidae/NUNTI/.local/pm-tools/sdk/system-images/android-34/android-automotive/arm64-v8a/vendor.img")


def main():
    with IMAGE.open("rb") as stream:
        image_sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
        with mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
            start = data.find(b"function sendBrowserHeartbeat(closing=false)")
            assert start >= 0
            end = data.find(b"const gearButtons", start)
            assert end > start
            frontend = data[start:end]
            checks = {
                "browserSessionPath": b'"/browser/session?client="' in frontend,
                "usesPost": b'method:"POST"' in frontend,
                "sendsImmediately": b"sendBrowserHeartbeat();" in frontend,
                "interval1000ms": b"setInterval(()=>sendBrowserHeartbeat(false),1000)" in frontend,
                "closingOnPagehide": b'"pagehide",()=>sendBrowserHeartbeat(true)' in frontend,
                "closingOnBeforeunload": b'"beforeunload",()=>sendBrowserHeartbeat(true)' in frontend,
                "hasClosingFlag": b'"&closing=1"' in frontend,
            }
            assert all(checks.values())
            symbols = [
                "browser-active", "browser-inactive", "client_timeout",
                "setWebSessionActive", "updateBrowserSession", "pruneBrowserSessions",
                "browserMonitorLoop", "kBrowserSessionTimeoutMs",
                "_ZN16vehicle_emulator7runtime10DdsRuntime12setWebActiveEb",
                "_ZN16vehicle_emulator7vehicle10GearBridge12setWebActiveEb",
            ]
            symbols_present = {symbol: data.find(symbol.encode()) >= 0 for symbol in symbols}
            assets = {
                "threeImportMapUsesLocalPath": data.find(b'"three":"/vendor/three/three.module.min.js"') >= 0,
                "threeAddonsUseLocalPath": data.find(b'"three/addons/":"/vendor/three/addons/"') >= 0,
                "highwayModuleUsesLocalPath": data.find(b"import('/highway-view.js')") >= 0,
                "webgl2RendererMessage": data.find(b"WebGL 2 is required") >= 0,
            }
    previous = json.loads((ROOT / "docs/architecture/validation-evidence/pleos-runtime/vehicle-state-inactive.json").read_text())
    result = {
        "inspectedAt": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
        "operations": "Read-only image bytes and preserved JSON. No executable JavaScript, browser session, emulator API, ADB, or state-changing command was run.",
        "image": str(IMAGE),
        "imageBytes": IMAGE.stat().st_size,
        "imageSha256": image_sha256,
        "frontendFunctionByteOffset": start,
        "frontendFunctionBytes": len(frontend),
        "frontendFunctionSha256": hashlib.sha256(frontend).hexdigest(),
        "checks": checks,
        "symbolsPresent": symbols_present,
        "visualizationAssets": assets,
        "pastObservedState": {
            "browser": previous["browser"],
            "controlsEmulatorActive": previous["controls"]["emulator_active"],
            "controlsDdsReady": previous["controls"]["dds_ready"],
            "gearBridgeReady": previous["gear"]["bridge_ready"],
            "availability": previous["availability"],
        },
        "interpretation": "The shipped frontend maintains a browser session with a one-second POST heartbeat. The past idle response had no browser clients. Browser absence is a supported explanation for inactive state, but a live before/after comparison by PM is needed to confirm recovery and DDS readiness.",
    }
    destination = Path(__file__).with_name("console-static-analysis.json")
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
