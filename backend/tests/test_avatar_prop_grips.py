"""Rendered hand contact, including the mirrored side that detached narrow props."""

from copy import deepcopy

import pytest

from nunti.avatar_studio.design_intent import build_design_intent
from nunti.avatar_studio.journey_art import render_character
from nunti.avatar_studio.matte_cutout import _components

ROUTE = [[0.1, 0.8], [0.3, 0.6], [0.25, 0.4], [0.6, 0.5], [0.85, 0.2]]


@pytest.mark.parametrize("prop", ["PAINTBRUSH", "PENCIL", "TREKKING_POLE"])
@pytest.mark.parametrize("prop_side", [-1, 1])
@pytest.mark.parametrize("facing", [-1, 1])
def test_narrow_prop_pixels_connect_to_the_character_on_both_hands(prop, prop_side, facing):
    design = build_design_intent(
        ROUTE, "서울식물원", "", "미술 전시 관람", fine_detail_seed="grip-contact"
    )
    character = design["characterPlan"]
    character["bodyFamily"] = "PUP"
    character["pose"] = "HUG"
    character["prop"]["id"] = prop
    character["composition"].update(propSide=prop_side, facing=facing, tilt=0)
    before = deepcopy(design)
    image = render_character(design)
    # A shaft floating beside a hand used to form a second opaque component.
    # Inspect the final antialiased pixels after global mirroring, not coordinates
    # or a metadata claim that the hand is holding the prop.
    mask = image.getchannel("A").point(lambda alpha: 255 if alpha >= 128 else 0)
    components = _components(mask.tobytes(), *image.size)
    assert len(components) == 1, [(len(pixels), bbox) for pixels, bbox in components]
    assert design == before, "Grip placement must not mutate the character or voice design."
