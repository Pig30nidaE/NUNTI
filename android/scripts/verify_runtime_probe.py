import argparse
import json
import subprocess
import time
from pathlib import Path

parser = argparse.ArgumentParser(
    description="Verify the installed debug-only Pleos runtime probe."
)
parser.add_argument("--adb", default="adb")
parser.add_argument("--serial", default="emulator-5554")
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
adb = [args.adb, "-s", args.serial]
package = "ai.nunti.avatar.demo"
component = package + "/ai.nunti.app.RuntimeProbeActivity"


def run(*args):
    return subprocess.run(
        adb + list(args), check=True, capture_output=True, text=True
    ).stdout


def start(*args):
    return run(
        "shell",
        "am",
        "start",
        "-W",
        "-f",
        "0x14000000",
        "-n",
        component,
        "--ez",
        "confirm_quiet_test",
        "true",
        *args,
    )


def events():
    return [
        json.loads(x)
        for x in run(
            "shell",
            "run-as",
            package,
            "--user",
            "10",
            "cat",
            "files/runtime-probe.jsonl",
        ).splitlines()
    ]


def wait_for(offset, predicate):
    end = time.monotonic() + 10
    while time.monotonic() < end:
        found = [e for e in events()[offset:] if predicate(e)]
        if found:
            return found[-1]
        time.sleep(0.2)
    raise AssertionError("Expected event not received")


hardware = run("shell", "getprop", "ro.hardware").strip()
assert hardware in {"ranchu", "goldfish"}, "Refusing a non-emulator target"
assert run("shell", "getprop", "ro.build.fingerprint").startswith("Pleos/"), (
    "Pleos image required"
)
start()
results = []
for action in ["stop", "background"]:
    run("shell", "am", "force-stop", package)
    start()
    time.sleep(0.7)
    count = len(events())
    start("--es", "probe_action", "speak")
    began = wait_for(count, lambda e: e.get("status") == "STARTED")
    if action == "stop":
        start("--es", "probe_action", "stop")
    else:
        run("shell", "am", "start", "-W", "-n", package + "/ai.nunti.app.MainActivity")
    cancelled = wait_for(
        count,
        lambda e, request_id=began["requestId"]: (
            e.get("requestId") == request_id and e.get("status") == "CANCELLED"
        ),
    )
    expected = "USER_CANCELLED" if action == "stop" else "BACKGROUND"
    assert cancelled["reason"] == expected, (action, cancelled)
    results.append({"case": action, "started": began, "terminal": cancelled})
    start()
    time.sleep(0.3)
    count = len(events())
    start("--es", "probe_action", "speak")
    rejected = wait_for(count, lambda e: e.get("status") == "REJECTED")
    assert rejected["reason"] == "REPEATED_TEXT", rejected
    results.append({"case": "repeat_after_" + action, "terminal": rejected})
run("shell", "am", "force-stop", package)
start()
out = args.output
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
print(json.dumps(results, ensure_ascii=False))
