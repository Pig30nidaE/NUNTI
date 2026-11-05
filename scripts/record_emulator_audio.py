#!/usr/bin/env python3
"""Capture authenticated localhost Android Emulator speaker PCM, not a microphone.

Requires grpcio-tools only for capture/--inspect. WAV analysis uses the stdlib.
Bindings are generated from the installed emulator's actual proto, not a copy.
"""

import argparse
import array
import hashlib
import importlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import wave


ROOT = Path(__file__).resolve().parents[1]
METHOD = "/android.emulation.control.EmulatorController/streamAudio"


def read_discovery(path):
    props = {}
    for line in path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith(("#", ";")):
            key, value = line.split("=", 1)
            props[key.strip()] = value.strip()
    return props


def find_discovery(serial, explicit=None):
    serial_port = serial.removeprefix("emulator-")
    if not serial.startswith("emulator-") or not serial_port.isdigit():
        raise ValueError("--serial must be emulator-<console port>")
    if explicit:
        paths = [explicit]
    else:
        roots = [Path.home() / "Library/Caches/TemporaryItems/avd/running"]
        for base in (os.getenv("XDG_RUNTIME_DIR"), os.getenv("TMPDIR")):
            if base:
                roots.append(Path(base) / "avd/running")
        roots.append(Path(tempfile.gettempdir()) / ("android-" + os.getenv("USER", "")) / "avd/running")
        paths = [p for root in roots for p in root.glob("pid_*.ini")]
    matches = []
    for path in paths:
        props = read_discovery(path)
        if props.get("port.serial") != serial_port:
            continue
        if not explicit:
            match = re.fullmatch(r"pid_(\d+)(?:_info)?\.ini", path.name)
            if not match:
                continue
            try:
                os.kill(int(match[1]), 0)
            except ProcessLookupError:
                continue
            except PermissionError:
                # Some local sandboxes cannot probe another process. The
                # authenticated connection still has to succeed before capture.
                pass
        matches.append((path, props))
    if len(matches) != 1:
        raise ValueError("Expected exactly one matching discovery INI for " + serial)
    path, props = matches[0]
    port = int(props.get("grpc.port", "0"))
    if not 1 <= port <= 65535:
        raise ValueError("Discovery INI has no valid grpc.port")
    if not props.get("grpc.token"):
        raise ValueError("Discovery has no grpc.token. Auth is required; do not use an open -grpc port.")
    return path, props, "127.0.0.1:" + str(port)


def bindings(sdk, output):
    import grpc_tools
    from grpc_tools import protoc

    proto_dir = sdk / "emulator/lib"
    proto = proto_dir / "emulator_controller.proto"
    builtins = Path(grpc_tools.__file__).parent / "_proto"
    result = protoc.main([
        "grpc_tools.protoc", "-I" + str(proto_dir), "-I" + str(builtins),
        "--python_out=" + str(output), str(proto),
    ])
    if result:
        raise ValueError("Could not compile installed emulator_controller.proto")
    sys.path.insert(0, str(output))
    pb = importlib.import_module("emulator_controller_pb2")
    service = pb.DESCRIPTOR.services_by_name["EmulatorController"]
    method = service.methods_by_name["streamAudio"]
    if not method.server_streaming or method.client_streaming:
        raise ValueError("Unexpected streamAudio method shape")
    return pb, hashlib.sha256(proto.read_bytes()).hexdigest()


