"""Build the registered Nunti raster rig for Rive CLI."""

from base64 import b64encode
from itertools import product
from pathlib import Path

from PIL import Image, ImageChops


SIZE = 768
SKINS = ("sea", "city", "mountain")
CHARACTERS = ("base", *SKINS)
CHARACTER_ASSETS = dict(zip(CHARACTERS, range(10, 14)))
SOURCE = "../avatar_generator"
PLATES = Path(__file__).with_name("plates")
ORIGINAL_BODY_ASSET = 14
BONES = (
    ("Body", 10, 384, 721),
    ("Head", 11, 384, 395),
    ("Left arm", 12, 293, 425),
    ("Right arm", 13, 475, 425),
    ("Sprout", 14, 384, 108),
    ("Left ear", 15, 217, 278),
    ("Right ear", 16, 551, 278),
)
FACE_SLOTS = {
    "blink-left": 51, "blink-right": 52, "wide": 53, "happy-eyes": 54, "happy-mouth": 55,
    "blink-left-half": 56, "blink-right-half": 57,
}
X = (0, 170, 214, 262, 308, 384, 460, 506, 554, 598, 768)
Y = (0, 45, 85, 115, 195, 300, 380, 412, 454, 510, 554, 596, 670, 768)
REST_X = (0, 170, 214, 237, 262, 308, 384, 460, 506, 532, 554, 598, 768)


def curve(value, start, end):
    fraction = min(1, max(0, (value - start) / (end - start)))
    return fraction * fraction * (3 - 2 * fraction)


def vertex_weights(x, y, *, rest_skin=None):
    if y <= 412:
        head = 1 - curve(y, 372, 412)
        sprout = 1 - curve(y, 77, 115)
        ear = (head - sprout) * curve(y, 155, 225) * (1 - curve(y, 325, 378)) if rest_skin else 0
        left = ear * (1 - curve(x, 210, 260))
        right = ear * curve(x, 508, 558)
        bone_weights = ((1, 1 - head), (2, head - sprout - left - right), (5, sprout), (6, left), (7, right))
    else:
        sleeve = curve(y, 412, 494) * (1 - curve(y, 554, 595))
        # The resting rig lifts its hands farther. Keep the travel pouch and
        # jacket front anchored while the sleeve and glove follow the shoulder.
        left = sleeve * (1 - curve(x, 217, 258) if rest_skin else 1 - curve(x, 251, 307))
        right_edge = (503, 530) if rest_skin == "sea" else (509, 548) if rest_skin else (461, 517)
        right = sleeve * curve(x, *right_edge)
        bone_weights = ((1, 1 - left - right), (3, left), (4, right))

    # Each packed weight is one byte. Give the last nonzero slot the rounding
    # remainder so the runtime receives exactly 255 total influence.
    active = [(index, weight) for index, weight in bone_weights if weight > 0]
    values = [round(weight * 255) for _, weight in active[:-1]]
    values.append(255 - sum(values))
    indices = sum(index << (8 * slot) for slot, (index, _) in enumerate(active))
    packed = sum(weight << (8 * slot) for slot, weight in enumerate(values))
    return indices, packed


def triangulation(xs, ys):
    # Put the perimeter first so the Rive Editor recognises the mesh outline.
    edge = [*((x, ys[0]) for x in xs), *((xs[-1], y) for y in ys[1:]),
            *((x, ys[-1]) for x in reversed(xs[:-1])),
            *((xs[0], y) for y in reversed(ys[1:-1]))]
    vertices = edge + list(product(xs[1:-1], ys[1:-1]))
    index = {point: i for i, point in enumerate(vertices)}
    triangles = []
    for y, bottom in zip(ys, ys[1:]):
        for x, right in zip(xs, xs[1:]):
            top_left, top_right = index[x, y], index[right, y]
            bottom_left, bottom_right = index[x, bottom], index[right, bottom]
            triangles.extend((top_left, top_right, bottom_right, top_left, bottom_right, bottom_left))
    encoded = bytearray()
    for value in triangles:
        if value >= 128:
            encoded.append((value & 127) | 128)
            value >>= 7
        encoded.append(value)
    return vertices, len(edge), b64encode(encoded).decode()


