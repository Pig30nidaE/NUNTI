"""Real raster -> public extractor -> known source-line comparisons, without a network."""

import hashlib
import io
import json
import math
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from nunti.avatar_studio.navigation import COLOR_HINTS, MAX_IMAGE_BYTES, extract_route

EXAMPLES = Path(__file__).resolve().parents[2] / "prototypes/avatar_generator/examples"


def encoded(image, format="PNG", **kwargs):
    stream = io.BytesIO()
    image.save(stream, format=format, **kwargs)
    return stream.getvalue()


def line_distance(point, polyline):
    px, py = point
    distances = []
    for (ax, ay), (bx, by) in zip(polyline, polyline[1:], strict=False):
        dx, dy = bx - ax, by - ay
        den = dx * dx + dy * dy
        t = 0 if den == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / den))
        distances.append(math.hypot(px - ax - t * dx, py - ay - t * dy))
    return min(distances)


def samples(polyline):
    for (ax, ay), (bx, by) in zip(polyline, polyline[1:], strict=False):
        count = max(1, math.ceil(math.hypot(bx - ax, by - ay) / 3))
        for i in range(count + 1):
            t = i / count
            yield ax + (bx - ax) * t, ay + (by - ay) * t


@pytest.mark.parametrize("name", ("synthetic-city", "synthetic-coast", "synthetic-hills"))
@pytest.mark.parametrize("hint", (None, "#2478ec"))
def test_synthetic_screenshot_roundtrip_matches_paired_source(name, hint):
    meta = json.loads((EXAMPLES / f"{name}.json").read_text())
    raw = (EXAMPLES / meta["imageFile"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == meta["provenance"]["imageSha256"]
    assert meta["provenance"]["realMapData"] is False
    assert meta["provenance"]["liveNavigation"] is False
    assert meta["groundTruth"]["coordinateSpace"] == "WHOLE_IMAGE_NORMALIZED_XY"
    result = extract_route(raw, hint)
    assert result["inputOrigin"] == "NAVIGATION_SCREENSHOT"
    assert (result["imageWidth"], result["imageHeight"]) == (960, 640)
    assert 2 <= len(result["points"]) <= 512
    assert 0 < result["confidence"] < 0.9
    assert set(result["warnings"]) >= {
        "USER_CONFIRMATION_REQUIRED",
        "SCREEN_COORDINATES_ONLY",
        "ROUTE_DIRECTION_UNVERIFIED",
    }
    assert all(0 <= n <= 1 for p in result["points"] for n in p)
    extracted = [(p[0] * 960, p[1] * 640) for p in result["points"]]
    truth = meta["groundTruth"]["pixelPoints"]
    # Both directions matter: a tiny correct fragment does not count as a successful whole route.
    assert max(line_distance(p, truth) for p in samples(extracted)) < 8
    assert max(line_distance(p, extracted) for p in samples(truth)) < 9
    assert math.dist(extracted[0], truth[0]) < 9
    assert math.dist(extracted[-1], truth[-1]) < 9
    assert result == extract_route(raw, hint)


@pytest.mark.parametrize("format", ("PNG", "JPEG"))
def test_distinctive_colored_line_on_gray_road_grid(format):
    image = Image.new("RGB", (700, 420), "#f3f3f1")
    draw = ImageDraw.Draw(image)
    for x in range(0, 700, 35):
        draw.line([(x, 0), (x, 420)], fill="#b3b3b3", width=2)
    for y in range(0, 420, 35):
        draw.line([(0, y), (700, y)], fill="#b3b3b3", width=2)
    truth = [(60, 340), (160, 300), (210, 170), (350, 180), (460, 90), (640, 80)]
    draw.line(truth, fill="#8650dd", width=11, joint="curve")
    result = extract_route(encoded(image, format, quality=94), "#8650dd")
    output = [(x * 700, y * 420) for x, y in result["points"]]
    assert max(line_distance(p, output) for p in samples(truth)) < 8
    assert result["inputOrigin"] == "NAVIGATION_SCREENSHOT"


@pytest.mark.parametrize("format", ("PNG", "JPEG"))
def test_real_alternative_paths_are_not_silently_selected(format):
    image = Image.new("RGB", (700, 420), "white")
    draw = ImageDraw.Draw(image)
    draw.line([(40, 100), (240, 60), (420, 100), (650, 60)], fill="#2478ec", width=9)
    draw.line([(40, 320), (240, 280), (420, 320), (650, 280)], fill="#2478ec", width=9)
    with pytest.raises(ValueError, match="^(MULTIPLE_ROUTES|OTHER_ROUTE_GEOMETRY)_AMBIGUOUS$"):
        extract_route(encoded(image, format, quality=94))


def test_hint_can_disambiguate_separate_differently_colored_alternatives():
    image = Image.new("RGB", (700, 420), "white")
    draw = ImageDraw.Draw(image)
    draw.line([(50, 100), (350, 60), (650, 100)], fill="#2478ec", width=9)
    draw.line([(50, 320), (350, 280), (650, 320)], fill="#ed7045", width=9)
    raw = encoded(image)
    with pytest.raises(ValueError, match="MULTIPLE_ROUTES_AMBIGUOUS"):
        extract_route(raw)
    result = extract_route(raw, "#2478ec")
    assert max(y for _, y in result["points"]) < 0.30
    assert "USER_CONFIRMATION_REQUIRED" in result["warnings"]


@pytest.mark.parametrize("kind", ("grid", "branch", "loop"))
def test_colored_network_or_closed_loop_does_not_become_one_invented_route(kind):
    image = Image.new("RGB", (600, 400), "white")
    draw = ImageDraw.Draw(image)
    if kind == "grid":
        for x in range(60, 570, 60):
            draw.line([(x, 40), (x, 350)], fill="#2478ec", width=5)
        for y in range(50, 360, 60):
            draw.line([(40, y), (560, y)], fill="#2478ec", width=5)
    elif kind == "branch":
        draw.line([(50, 300), (300, 200), (550, 300)], fill="#2478ec", width=9)
        draw.line([(300, 200), (300, 40)], fill="#2478ec", width=9)
    else:
        draw.ellipse((80, 60, 520, 340), outline="#2478ec", width=9)
    with pytest.raises(ValueError, match="AMBIGUOUS"):
        extract_route(encoded(image))


@pytest.mark.parametrize("color", ("white", "#cccccc", "#2478ec"))
def test_blank_gray_or_saturated_background_is_not_a_route(color):
    with pytest.raises(ValueError, match="NO_COLORED_ROUTE|BACKGROUND_AMBIGUOUS|NO_ROUTE_FOUND"):
        extract_route(encoded(Image.new("RGB", (600, 400), color)))


def test_gray_road_grid_without_route_is_rejected():
    image = Image.new("RGB", (600, 400), "white")
    draw = ImageDraw.Draw(image)
    for x in range(40, 580, 45):
        draw.line([(x, 0), (x, 400)], fill="#777777", width=6)
    for y in range(40, 380, 45):
        draw.line([(0, y), (600, y)], fill="#777777", width=6)
    with pytest.raises(ValueError, match="NO_COLORED_ROUTE"):
        extract_route(encoded(image))


def test_visible_short_branch_is_not_pruned_as_raster_noise():
    image = Image.new("RGB", (600, 400), "white")
    draw = ImageDraw.Draw(image)
    draw.line([(50, 250), (550, 250)], fill="#2478ec", width=7)
    draw.line([(300, 250), (300, 220)], fill="#2478ec", width=7)
    with pytest.raises(ValueError, match="BRANCHING_AMBIGUOUS"):
        extract_route(encoded(image), "blue")


def test_exif_orientation_uses_the_displayed_image_dimensions():
    image = Image.new("RGB", (600, 400), "white")
    ImageDraw.Draw(image).line(
        [(80, 300), (200, 270), (330, 100), (540, 80)], fill="#2478ec", width=11
    )
    exif = image.getexif()
    exif[274] = 6
    result = extract_route(encoded(image, "JPEG", exif=exif, quality=95), "#2478ec")
    assert (result["imageWidth"], result["imageHeight"]) == (400, 600)
    assert "IMAGE_EXIF_ORIENTATION_APPLIED" in result["warnings"]


@pytest.mark.parametrize("hint", ("gold", "#abc", "#zzzzzz", [1, 2], [True, 1, 2], [256, 1, 2]))
def test_invalid_hints_are_rejected(hint):
    with pytest.raises(ValueError, match="INVALID_COLOR_HINT"):
        extract_route(encoded(Image.new("RGB", (100, 100), "white")), hint)


@pytest.mark.parametrize("hint", tuple(COLOR_HINTS))
def test_ui_named_color_hints(hint):
    image = Image.new("RGB", (600, 400), "white")
    ImageDraw.Draw(image).line(
        [(50, 330), (180, 250), (280, 280), (430, 130), (550, 80)],
        fill=COLOR_HINTS[hint],
        width=10,
    )
    result = extract_route(encoded(image), hint)
    assert len(result["points"]) >= 4
    assert "USER_CONFIRMATION_REQUIRED" in result["warnings"]


@pytest.mark.parametrize("hint", ("#ffffff", "#222222", "#000000"))
def test_achromatic_hint_does_not_select_gray_roads(hint):
    with pytest.raises(ValueError, match="COLOR_HINT_NOT_CHROMATIC"):
        extract_route(encoded(Image.new("RGB", (100, 100), "white")), hint)


@pytest.mark.parametrize(
    "raw", (b"", b"not an image", b"\x89PNG\r\n\x1a\n", b"x" * (MAX_IMAGE_BYTES + 1))
)
def test_invalid_or_truncated_bytes_are_rejected(raw):
    with pytest.raises(ValueError, match="INVALID_IMAGE"):
        extract_route(raw)


def test_limits_and_unsupported_format_are_checked_before_extraction():
    with pytest.raises(ValueError, match="IMAGE_DIMENSIONS_EXCEEDED"):
        extract_route(encoded(Image.new("RGB", (4097, 64), "white")))
    with pytest.raises(ValueError, match="IMAGE_DIMENSIONS_EXCEEDED"):
        extract_route(encoded(Image.new("RGB", (63, 100), "white")))
    with pytest.raises(ValueError, match="IMAGE_DIMENSIONS_EXCEEDED"):
        extract_route(encoded(Image.new("RGB", (3000, 3000), "white")))
    with pytest.raises(ValueError, match="UNSUPPORTED_IMAGE_FORMAT"):
        extract_route(encoded(Image.new("RGB", (100, 100), "white"), "GIF"))


def test_index_contains_only_declared_synthetic_test_inputs():
    entries = json.loads((EXAMPLES / "index.json").read_text())
    assert len(entries) == 3
    for entry in entries:
        assert entry["route"]["inputOrigin"] == "TEST_ROUTE"
        assert entry["provenance"]["kind"] == "SYNTHETIC_NAVIGATION_SCREENSHOT"
        assert entry["route"]["confirmed"] is True
        assert "displayName" not in entry and "voice" not in entry
        assert (EXAMPLES / entry["imageFile"]).is_file()