def analyze_wav(path):
    with wave.open(str(path), "rb") as source:
        channels, width, rate, frames = source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getnframes()
        if width != 2 or source.getcomptype() != "NONE":
            raise ValueError("Analysis supports uncompressed signed 16-bit PCM WAV only")
        nonzero = peak = square_sum = sample_count = 0
        first_frame = last_frame = None
        while True:
            raw = source.readframes(48000)
            if not raw:
                break
            samples = array.array("h", raw)
            if sys.byteorder != "little":
                samples.byteswap()
            for index, sample in enumerate(samples):
                absolute = abs(sample)
                peak = max(peak, absolute)
                square_sum += sample * sample
                if sample:
                    frame = (sample_count + index) // channels
                    if first_frame is None:
                        first_frame = frame
                    last_frame = frame
                    nonzero += 1
            sample_count += len(samples)
    return {
        "wav": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "sampleRateHz": rate, "channels": channels, "sampleWidthBytes": width,
        "frames": frames, "pcmDurationSeconds": frames / rate,
        "nonzeroSamples": nonzero, "peak": peak,
        "rms": math.sqrt(square_sum / sample_count) if sample_count else 0,
        "firstNonzeroPcmSeconds": first_frame / rate if first_frame is not None else None,
        "lastNonzeroPcmSeconds": last_frame / rate if last_frame is not None else None,
        "evidenceLevel": "RAW_PCM_ONLY_NOT_SPEECH_ACCEPTANCE",
        "humanListeningPerformed": False,
        "interpretation": "Nonzero PCM proves an output signal only. Not speech attribution, pronunciation, quality, or wall-clock latency.",
    }


