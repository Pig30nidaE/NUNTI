"""Flat-border cutout contracts; no model inference or remote assets."""

from __future__ import annotations

import hashlib
import io
import unittest

from PIL import Image, ImageDraw, ImageFilter

from nunti.avatar_studio.matte_cutout import MatteCutoutError, cutout_matte_rgb

ROUTE = [[0.1, 0.8], [0.3, 0.4], [0.5, 0.6], [0.9, 0.1]]


def source_png(*, extra=False, enclosed=False, tiny=False):
    image = Image.new("RGB", (256, 256), (250, 247, 232))
    draw = ImageDraw.Draw(image)
    draw.ellipse((75, 46, 210, 212), fill=(166, 211, 193), outline=(95, 146, 126), width=3)
    draw.ellipse((120, 100, 129, 111), fill=(65, 55, 45))
    draw.ellipse((162, 100, 171, 111), fill=(65, 55, 45))
    if extra:
        draw.rectangle((8, 185, 60, 240), fill=(100, 180, 200))
    if enclosed:
        draw.ellipse((125, 145, 153, 173), fill=(250, 247, 232))
    if tiny:
        draw.rectangle((24, 24, 26, 26), fill=(110, 145, 120))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def source_with_ground_object(
    *, bbox=(85, 226, 200, 238), darkening=(22, 22, 22), blur=1.5, rectangle=False, second=None
):
    """Synthetic control: same body, independently adjustable detached object."""
    image = Image.open(io.BytesIO(source_png())).copy()
    mask = Image.new("L", image.size)
    draw = ImageDraw.Draw(mask)
    shape = draw.rectangle if rectangle else draw.ellipse
    shape(bbox, fill=255)
    if second is not None:
        shape(second, fill=255)
    if blur:
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
    shade = Image.new(
        "RGB", image.size, tuple(v - d for v, d in zip((250, 247, 232), darkening, strict=True))
    )
    image.paste(shade, mask=mask)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class MatteCutoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = source_png()
        cls.rgba, cls.formation, cls.report = cutout_matte_rgb(cls.original, ROUTE)
        cls.output = Image.open(io.BytesIO(cls.rgba))

    def assert_rejected(self, source, code):
        with self.assertRaises(MatteCutoutError) as raised:
            cutout_matte_rgb(source, ROUTE)
        self.assertEqual(raised.exception.code, code)

    def test_keeps_canvas_and_all_original_rgb_channels(self):
        source = Image.open(io.BytesIO(self.original))
        self.assertEqual(self.output.mode, "RGBA")
        self.assertEqual(self.output.size, source.size)
        self.assertEqual(self.output.convert("RGB").tobytes(), source.tobytes())
        self.assertEqual(self.report["originalSha256"], hashlib.sha256(self.original).hexdigest())
        self.assertEqual(self.report["rgbaSha256"], hashlib.sha256(self.rgba).hexdigest())
        self.assertTrue(self.report["rgbChannelsPreserved"])
        self.assertFalse(self.report["cropApplied"])

    def test_removes_only_border_connected_background_and_keeps_opaque_body(self):
        alpha = self.output.getchannel("A")
        self.assertEqual(alpha.getpixel((0, 0)), 0)
        self.assertEqual(alpha.getpixel((140, 125)), 255)
        self.assertGreater(sum(alpha.histogram()[1:255]), 0)
        original = source_png(enclosed=True)
        rgba, _, _ = cutout_matte_rgb(original, ROUTE)
        # Enclosed background-coloured body detail is not silently punched out.
        self.assertEqual(Image.open(io.BytesIO(rgba)).getpixel((140, 158))[3], 255)

    def test_measures_actual_alpha_boundary_instead_of_using_a_template(self):
        self.assertEqual(self.formation["source"], "MEASURED_ALPHA_BOUNDARY")
        contour = self.formation["contour"]
        self.assertEqual(len(contour), 192)
        self.assertEqual(contour[0], contour[-1])
        alpha = self.output.getchannel("A")
        for x, y in contour:
            px, py = round(x * 256), round(y * 256)
            self.assertGreater(
                max(alpha.getpixel((px + dx, py + dy)) for dx in (-1, 0, 1) for dy in (-1, 0, 1)),
                127,
            )
        xs = [p[0] for p in contour]
        ys = [p[1] for p in contour]
        self.assertAlmostEqual(min(xs), 75 / 256, delta=2 / 256)
        self.assertAlmostEqual(max(ys), 212 / 256, delta=2 / 256)

    def test_projection_and_face_are_explicitly_unverified(self):
        self.assertEqual(self.formation["mapping"], "GEOMETRIC_PROJECTION_NOT_SEMANTIC")
        self.assertEqual(len(self.formation["spine"]), 96)
        self.assertEqual(self.formation["faceCenter"], None)
        self.assertFalse(self.formation["faceCenterVerified"])
        self.assertEqual(self.formation["faceCenterSource"], "UNKNOWN")
        self.assertFalse(self.report["semanticRouteVerified"])
        self.assertFalse(self.report["faceVerified"])
        self.assertTrue(
            all(color.startswith("#") and len(color) == 7 for color in self.formation["palette"])
        )
        _, horizontal, _ = cutout_matte_rgb(self.original, [[0.1, 0.5], [0.9, 0.5]])
        points = horizontal["spine"]
        self.assertGreater(points[-1][0], points[0][0])
        self.assertEqual(points[-1][1], points[0][1])

    def test_retry_is_byte_and_metadata_stable(self):
        self.assertEqual(
            (self.rgba, self.formation, self.report), cutout_matte_rgb(self.original, ROUTE)
        )

    def test_rejects_large_inset_without_removing_or_cropping_it(self):
        original = source_png(extra=True)
        before = hashlib.sha256(original).digest()
        self.assert_rejected(original, "MULTIPLE_LARGE_OBJECTS")
        self.assertEqual(before, hashlib.sha256(original).digest())

    def test_preserves_small_detached_detail_and_reports_it(self):
        rgba, _, report = cutout_matte_rgb(source_png(tiny=True), ROUTE)
        self.assertGreater(Image.open(io.BytesIO(rgba)).getpixel((25, 25))[3], 0)
        self.assertEqual(len(report["foregroundComponents"]), 2)

    def test_removes_only_soft_low_contrast_oval_below_body_with_auditable_evidence(self):
        original = source_with_ground_object()
        before = hashlib.sha256(original).hexdigest()
        rgba, _, report = cutout_matte_rgb(original, ROUTE)
        output = Image.open(io.BytesIO(rgba))
        self.assertEqual(output.getpixel((145, 232))[3], 0)
        self.assertEqual(output.getpixel((140, 125))[3], 255)
        self.assertEqual(
            output.convert("RGB").tobytes(), Image.open(io.BytesIO(original)).tobytes()
        )
        self.assertEqual(hashlib.sha256(original).hexdigest(), before)
        self.assertEqual(report["originalSha256"], before)
        self.assertEqual(len(report["foregroundComponents"]), 1)
        self.assertEqual(len(report["sourceForegroundComponents"]), 2)
        self.assertEqual(len(report["removedGroundShadows"]), 1)
        evidence = report["removedGroundShadows"][0]
        self.assertEqual(evidence["reason"], "DETACHED_SOFT_GROUND_SHADOW")
        self.assertGreater(evidence["area"], 256 * 256 * 0.01)
        self.assertLessEqual(evidence["areaRelativeToBody"], 0.08)
        self.assertGreaterEqual(evidence["aspectRatio"], 4)
        self.assertGreaterEqual(
            evidence["interiorMedianContrast"] - evidence["edgeMedianContrast"], 2
        )
        self.assertFalse(evidence["semanticIdentityVerified"])
        # Neither a retry nor the changed alpha may recolor the original canvas.
        retry_rgba, _, retry_report = cutout_matte_rgb(original, ROUTE)
        self.assertEqual((rgba, report), (retry_rgba, retry_report))

    def test_rejects_detached_colored_dark_or_hard_edged_props(self):
        for options in (
            {"darkening": (22, 5, 12)},
            {"darkening": (60, 60, 60)},
            {"blur": 0},
            {"rectangle": True},
        ):
            with self.subTest(options=options):
                self.assert_rejected(source_with_ground_object(**options), "MULTIPLE_LARGE_OBJECTS")

    def test_rejects_shadow_like_objects_above_beside_far_below_or_too_large(self):
        for bbox in (
            (85, 20, 200, 32),  # Above the character.
            (5, 220, 70, 240),  # Outside the body's horizontal range.
            (85, 241, 200, 253),  # Too far below the body.
            (77, 218, 209, 240),  # Too tall and too much area.
        ):
            with self.subTest(bbox=bbox):
                self.assert_rejected(source_with_ground_object(bbox=bbox), "MULTIPLE_LARGE_OBJECTS")

    def test_rejects_second_character_even_with_removable_ground_shadow(self):
        image = Image.open(io.BytesIO(source_with_ground_object()))
        draw = ImageDraw.Draw(image)
        draw.ellipse((5, 90, 60, 155), fill=(180, 200, 210), outline=(70, 90, 100), width=2)
        draw.ellipse((20, 110, 24, 116), fill=(40, 40, 40))
        draw.ellipse((40, 110, 44, 116), fill=(40, 40, 40))
        output = io.BytesIO()
        image.save(output, format="PNG")
        self.assert_rejected(output.getvalue(), "MULTIPLE_LARGE_OBJECTS")

    def test_does_not_remove_multiple_plausible_ground_shadows(self):
        original = source_with_ground_object(
            bbox=(80, 215, 205, 224), second=(80, 227, 205, 236), blur=1
        )
        self.assert_rejected(original, "MULTIPLE_LARGE_OBJECTS")

    def test_rejects_varying_background(self):
        image = Image.new("RGB", (256, 256))
        draw = ImageDraw.Draw(image)
        for y in range(256):
            draw.line((0, y, 255, y), fill=(y, 210, 220))
        output = io.BytesIO()
        image.save(output, format="PNG")
        self.assert_rejected(output.getvalue(), "BACKGROUND_NOT_FLAT")

    def test_rejects_blank_and_rectangular_panel(self):
        image = Image.new("RGB", (256, 256), "white")
        output = io.BytesIO()
        image.save(output, format="PNG")
        self.assert_rejected(output.getvalue(), "SUBJECT_TOO_SMALL")
        ImageDraw.Draw(image).rectangle((80, 50, 195, 210), fill="blue")
        output = io.BytesIO()
        image.save(output, format="PNG")
        self.assert_rejected(output.getvalue(), "RECTANGULAR_PANEL")

    def test_rejects_invalid_format_or_already_rgba_source(self):
        self.assert_rejected(b"not an image", "INVALID_PNG")
        self.assert_rejected(b"", "INVALID_PNG")
        image = Image.open(io.BytesIO(self.original)).convert("RGBA")
        output = io.BytesIO()
        image.save(output, format="PNG")
        self.assert_rejected(output.getvalue(), "SOURCE_NOT_RGB_PNG")


if __name__ == "__main__":
    unittest.main()
