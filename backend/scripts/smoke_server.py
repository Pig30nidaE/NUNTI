"""Real loopback HTTP + process restart smoke test, entirely synthetic data."""

import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx


def main():
    with tempfile.TemporaryDirectory(prefix="nunti-smoke-") as directory:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        token = secrets.token_urlsafe(32)
        env = os.environ | {
            "NUNTI_AUTH_TOKENS": json.dumps({token: "smoke"}),
            "NUNTI_DEMO_TOKEN": token,
            "NUNTI_DB_PATH": str(Path(directory) / "server.sqlite3"),
            "NUNTI_SYNC_ENABLED": "true",
            "NUNTI_ENABLE_MOCKS": "true",
            "NUNTI_REQUIRE_HTTPS": "false",
        }
        url = f"http://127.0.0.1:{port}"
        for iteration in range(2):
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "nunti.api:create_app",
                    "--factory",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--no-access-log",
                    "--log-level",
                    "error",
                ],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            try:
                with httpx.Client(
                    base_url=url, headers={"Authorization": f"Bearer {token}"}
                ) as client:
                    for _ in range(100):
                        try:
                            if client.get("/health", timeout=0.2).status_code == 200:
                                break
                        except httpx.TransportError:
                            pass
                        if process.poll() is not None:
                            raise RuntimeError("Server failed to start")
                        time.sleep(0.05)
                    else:
                        raise RuntimeError("Server startup timed out")
                    if iteration == 0:
                        subprocess.run(
                            [
                                sys.executable,
                                "-m",
                                "nunti.demo",
                                "--url",
                                url,
                                "--consent",
                                "--outbox",
                                str(Path(directory) / "outbox.sqlite3"),
                            ],
                            env=env,
                            check=True,
                            timeout=30,
                        )
                    trip = client.get("/v1/trips/trip-09-reconnect").json()["data"]
                    assert (trip["eventCount"], trip["emotionCount"], trip["reportAvailable"]) == (
                        1,
                        1,
                        True,
                    )
                    assert client.get("/docs").status_code == 200
                    assert client.get("/openapi.json").status_code == 200
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                process.stderr.close()
        print(
            "PASS: real HTTP, simulated disconnect/lost ACK, process restart and persisted records"
        )


if __name__ == "__main__":
    main()