def capture(args):
    import grpc

    discovery, props, target = find_discovery(args.serial, args.discovery)
    if props.get("grpc.server_cert") or props.get("grpc.tls"):
        raise ValueError("TLS discovery requires a separately reviewed certificate configuration; refusing plaintext fallback")
    output = args.output.resolve()
    packets_path = output.with_suffix(".packets.jsonl")
    summary_path = output.with_suffix(".summary.json")
    for path in (output, packets_path, summary_path):
        if path.exists():
            raise ValueError("Refusing to overwrite existing capture: " + str(path))
    output.parent.mkdir(parents=True, exist_ok=True)
    channel = None
    call = None
    packet_count = frame_count = 0
    outcome = "UNKNOWN"
    started_ns = started_epoch_ns = ended_ns = None
    with tempfile.TemporaryDirectory(prefix="nunti-audio-proto-") as tmp:
        pb, proto_sha = bindings(args.sdk, Path(tmp))
        channel = grpc.insecure_channel(target)
        try:
            try:
                grpc.channel_ready_future(channel).result(timeout=5)
            except grpc.FutureTimeoutError:
                raise ValueError("Local emulator gRPC endpoint was not reachable within 5 seconds") from None
            rpc = channel.unary_stream(
                METHOD, request_serializer=pb.AudioFormat.SerializeToString,
                response_deserializer=pb.AudioPacket.FromString,
            )
            requested = pb.AudioFormat(samplingRate=args.rate, channels=pb.AudioFormat.Stereo, format=pb.AudioFormat.AUD_FMT_S16)
            started_ns, started_epoch_ns = time.monotonic_ns(), time.time_ns()
            call = rpc(requested, timeout=args.seconds, metadata=(("authorization", "Bearer " + props["grpc.token"]),))
            # Timers are captured on packet receipt, before PCM processing/file IO.
            print(json.dumps({"state": "CAPTURING", "serial": args.serial, "target": target, "seconds": args.seconds}), flush=True)
            with wave.open(str(output), "wb") as dest, packets_path.open("x") as packets:
                dest.setnchannels(2)
                dest.setsampwidth(2)
                dest.setframerate(args.rate)
                try:
                    for packet in call:
                        receipt_ns, receipt_epoch_ns = time.monotonic_ns(), time.time_ns()
                        fmt = packet.format
                        if fmt.samplingRate not in (0, args.rate) or fmt.channels != pb.AudioFormat.Stereo or fmt.format != pb.AudioFormat.AUD_FMT_S16:
                            raise ValueError("Unexpected packet PCM format; refusing mislabelled WAV")
                        if len(packet.audio) % 4:
                            raise ValueError("PCM packet is not aligned to stereo 16-bit frames")
                        frames = len(packet.audio) // 4
                        samples = array.array("h", packet.audio)
                        if sys.byteorder != "little":
                            samples.byteswap()
                        packets.write(json.dumps({
                            "index": packet_count, "captureTimestampEpochUs": packet.timestamp,
                            "receivedMonotonicNs": receipt_ns, "receivedEpochNs": receipt_epoch_ns,
                            "pcmStartFrame": frame_count, "frames": frames, "bytes": len(packet.audio),
                            "peak": max((abs(value) for value in samples), default=0),
                            "nonzeroSamples": sum(value != 0 for value in samples),
                        }, separators=(",", ":")) + "\n")
                        dest.writeframesraw(packet.audio)
                        packet_count += 1
                        frame_count += frames
                    outcome = "STREAM_ENDED"
                except grpc.RpcError as error:
                    outcome = error.code().name
                    if error.code() != grpc.StatusCode.DEADLINE_EXCEEDED:
                        # Never print error.details(): server errors may echo credentials.
                        raise ValueError("streamAudio RPC failed: " + outcome) from None
                except KeyboardInterrupt:
                    outcome = "INTERRUPTED"
                    call.cancel()
                finally:
                    ended_ns = time.monotonic_ns()
        finally:
            if call is not None:
                call.cancel()
            if channel is not None:
                channel.close()
    result = analyze_wav(output)
    result.update({
        "source": "AUTHENTICATED_EMULATOR_SPEAKER_STREAM", "serial": args.serial,
        "target": target, "discoveryFile": str(discovery), "auth": "EXISTING_DISCOVERY_TOKEN_REDACTED",
        "protoSha256": proto_sha, "packetCount": packet_count, "outcome": outcome,
        "startedMonotonicNs": started_ns, "startedEpochNs": started_epoch_ns,
        "wallDurationSeconds": (ended_ns - started_ns) / 1e9,
        "packetTimingFile": str(packets_path),
        "timingLimit": "WAV concatenates delivered packets without filling gaps. Use packet timestamps for timing analysis. Other guest audio is also captured.",
    })
    summary_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["nonzeroSamples"] else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", type=Path, default=Path(os.getenv("ANDROID_HOME", ROOT / ".local/pm-tools/sdk")))
    parser.add_argument("--serial", default="emulator-5554")
    parser.add_argument("--discovery", type=Path, help="Exact existing emulator discovery INI; never logged contents")
    parser.add_argument("--output", type=Path, help="New WAV file; companion packet JSONL and summary JSON are written")
    parser.add_argument("--seconds", type=float, default=20, help="Capture stream deadline, 1..300 seconds")
    parser.add_argument("--rate", type=int, choices=(16000, 24000, 44100, 48000), default=48000)
    parser.add_argument("--inspect", action="store_true", help="Compile actual SDK proto and report dependency/runtime availability without capture")
    parser.add_argument("--analyze", type=Path, metavar="WAV", help="Analyze an existing PCM WAV without grpc dependencies")
    args = parser.parse_args()
    if not 1 <= args.seconds <= 300:
        parser.error("--seconds must be between 1 and 300")
    try:
        if args.analyze:
            print(json.dumps(analyze_wav(args.analyze), ensure_ascii=False, indent=2))
            return 0
        if args.inspect:
            with tempfile.TemporaryDirectory(prefix="nunti-audio-proto-") as tmp:
                _, proto_sha = bindings(args.sdk, Path(tmp))
            result = {"protoSha256": proto_sha, "streamAudioContract": "VALID", "grpcio": importlib.metadata.version("grpcio"), "grpcio-tools": importlib.metadata.version("grpcio-tools"), "capturePerformed": False}
            try:
                _, _, target = find_discovery(args.serial, args.discovery)
                result.update({"discovery": "PRESENT_WITH_TOKEN", "target": target})
            except ValueError as error:
                result.update({"discovery": "UNAVAILABLE", "reason": str(error)})
            print(json.dumps(result, indent=2))
            return 0
        if not args.output:
            parser.error("--output is required for capture")
        return capture(args)
    except ImportError:
        print("Missing grpcio-tools. Install into .local/voice-runtime/venv; see tts-runtime-notes.md.", file=sys.stderr)
    except (ValueError, OSError, wave.Error) as error:
        print(str(error), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
