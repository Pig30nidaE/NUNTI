"""Register approved-reference image edits and export the Skin V2 runtime layers."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'artifacts/nunti-visual-polish/final-source'
OUTPUT = ROOT / 'prototypes/avatar_generator/skin-v2/polish'
SIZE = 768
EYE_ANCHORS = (314, 465, 273)
SOLE = 721
EXPRESSION = (264, 189, 515, 365)  # Exclusive right/bottom.

Point = tuple[int, int]


@dataclass(frozen=True)
class Plate:
    # Eye centers, their shared height and the lower edge of the soles in the source.
    anchors: tuple[int, int, int, int]
    collar: tuple[Point, ...]
    accessories: tuple[tuple[Point, ...], ...]


PLATES = {
    'sea': Plate(
        (418, 620, 364, 991),
        ((0, 494), (307, 494), (343, 511), (369, 522), (409, 524), (451, 530),
         (509, 532), (563, 531), (608, 526), (645, 522), (674, 509), (703, 494), (1024, 494)),
        (((322, 719), (348, 691), (395, 684), (468, 629), (491, 626), (499, 641),
          (430, 699), (441, 722), (444, 766), (429, 786), (407, 800), (344, 800), (320, 771)),),
    ),
    'city': Plate(
        (420, 617, 362, 983),
        ((0, 484), (293, 484), (334, 484), (368, 502), (398, 509), (438, 519),
         (487, 531), (521, 537), (547, 535), (568, 528), (601, 519), (631, 510),
         (651, 499), (688, 484), (1024, 484)),
        (((331, 675), (354, 655), (400, 650), (465, 664), (620, 524), (639, 524),
          (659, 545), (492, 696), (498, 736), (491, 768), (471, 791), (351, 795), (327, 767)),),
    ),
    'mountain': Plate(
        (418, 620, 364, 985),
        ((0, 498), (294, 498), (327, 503), (348, 502), (373, 513), (420, 525),
         (475, 531), (537, 533), (601, 529), (643, 517), (674, 502), (699, 500), (1024, 498)),
        (((302, 610), (312, 562), (326, 539), (356, 521), (364, 550), (437, 554),
          (429, 608), (422, 634), (399, 680), (372, 703), (352, 697), (365, 639),
          (373, 584), (343, 587), (319, 619)),
         ((586, 554), (653, 550), (660, 518), (683, 530), (702, 549), (713, 597),
          (701, 622), (674, 582), (644, 583), (655, 619), (665, 693), (648, 705),
          (620, 685), (603, 649), (594, 615))),
    ),
}


def register(source: Image.Image, plate: Plate) -> tuple[Image.Image, tuple[float, ...]]:
    left, right, eye_y, sole = plate.anchors
    sx = (EYE_ANCHORS[1] - EYE_ANCHORS[0]) / (right - left)
    sy = (SOLE - EYE_ANCHORS[2]) / (sole - eye_y)
    tx = EYE_ANCHORS[0] - sx * left
    ty = EYE_ANCHORS[2] - sy * eye_y

    # The API plates carry very faint stray pixels outside the subject. Keep
    # antialiasing at the silhouette and normalize the solid interior before scaling.
    source.putalpha(source.getchannel('A').point(lambda a: round(max(0, min(1, (a - 12) / 236)) * 255)))
    registered = source.transform((SIZE, SIZE), Image.Transform.AFFINE,
                                  (1 / sx, 0, -tx / sx, 0, 1 / sy, -ty / sy),
                                  Image.Resampling.BICUBIC)
    keep = registered.getchannel('A').point(lambda a: 255 if a > 3 else 0)
    return Image.composite(registered, Image.new('RGBA', registered.size), keep), (sx, sy, tx, ty)


def partition(image: Image.Image, plate: Plate, transform: tuple[float, ...]) -> dict[str, Image.Image]:
    sx, sy, tx, ty = transform

    def registered_polygon(points: tuple[Point, ...]) -> list[Point]:
        return [(round(x * sx + tx), round(y * sy + ty)) for x, y in points]

    def blank_mask() -> Image.Image:
        return Image.new('L', image.size)

    expression = blank_mask()
    x0, y0, x1, y1 = EXPRESSION
    ImageDraw.Draw(expression).rectangle((x0, y0, x1 - 1, y1 - 1), fill=255)

    head = blank_mask()
    collar = registered_polygon(plate.collar)
    ImageDraw.Draw(head).polygon([(0, 0), (SIZE, 0), (SIZE, collar[-1][1]), *reversed(collar),
                                  (0, collar[0][1])], fill=255)
    body = ImageChops.invert(head)
    head = ImageChops.subtract(head, expression)

    accessory = blank_mask()
    draw = ImageDraw.Draw(accessory)
    for region in plate.accessories:
        draw.polygon(registered_polygon(region), fill=255)
    accessory = ImageChops.multiply(accessory, body)
    outfit = ImageChops.subtract(body, accessory)

    # Each pixel belongs to exactly one layer, so the still and the settled
    # transformation are identical without seams or doubled alpha.
    transparent = Image.new('RGBA', image.size)
    return {name: Image.composite(image, transparent, mask) for name, mask in
            (('outfit', outfit), ('head', head), ('eyes', expression), ('accessory', accessory))}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, default=SOURCE)
    parser.add_argument('--output-dir', type=Path, default=OUTPUT)
    args = parser.parse_args()

    for skin, plate in PLATES.items():
        with Image.open(args.source_dir / f'{skin}.png') as source:
            if source.size != (1024, 1024) or source.mode != 'RGBA':
                raise ValueError(f'{skin}: expected a transparent 1024×1024 source plate')
            image, transform = register(source, plate)
        layers = partition(image, plate, transform)
        assembled = Image.new('RGBA', image.size)
        for layer in layers.values():
            if layer.getchannel('A').getextrema() != (0, 255):
                raise ValueError(f'{skin}: empty or nontransparent layer')
            assembled.alpha_composite(layer)
        if assembled.tobytes() != image.tobytes():
            raise ValueError(f'{skin}: layers differ from the registered source')

        output = args.output_dir / skin
        output.mkdir(parents=True, exist_ok=True)
        for name, result in {'final': image, **layers}.items():
            result.save(output / f'{name}.png', optimize=True)
        print(f'{skin}: 5 registered PNGs, exact recomposition, alpha bounds {image.getbbox()}')


if __name__ == '__main__':
    main()
