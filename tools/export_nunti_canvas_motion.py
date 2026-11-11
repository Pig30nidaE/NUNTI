#!/usr/bin/env python3
"""Package the authored Nunti animation tracks and artwork for native Canvas."""

import argparse
import json
from pathlib import Path
from shutil import copyfile
import sys
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "prototypes" / "nunti_rive"
ASSETS = ROOT / "android" / "app" / "src" / "main" / "assets"
TRANSFORM_CLIPS = ("anticipation", "transform", "reveal")


def read_clips(authored):
    """Read the same rounded keys the original timeline exporter authored."""
    clips = {}
    xml = ElementTree.fromstring(f"<Clips>{authored}</Clips>")
    for clip in xml.findall("LinearAnimation"):
        if clip.attrib["fps"] != "60":
            raise ValueError(f"Canvas motion expects 60 fps: {clip.attrib['name']}")
        tracks = []
        for obj in clip.findall("KeyedObject"):
            joint = int(obj.attrib["objectId"].rsplit(":", 1)[1])
            for prop in obj.findall("KeyedProperty"):
                keys = [[int(key.attrib["frame"]), json.loads(key.attrib["value"])]
                        for key in prop.findall("KeyFrameDouble")]
                if keys:
                    tracks.append([joint, prop.attrib["property"], keys])
        clips[clip.attrib["name"]] = {"frames": int(clip.attrib["duration"]), "tracks": tracks}
    return clips


def export(assets):
    sys.path.insert(0, str(SOURCE))
    from motion import companion_motion, motion
    from rig import CHARACTERS, FACE_SLOTS, PLATES, SKINS

    data = {}
    for index, skin in enumerate(CHARACTERS, start=4):
        clips = read_clips(companion_motion(index, skin))
        if skin in SKINS:
            transform = read_clips(motion(SKINS.index(skin) + 1, skin))
            clips.update((name, transform[name]) for name in TRANSFORM_CLIPS)
        data[skin] = clips

    target = assets / "nunti-character" / "motion.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, separators=(",", ":")) + "\n", encoding="utf-8")

    # Keep the exact registered plates that were reviewed with the authored rig.
    plates = [Path("original-body.png"), *(Path(f"{skin}-head.png") for skin in SKINS)]
    plates.extend(Path("expressions") / f"{skin}-{name}.png" for skin in CHARACTERS for name in FACE_SLOTS)
    for plate in plates:
        destination = assets / "plates" / plate
        destination.parent.mkdir(parents=True, exist_ok=True)
        copyfile(PLATES / plate, destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, default=ASSETS)
    export(parser.parse_args().assets)
