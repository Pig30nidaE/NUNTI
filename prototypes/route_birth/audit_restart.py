#!/usr/bin/env python3
"""Observe immutable READY artifacts before/after a normal worker process restart."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from generator import canonical, digest
from worker import file_sha, read_sealed


def get(url, body=None):
    request = urllib.request.Request(url, data=canonical(body).encode() if body is not None else None,
                                    headers={"Content-Type": "application/json"} if body is not None else {})
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.status, response.read()


def write_new(path, data):
    with path.open("xb") as target:
        target.write(data)


def json_new(path, value):
    write_new(path, (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("before", "after"))
    parser.add_argument("--workspace", type=Path, default=ROOT / ".local/route-birth")
    parser.add_argument("--output", type=Path, default=HERE / "restart-01")
    parser.add_argument("--url", default="http://127.0.0.1:8766")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    destination = args.output / args.phase
    destination.mkdir()
    jobs = args.workspace / "jobs"
    job_files = {str(p.relative_to(jobs)): file_sha(p) for p in sorted(jobs.rglob("*")) if p.is_file()}
    assert len(job_files) == 40, len(job_files)
    ids = sorted(p.name for p in jobs.iterdir() if p.is_dir())
    assert len(ids) == 5
    pid_output = subprocess.check_output(["/usr/sbin/lsof", "-t", "-nP", "-iTCP:8766", "-sTCP:LISTEN"], text=True).strip().splitlines()
    pids = sorted(set(int(value) for value in pid_output))
    assert len(pids) == 1
    command = subprocess.check_output(["/bin/ps", "-p", str(pids[0]), "-o", "command="], text=True).strip()
    assert "prototypes/route_birth/worker.py serve --workspace .local/route-birth --port 8766" in command
    status, health = get(args.url + "/health")
    assert status == 200 and json.loads(health) == {"status": "ok", "version": "route-born-1"}
    responses, audios, retry_results = {}, {}, {}
    for request_id in ids:
        plan = read_sealed(jobs / request_id / "plan.json")
        status, raw = get(args.url + "/v1/journeys/" + request_id)
        result = json.loads(raw)
        assert status == 200 and result["state"] == "READY" and result["requestId"] == request_id
        artifact = result["artifact"]
        assert artifact == read_sealed(jobs / request_id / "result.json")
        assert digest(json.loads(artifact["inputCanonical"])) == artifact["inputSha256"] == plan["inputSha256"]
        responses[request_id] = hashlib.sha256(raw).hexdigest()
        write_new(destination / (request_id + "-get.json"), raw)
        for clip in artifact["voiceManifest"]["clips"]:
            audio_status, audio = get(args.url + "/v1/journeys/" + request_id + "/audio/" + clip["audioPath"])
            sha = hashlib.sha256(audio).hexdigest()
            assert audio_status == 200 and sha == clip["audioSha256"]
            audios[request_id + "/" + clip["audioPath"]] = sha
        if args.phase == "after":
            retry_status, retry_raw = get(args.url + "/v1/journeys", plan["request"])
            assert retry_status == 200 and retry_raw == raw
            retry_results[request_id] = {"status": retry_status, "state": json.loads(retry_raw)["state"], "responseSha256": hashlib.sha256(retry_raw).hexdigest()}
            write_new(destination / (request_id + "-retry.json"), retry_raw)
    assert len(audios) == 15
    assert job_files == {str(p.relative_to(jobs)): file_sha(p) for p in sorted(jobs.rglob("*")) if p.is_file()}
    observation = {"phase": args.phase, "pid": pids[0], "command": command, "httpReadyResponseSha256": responses, "httpAudioSha256": audios,
                   "jobFileSha256": job_files, "sourceSha256": {p.name: file_sha(p) for p in (HERE / "worker.py", HERE / "generator.py")}, "retries": retry_results}
    json_new(args.output / (args.phase + ".json"), observation)
    if args.phase == "after":
        before = json.loads((args.output / "before.json").read_text())
        for key in ("httpReadyResponseSha256", "httpAudioSha256", "jobFileSha256", "sourceSha256"):
            assert before[key] == observation[key], key
        assert before["pid"] != observation["pid"]
        report = {"status": "PASS_ACTUAL_PROCESS_RESTART_FIVE_READY_FIFTEEN_WAV_IMMUTABLE_RETRIES", "oldPid": before["pid"], "newPid": observation["pid"],
                  "normalCliUnchanged": before["command"] == observation["command"], "readyResponseCount": len(responses), "wavCount": len(audios), "jobFilesUnchanged": len(job_files),
                  "sameCanonicalInputRetriesReady": len(retry_results), "allResponseAndWavHashesUnchanged": True, "workerAndGeneratorSourceUnchanged": True,
                  "limits": "No model-call counter is exposed or instrumented. This proves unchanged committed results and audio were returned after an actual normal process restart; it does not directly count model render calls."}
        json_new(args.output / "verification.json", report)
        print(canonical(report))
    else:
        print(canonical({"phase": "before", "pid": observation["pid"], "jobs": len(ids), "wavCount": len(audios), "jobFileCount": len(job_files)}))


if __name__ == "__main__":
    main()