def mesh(artboard, asset, name, *, patch=None, rest_skin=None):
    left, top, right, bottom = patch or (0, 0, SIZE, SIZE)
    xs, ys = ((left, right), (top, bottom)) if patch else (REST_X if rest_skin else X, Y)
    vertices, perimeter, indices = triangulation(xs, ys)
    rows = [f'        <Image originX="0" originY="0" assetId="0:{asset}" name="{name}">',
            f'          <Mesh triangleIndexBytes="{indices}" name="{name} mesh">']
    for index, (x, y) in enumerate(vertices):
        tag = "ContourMeshVertex" if index < perimeter else "MeshVertex"
        bones, weights = (2, 255) if patch else vertex_weights(x, y, rest_skin=rest_skin)
        u, v = (x - left) / (right - left), (y - top) / (bottom - top)
        rows.extend((
            f'            <{tag} x="{x}" y="{y}" u="{u:.9f}" v="{v:.9f}">',
            f'              <Weight indices="{bones}" values="{weights}"/>',
            f'            </{tag}>',
        ))
    rows.append('            <Skin name="Bind pose">')
    for bone, slot, x, y in BONES:
        rows.append(f'              <Tendon boneId="{artboard}:{slot}" tx="{x}" ty="{y}" name="{bone}"/>')
    rows.extend(("            </Skin>", "          </Mesh>", "        </Image>"))
    return "\n".join(rows)


def texture_layer(artboard_id, slot, texture, name, opacity=0, **mesh_options):
    return (
        f'    <Node name="{name}" id="{artboard_id}:{slot}" opacity="{opacity}">\n'
        f'{mesh(artboard_id, texture, name, **mesh_options)}\n    </Node>'
    )


def wardrobe(artboard_id, skin, asset):
    from motion import BASE_MASTER, SKIN_MASTER, ORIGINAL_BODY, TRAVEL_HEAD, POSE_MASTER

    # The approved head and face pixels move as one region. The accessory and
    # base outfit remain attached below it until the wardrobe accent lands.
    return "\n".join((
        texture_layer(artboard_id, BASE_MASTER, 10, "Original vinyl", opacity=1),
        texture_layer(artboard_id, SKIN_MASTER, asset, "Travel vinyl"),
        texture_layer(artboard_id, ORIGINAL_BODY, ORIGINAL_BODY_ASSET, "Original outfit and accessories"),
        texture_layer(artboard_id, TRAVEL_HEAD, asset + 4, "Travel headwear and face"),
        texture_layer(artboard_id, POSE_MASTER, asset, "Travel reaction rig", rest_skin=skin),
    ))


def compose_plate(relative_directory, parts):
    directory = Path(__file__).parent / SOURCE / "skin-v2" / relative_directory
    image = Image.new("RGBA", (SIZE, SIZE))
    for part in parts:
        with Image.open(directory / f"{part}.png") as layer:
            image.alpha_composite(layer)
    return image


def travel_head_plate(skin, original_body):
    directory = f"polish/{skin}"
    head = compose_plate(directory, ("head", "eyes"))
    collar = compose_plate(directory, ("outfit", "accessory"))
    # A few collar pixels back the seam while the new headwear sits on the
    # original outfit. Keep the support behind the original scarf and feather
    # its lower edge so it cannot draw a separate stripe.
    limit = Image.new("L", (SIZE, SIZE), 0)
    limit.paste(255, (0, 0, SIZE, 403))
    for y in range(403, 413):
        limit.paste(round((413 - y) * 255 / 10), (0, y, SIZE, y + 1))
    uncovered = ImageChops.invert(original_body.getchannel("A"))
    collar.putalpha(ImageChops.multiply(collar.getchannel("A"), ImageChops.multiply(limit, uncovered)))
    result = Image.alpha_composite(Image.new("RGBA", (SIZE, SIZE)), collar)
    result.alpha_composite(head)
    return result


