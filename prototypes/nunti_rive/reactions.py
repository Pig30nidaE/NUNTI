"""Parked reactions for the registered Nunti raster rig, at 60 fps."""

BODY, HEAD, LEFT_ARM, RIGHT_ARM, SPROUT = 10, 11, 12, 13, 14
LEFT_EAR, RIGHT_EAR = 15, 16
BLINK_LEFT, BLINK_RIGHT, WIDE, HAPPY_EYES, HAPPY_MOUTH = 51, 52, 53, 54, 55
HALF_LEFT, HALF_RIGHT = 56, 57


def _blink_tracks(half, closed, duration, lower, shut, lift, open_):
    return {
        (half, "opacity"): ((0, 0), (lower, 1), (shut, 0), (lift, 1), (open_, 0), (duration, 0)),
        (closed, "opacity"): ((0, 0), (shut, 1), (lift, 0), (duration, 0)),
    }


def reaction_tracks(skin):
    """Yield timeline names, frame lengths, property tracks and loop modes."""
    yield "idle", 336, {
        (BODY, "y"): ((0, 721), (84, 718), (165, 721), (249, 718.5), (336, 721)),
        (BODY, "scaleY"): ((0, 1), (84, 1.008), (165, 1), (249, 1.006), (336, 1)),
        (HEAD, "rotation"): ((0, 0), (100, -0.012), (233, 0.011), (336, 0)),
        (SPROUT, "rotation"): ((0, 0), (89, -0.041), (195, 0.028), (266, -0.016), (336, 0)),
        (LEFT_EAR, "rotation"): ((0, 0), (139, 0.020), (221, -0.018), (336, 0)),
        (RIGHT_EAR, "rotation"): ((0, 0), (151, -0.017), (232, 0.015), (336, 0)),
        **_blink_tracks(HALF_LEFT, BLINK_LEFT, 336, 114, 116, 119, 122),
        **_blink_tracks(HALF_RIGHT, BLINK_RIGHT, 336, 115, 117, 119, 123),
    }, "loop"

    yield "curious", 64, {
        (BODY, "y"): ((0, 721), (8, 722), (19, 715), (45, 716), (64, 721)),
        (BODY, "scaleY"): ((0, 1), (8, 0.988), (20, 1.018), (45, 1.014), (64, 1)),
        (HEAD, "rotation"): ((0, 0), (8, -0.025), (21, 0.116), (44, 0.105), (57, -0.018), (64, 0)),
        (SPROUT, "rotation"): ((0, 0), (10, -0.070), (25, -0.094), (44, -0.040), (58, 0.041), (64, 0)),
        (LEFT_EAR, "rotation"): ((0, 0), (16, -0.055), (31, 0.022), (64, 0)),
        (RIGHT_EAR, "rotation"): ((0, 0), (21, 0.074), (42, 0.048), (60, -0.015), (64, 0)),
        (WIDE, "opacity"): ((0, 0), (11, 0), (15, 1), (44, 1), (50, 0), (64, 0)),
    }, "oneShot"

    yield "happy", 59, {
        (BODY, "y"): ((0, 721), (8, 727), (22, 706), (34, 724), (44, 719), (59, 721)),
        (BODY, "scaleX"): ((0, 1), (8, 1.033), (18, 0.979), (34, 1.026), (45, 0.994), (59, 1)),
        (BODY, "scaleY"): ((0, 1), (8, 0.963), (18, 1.028), (34, 0.973), (45, 1.006), (59, 1)),
        (HEAD, "rotation"): ((0, 0), (19, -0.059), (37, 0.035), (59, 0)),
        (LEFT_ARM, "rotation"): ((0, 0), (9, -0.055), (22, 0.54), (37, -0.062), (59, 0)),
        (RIGHT_ARM, "rotation"): ((0, 0), (9, 0.054), (23, -0.56), (38, 0.068), (59, 0)),
        (SPROUT, "rotation"): ((0, 0), (14, 0.085), (26, -0.125), (40, 0.071), (52, -0.021), (59, 0)),
        (LEFT_EAR, "rotation"): ((0, 0), (23, -0.089), (38, 0.051), (59, 0)),
        (RIGHT_EAR, "rotation"): ((0, 0), (26, 0.082), (42, -0.047), (59, 0)),
        (HAPPY_EYES, "opacity"): ((0, 0), (14, 0), (18, 1), (30, 1), (35, 0), (59, 0)),
        (HAPPY_MOUTH, "opacity"): ((0, 0), (10, 0), (15, 1), (38, 1), (44, 0), (59, 0)),
    }, "oneShot"

    yield "wink", 45, {
        (HEAD, "rotation"): ((0, 0), (8, -0.017), (19, 0.077), (27, 0.072), (39, -0.016), (45, 0)),
        (BODY, "y"): ((0, 721), (17, 718.5), (33, 719.5), (45, 721)),
        (LEFT_ARM, "rotation"): ((0, 0), (8, -0.060), (18, 0.56), (24, 0.44), (30, 0.54), (37, 0.22), (45, 0)),
        (LEFT_EAR, "rotation"): ((0, 0), (20, 0.058), (34, -0.022), (45, 0)),
        (SPROUT, "rotation"): ((0, 0), (20, -0.075), (37, 0.032), (45, 0)),
        **_blink_tracks(HALF_LEFT, BLINK_LEFT, 45, 12, 14, 24, 27),
    }, "oneShot"

    yield "proud", 65, {
        (BODY, "y"): ((0, 721), (9, 724), (24, 715), (44, 716), (65, 721)),
        (BODY, "scaleX"): ((0, 1), (9, 0.994), (26, 1.021), (44, 1.018), (65, 1)),
        (BODY, "scaleY"): ((0, 1), (9, 0.990), (25, 1.025), (43, 1.020), (65, 1)),
        (HEAD, "rotation"): ((0, 0), (13, -0.044), (29, 0.057), (45, 0.052), (65, 0)),
        (LEFT_ARM, "rotation"): ((0, 0), (23, -0.195), (43, -0.161), (65, 0)),
        (RIGHT_ARM, "rotation"): ((0, 0), (26, 0.133), (44, 0.108), (65, 0)),
        (SPROUT, "rotation"): ((0, 0), (16, -0.045), (29, 0.053), (48, -0.018), (65, 0)),
        (HAPPY_MOUTH, "opacity"): ((0, 0), (17, 0), (22, 1), (43, 1), (49, 0), (65, 0)),
    }, "oneShot"

    duration, tracks = _signature(skin)
    yield "signature", duration, tracks, "oneShot"


