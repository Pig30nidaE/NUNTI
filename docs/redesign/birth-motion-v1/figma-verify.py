"""Verify saved Figma Motion readbacks and their exact local source assets."""
from pathlib import Path
import hashlib
import json
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
metadata = json.loads((HERE / "figma-assets-and-render.json").read_text())
tracks = json.loads((HERE / "figma-manual-tracks.json").read_text())
checks = []

def check(name, condition):
    assert condition, name
    checks.append(name)

for item in metadata["assets"]:
    path = ROOT / metadata["sourceRoot"] / item["path"]
    check("source SHA256: " + item["path"], hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"])

for index, stage in enumerate(tracks["stages"]):
    name = "A" if index == 0 else "B"
    nodes = stage["nodes"]
    check(name + " 768-square / 4000ms", stage["width"] == stage["height"] == 768 and stage["timelines"][0]["duration"] == 4)
    core = next(n for n in nodes if n["type"] == "INSTANCE")
    check(name + " core fixed and fully visible", core["x"] == core["y"] == 0 and core["opacity"] == 1 and not core["tracks"])
    check(name + " inner source has no motion", all(not n["tracks"] for n in nodes if n["name"] == "고정 원화"))
    for prefix in ["02 /", "03 /"]:
        node = next(n for n in nodes if n["name"].startswith(prefix))
        times = [k["timelinePosition"] for k in node["tracks"]["OPACITY"]["keyframes"]]
        check(name + " expression timing " + prefix, times == [2.85, 3.05])
    for prefix, bounds, times in [("05 /", [367, 503, 70, 26], [1.7, 2.5]), ("06 /", [328, 403, 55, 11], [0.45, 1.3])]:
        node = next(n for n in nodes if n["type"] == "FRAME" and n["name"].startswith(prefix))
        field = "WIDTH" if index == 0 else "OPACITY"
        check(name + " reveal geometry " + prefix, [node[k] for k in ["x", "y", "width", "height"]] == bounds)
        check(name + " reveal timing/type " + prefix, list(node["tracks"]) == [field] and [k["timelinePosition"] for k in node["tracks"][field]["keyframes"]] == times)
    check(name + " glow scope", len([n for n in nodes if n["type"] == "ELLIPSE"]) == (2 if index == 0 else 0))
    for node in [n for n in nodes if n["type"] == "ELLIPSE"]:
        color = node["fills"][0]["color"]
        check(name + " warm-gold parity " + node["id"], [round(color[c] * 255) for c in ["r", "g", "b"]] == [249, 216, 146])
    for time in metadata["sampleTimes"]:
        check(name + " decoded frame " + time, Image.open(HERE / f"figma-{name.lower()}-frame-{time}.png").size == (768, 768))

report = {"status": "PASS", "scope": "Saved actual Figma API readbacks, local source hashes, decoded preview frame dimensions; not a live Figma call or Android runtime test.", "checks": checks}
(HERE / "figma-verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(f"PASS {len(checks)} saved-artifact checks")
