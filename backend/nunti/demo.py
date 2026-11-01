"""Run a fixed mock scenario against a running server with simulated transport loss."""

import argparse
import os
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .demo_outbox import DemoOutbox
from .fixtures import load_scenario, scenario_names


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--scenario", choices=scenario_names(), default="09-reconnect")
    parser.add_argument("--consent", action="store_true")
    parser.add_argument("--outbox", type=Path, default=Path("data/demo-outbox.sqlite3"))
    args = parser.parse_args()
    target = urlparse(args.url)
    if target.scheme != "https" and not (
        target.scheme == "http" and target.hostname in {"127.0.0.1", "localhost", "::1"}
    ):
        parser.error("Use HTTPS, or loopback HTTP for development")
    token = os.environ.get("NUNTI_DEMO_TOKEN")
    if not token or not args.consent:
        parser.error("Set NUNTI_DEMO_TOKEN and explicitly pass --consent for synthetic data upload")
    scenario = load_scenario(args.scenario)
    outbox = DemoOutbox(args.outbox, consent=True)
    with httpx.Client(
        base_url=args.url, headers={"Authorization": f"Bearer {token}"}, timeout=5
    ) as client:
        virtual_time = 0
        for index, step in enumerate(scenario["steps"]):
            if step["method"] == "GET":
                result = client.get(step["path"])
                result.raise_for_status()
                print(step["method"], step["path"], result.status_code)
                continue
            outbox.enqueue(f"{args.scenario}:{index}", step["method"], step["path"], step["body"])
            fault = step.get("transportFault")

            def sender(method, path, **kwargs):
                nonlocal fault
                current, fault = fault, None
                if current == "before_send":
                    raise httpx.ConnectError("Simulated offline connection")
                response = client.request(method, path, **kwargs)
                if current == "after_commit":
                    raise httpx.ReadError("Simulated lost acknowledgment")
                return response

            for _ in range(10):
                state = outbox.pump_once(sender, at=virtual_time)
                virtual_time += 121  # Virtual clock advances; this is a deterministic mock replay.
                if state == "acknowledged":
                    print(step["method"], step["path"], state)
                    break
                if state == "blocked":
                    raise SystemExit("Outbox blocked; inspect credentials or contract conflict")
            else:
                raise SystemExit("Transport unavailable; pending requests retained")
    print("Mock scenario complete; no actual vehicle SDK or TTS invoked.")


if __name__ == "__main__":
    main()