def _signature(skin):
    if skin == "sea":
        # The hand meets the shell at the side of the cap during the bow.
        return 68, {
            (BODY, "y"): ((0, 721), (17, 717), (33, 727), (51, 719), (68, 721)),
            (BODY, "scaleY"): ((0, 1), (17, 1.012), (33, 0.974), (51, 1.009), (68, 1)),
            (HEAD, "rotation"): ((0, 0), (15, -0.052), (33, 0.108), (42, 0.081), (56, -0.024), (68, 0)),
            (RIGHT_ARM, "rotation"): ((0, 0), (10, 0.042), (23, -1.47), (29, -1.65), (37, -1.60), (54, 0.030), (68, 0)),
            (LEFT_ARM, "rotation"): ((0, 0), (33, -0.116), (53, 0.030), (68, 0)),
            (SPROUT, "rotation"): ((0, 0), (32, -0.126), (51, 0.108), (63, -0.018), (68, 0)),
            (LEFT_EAR, "rotation"): ((0, 0), (35, 0.072), (53, -0.036), (68, 0)),
            (HAPPY_EYES, "opacity"): ((0, 0), (25, 0), (29, 1), (36, 1), (41, 0), (68, 0)),
        }
    if skin == "city":
        # Snap into the headphones pose, then hold the wink after the tilt lands.
        return 62, {
            (BODY, "y"): ((0, 721), (10, 724), (23, 714), (43, 715.5), (62, 721)),
            (BODY, "scaleY"): ((0, 1), (10, 0.987), (23, 1.023), (43, 1.015), (62, 1)),
            (HEAD, "rotation"): ((0, 0), (11, 0.040), (23, -0.102), (43, -0.082), (54, 0.019), (62, 0)),
            (LEFT_ARM, "rotation"): ((0, 0), (10, 0.051), (23, -0.29), (40, -0.208), (62, 0)),
            (RIGHT_ARM, "rotation"): ((0, 0), (24, 0.177), (43, 0.139), (62, 0)),
            (SPROUT, "rotation"): ((0, 0), (17, -0.085), (29, 0.089), (47, -0.035), (62, 0)),
            (LEFT_EAR, "rotation"): ((0, 0), (25, -0.055), (40, -0.035), (62, 0)),
            **_blink_tracks(HALF_RIGHT, BLINK_RIGHT, 62, 24, 27, 38, 41),
            (HAPPY_MOUTH, "opacity"): ((0, 0), (18, 0), (23, 1), (42, 1), (47, 0), (62, 0)),
        }
    if skin == "mountain":
        # Load the knees, hang at the apex, and let the sprout settle after landing.
        return 68, {
            (BODY, "y"): ((0, 721), (10, 728), (27, 692), (39, 724), (51, 717), (60, 722), (68, 721)),
            (BODY, "scaleX"): ((0, 1), (10, 1.050), (21, 0.976), (39, 1.041), (51, 0.991), (68, 1)),
            (BODY, "scaleY"): ((0, 1), (10, 0.946), (21, 1.039), (39, 0.957), (51, 1.010), (68, 1)),
            (HEAD, "rotation"): ((0, 0), (25, -0.074), (42, 0.051), (56, -0.022), (68, 0)),
            (LEFT_ARM, "rotation"): ((0, 0), (10, -0.080), (25, 0.39), (43, -0.087), (68, 0)),
            (RIGHT_ARM, "rotation"): ((0, 0), (10, 0.080), (27, -0.37), (45, 0.078), (68, 0)),
            (SPROUT, "rotation"): ((0, 0), (21, 0.085), (30, -0.143), (47, 0.107), (59, -0.044), (68, 0)),
            (LEFT_EAR, "rotation"): ((0, 0), (30, -0.082), (47, 0.055), (68, 0)),
            (RIGHT_EAR, "rotation"): ((0, 0), (33, 0.078), (49, -0.043), (68, 0)),
            (HAPPY_EYES, "opacity"): ((0, 0), (20, 0), (24, 1), (33, 1), (38, 0), (68, 0)),
            (HAPPY_MOUTH, "opacity"): ((0, 0), (14, 0), (19, 1), (43, 1), (49, 0), (68, 0)),
        }
    # The original Nunti greets with a little shoulder lift and sprout flick.
    return 55, {
        (BODY, "y"): ((0, 721), (11, 723), (24, 714), (42, 719), (55, 721)),
        (BODY, "scaleY"): ((0, 1), (11, 0.986), (24, 1.021), (42, 1.005), (55, 1)),
        (HEAD, "rotation"): ((0, 0), (19, 0.069), (35, -0.029), (55, 0)),
        (LEFT_ARM, "rotation"): ((0, 0), (21, 0.33), (34, 0.26), (55, 0)),
        (SPROUT, "rotation"): ((0, 0), (19, -0.085), (34, 0.067), (49, -0.014), (55, 0)),
        (RIGHT_EAR, "rotation"): ((0, 0), (21, 0.052), (40, -0.024), (55, 0)),
        (HAPPY_MOUTH, "opacity"): ((0, 0), (12, 0), (17, 1), (36, 1), (42, 0), (55, 0)),
    }