def face_asset(skin, patch):
    return 100 + CHARACTERS.index(skin) * len(FACE_SLOTS) + FACE_SLOTS[patch] - 51


def artboard(artboard_id, skin, motion, *, rest=False):
    from expressions import PATCHES

    asset = CHARACTER_ASSETS[skin]
    prefix = f"{artboard_id}:"
    name = skin.title() + (" Rest" if rest else "")
    body = (texture_layer(artboard_id, 20, asset, "Approved vinyl", opacity=1, rest_skin=skin)
            if rest else wardrobe(artboard_id, skin, asset))
    faces = "\n".join(texture_layer(artboard_id, slot, face_asset(skin, patch), patch, patch=PATCHES[patch])
                      for patch, slot in FACE_SLOTS.items())
    return f'''  <Artboard name="{name}" width="{SIZE}" height="{SIZE}" x="{(artboard_id - 1) * 840}" id="{prefix}2"
            styleId="{prefix}3" defaultStateMachineId="{prefix}30" viewModelId="0:1" viewModelInstanceId="0:2">
    <LayoutComponentStyle id="{prefix}3"/>
    <RootBone x="384" y="721" length="0" name="Body" id="{prefix}10">
      <RootBone x="0" y="-326" length="0" name="Head" id="{prefix}11">
        <RootBone x="0" y="-287" length="0" name="Sprout" id="{prefix}14"/>
        <RootBone x="-167" y="-117" length="0" name="Left ear" id="{prefix}15"/>
        <RootBone x="167" y="-117" length="0" name="Right ear" id="{prefix}16"/>
      </RootBone>
      <RootBone x="-91" y="-296" length="0" name="Left arm" id="{prefix}12"/>
      <RootBone x="91" y="-296" length="0" name="Right arm" id="{prefix}13"/>
    </RootBone>
{faces}
{body}
{motion(artboard_id, skin)}
  </Artboard>'''


def main():
    from expressions import bake_expressions
    from motion import bindings, companion_motion, motion

    boards = [artboard(index, skin, motion) for index, skin in enumerate(SKINS, start=1)]
    boards.extend(artboard(index, skin, companion_motion, rest=True) for index, skin in enumerate(CHARACTERS, start=4))
    base_path = f"{SOURCE}/nunti-motion/base.png"
    assets = [f'  <ImageAsset file="{base_path}" name="Approved base Nunti" id="0:10"/>']
    PLATES.mkdir(exist_ok=True)
    original_body = compose_plate("default", ("outfit", "accessory"))
    original_body.save(PLATES / "original-body.png", optimize=True)
    assets.append(f'  <ImageAsset file="plates/original-body.png" name="Approved outfit and gear" id="0:{ORIGINAL_BODY_ASSET}"/>')
    for index, skin in enumerate(SKINS, start=11):
        path = f"{SOURCE}/skin-v2/polish/{skin}/final.png"
        assets.append(f'  <ImageAsset file="{path}" name="{skin.title()} skin" id="0:{index}"/>')
        head_plate = f"{skin}-head.png"
        travel_head_plate(skin, original_body).save(PLATES / head_plate, optimize=True)
        assets.append(f'  <ImageAsset file="plates/{head_plate}" name="{skin.title()} headwear and face" id="0:{index + 4}"/>')
    bake_expressions(PLATES / "expressions")
    for skin in CHARACTERS:
        for patch in FACE_SLOTS:
            assets.append(f'  <ImageAsset file="plates/expressions/{skin}-{patch}.png" name="{skin} {patch}" id="0:{face_asset(skin, patch)}"/>')
    rml = "\n".join(('<Rive version="1" kind="fragment">', bindings(), *assets, *boards, "</Rive>", ""))
    Path(__file__).with_name("scene.rml").write_text(rml, encoding="utf-8")


if __name__ == "__main__":
    main()
