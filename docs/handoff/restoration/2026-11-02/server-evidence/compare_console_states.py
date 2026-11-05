"""Read and compare PM-owned snapshots without contacting the emulator."""

from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
from zoneinfo import ZoneInfo


def main():
    root = Path("/Users/pig30nidae/NUNTI/docs/handoff/restoration/2026-11-02/pm-evidence")
    evidence = Path(__file__).resolve().parent
    snapshots = {}
    for name in ("vehicle-state-before-browser.json", "vehicle-state-browser-open.json"):
        source = root / name
        value = json.loads(source.read_text())
        copy = evidence / ("console-" + name)
        shutil.copyfile(source, copy)
        snapshots[name] = {
            "source": str(source),
            "copy": copy.name,
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "browser": value["browser"],
            "gear": value["gear"],
            "controls": {key: value["controls"].get(key) for key in ("source", "timestamp_ms", "emulator_active", "input_active", "dds_ready")},
            "availability": value["availability"],
        }
    before, opened = snapshots.values()
    assert before["browser"]["active"] is False and before["browser"]["clients"] == 0
    assert opened["browser"]["active"] is True and opened["browser"]["clients"] == 1
    for key in ("emulator_active",):
        assert before["controls"][key] is False and opened["controls"][key] is True
    assert before["controls"]["dds_ready"]["all"] is False
    assert opened["controls"]["dds_ready"]["all"] is True
    assert before["gear"]["bridge_ready"] is False and opened["gear"]["bridge_ready"] is True
    assert before["gear"]["actual"] is None and opened["gear"]["actual"]["value"] == "Park"
    assert opened["availability"]["source"] == "web-activation"
    assert opened["availability"]["strict_success"] is True
    assert opened["availability"]["direct_vhal_write"] is False
    result = {
        "checkedAt": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
        "operations": "Read PM snapshots, write copies and comparison into SERVER evidence. No ADB, browser, or HTTP requests.",
        "ok": True,
        "snapshots": snapshots,
        "confirmed": "In the restored environment the official browser session activation coincides with emulator active, DDS ready, gear bridge ready, Park actual state and availability web-activation success.",
        "limits": "No gear change, speed, Car API observation, UX restriction or app response is validated by this comparison.",
    }
    (evidence / "console-state-comparison.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
