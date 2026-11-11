"""RML timelines and the app-driven Nunti state machine."""

from xml.etree.ElementTree import Element, SubElement, indent, tostring


BODY, HEAD, LEFT_ARM, RIGHT_ARM, SPROUT = 10, 11, 12, 13, 14
BASE_MASTER, SKIN_MASTER = 20, 21
ORIGINAL_BODY, TRAVEL_HEAD = 24, 25
POSE_MASTER = 26
MOTION_STARTED, MOTION_FINISHED = 28, 29
ANTICIPATION_FRAMES, TRANSFORM_FRAMES, REVEAL_FRAMES = 33, 165, 42
# The headwear locks during the hold; the outfit and gear land just ahead of the release.
HEADWEAR_CUE, OUTFIT_CUE = 129, 162

STATE_MACHINE = 30
VIEW_MODEL = "0:1"
VIEW_MODEL_INSTANCE = "0:2"
START_TRIGGER = "0:3"
REACTIONS = ("curious", "happy", "wink", "proud", "signature")
REACTION_TRIGGERS = {name: f"0:{index}" for index, name in enumerate(REACTIONS, start=4)}
COMPANION_READY, SIGNATURE_FINISHED = 58, 59


def bindings() -> str:
    model = Element(
        "ViewModel", id=VIEW_MODEL, name="NuntiMotionControls", defaultInstanceId=VIEW_MODEL_INSTANCE
    )
    triggers = {"start": START_TRIGGER, **REACTION_TRIGGERS}
    for name, trigger in triggers.items():
        SubElement(model, "ViewModelPropertyTrigger", id=trigger, name=name)
    instance = SubElement(model, "ViewModelInstance", id=VIEW_MODEL_INSTANCE, name="Default", exports="true")
    for trigger in triggers.values():
        SubElement(instance, "ViewModelInstanceTrigger", viewModelPropertyId=trigger)
    return _xml(model)


def _xml(element: Element) -> str:
    indent(element, space="  ")
    return tostring(element, encoding="unicode")


def _machine(artboard_id: int) -> Element:
    def ref(slot: int) -> str:
        return f"{artboard_id}:{slot}"

    machine = Element("StateMachine", id=ref(STATE_MACHINE), name="NuntiMotion")
    layer = SubElement(machine, "StateMachineLayer", name="Nunti")
    SubElement(layer, "AnyState", x="0", y="-130")
    SubElement(layer, "ExitState", x="880", y="-130")
    entry = SubElement(layer, "EntryState", x="0", y="0")
    SubElement(entry, "StateTransition", stateToId=ref(31))

    for index in range(4):
        state = SubElement(
            layer, "AnimationState", id=ref(31 + index), animationId=ref(41 + index),
            x=str(180 + index * 220), y="0", reset="true",
        )
        if index == 0:
            start = SubElement(state, "StateTransition", stateToId=ref(32), duration="85")
            _trigger_condition(start, START_TRIGGER)
        else:
            _exit_transition(state, ref(32 + index if index < 3 else 85))
    _companion_states(layer, artboard_id, x=1060)
    return machine


def _trigger_condition(transition: Element, trigger_id: str) -> None:
    condition = SubElement(transition, "TransitionViewModelCondition", opValue="equal")
    left = SubElement(condition, "TransitionPropertyViewModelComparator")
    trigger = SubElement(left, "BindablePropertyTrigger")
    SubElement(trigger, "DataBindContext", sourcePathIds=f"{VIEW_MODEL}-{trigger_id}", propertyKey="686")
    SubElement(condition, "TransitionValueTriggerComparator")


def _exit_transition(state: Element, target: str) -> None:
    SubElement(state, "StateTransition", stateToId=target,
               enableExitTime="true", exitTimeIsPercetange="true", exitTime="100")


def _timeline(
    artboard_id: int,
    slot: int,
    name: str,
    duration: int,
    tracks: dict[tuple[int, str], tuple[tuple[int, float], ...]],
    loop: str = "oneShot",
) -> Element:
    animation = Element(
        "LinearAnimation", id=f"{artboard_id}:{slot}", fps="60", duration=str(duration),
        name=name, loopValue=loop,
    )
    objects: dict[int, Element] = {}
    for (joint, prop), poses in tracks.items():
        if joint not in objects:
            objects[joint] = SubElement(animation, "KeyedObject", objectId=f"{artboard_id}:{joint}")
        keyed_property = SubElement(objects[joint], "KeyedProperty", property=prop)
        for index, (frame, value) in enumerate(poses):
            key = SubElement(keyed_property, "KeyFrameDouble", frame=str(frame), value=str(round(value, 5)))
            if index < len(poses) - 1 and (prop != "opacity" or (joint < 51 and poses[index + 1][0] - frame <= 6)):
                key.set("interpolationType", "cubic")
                SubElement(key, "CubicEaseInterpolator", x1="0.36", y1="0", x2="0.42", y2="1")
    return animation


def _timeline_event(animation: Element, event_id: str, frame: int) -> None:
    keyed_object = SubElement(animation, "KeyedObject", objectId=event_id)
    keyed_property = SubElement(keyed_object, "KeyedProperty", property="trigger")
    SubElement(keyed_property, "KeyFrameCallback", frame=str(frame))


def _reaction_timelines(artboard_id, skin, *, after_reveal=False):
    from reactions import reaction_tracks

    animations = {}
    for slot, (name, duration, tracks, loop) in enumerate(reaction_tracks(skin), start=70):
        if after_reveal and name == "signature":
            tracks = {**tracks, (SKIN_MASTER, "opacity"): ((0, 0),), (POSE_MASTER, "opacity"): ((0, 1),)}
        label = "companion idle" if after_reveal and name == "idle" else name
        animations[name] = _timeline(artboard_id, slot, label, duration, tracks, loop)
    return animations


def _companion_states(layer: Element, artboard_id: int, x: int) -> None:
    def ref(slot: int) -> str:
        return f"{artboard_id}:{slot}"

    idle = SubElement(layer, "AnimationState", id=ref(80), animationId=ref(70), x=str(x), y="0", reset="true")
    for i, name in enumerate(REACTIONS, start=1):
        target = ref(80 + i)
        transition = SubElement(idle, "StateTransition", stateToId=target, duration="50")
        _trigger_condition(transition, REACTION_TRIGGERS[name])
        state = SubElement(layer, "AnimationState", id=target, animationId=ref(70 + i),
                           x=str(x + 280), y=str((i - 3) * 116), reset="true")
        _exit_transition(state, ref(80))


def companion_motion(artboard_id: int, skin: str) -> str:
    def ref(slot: int) -> str:
        return f"{artboard_id}:{slot}"

    animations = _reaction_timelines(artboard_id, skin)
    machine = Element("StateMachine", id=ref(STATE_MACHINE), name="NuntiMotion")
    layer = SubElement(machine, "StateMachineLayer", name="Companion")
    SubElement(layer, "AnyState", x="0", y="-130")
    SubElement(layer, "ExitState", x="860", y="-130")
    entry = SubElement(layer, "EntryState", x="0", y="0")
    SubElement(entry, "StateTransition", stateToId=ref(80))
    _companion_states(layer, artboard_id, x=180)
    ready = Element("Event", id=ref(COMPANION_READY), name="CompanionReady")
    _timeline_event(animations["idle"], ref(COMPANION_READY), 1)
    return "\n".join(_xml(element) for element in (ready, machine, *animations.values()))


def motion(artboard_id: int, skin: str) -> str:
    turn, lift_frame, lift_y, sprout_follow, arm_open = {
        "sea": (1, 15, 703, 0.184, 0.24),
        "city": (-1, 12, 704, 0.164, 0.25),
        "mountain": (1, 16, 708, 0.144, 0.28),
    }[skin]
    idle = _timeline(artboard_id, 41, "idle", 168, {
        (BODY, "y"): ((0, 721), (84, 718), (168, 721)),
        (BODY, "scaleY"): ((0, 1), (84, 1.008), (168, 1)),
        (HEAD, "rotation"): ((0, 0), (46, -0.014), (108, 0.012), (168, 0)),
        (SPROUT, "rotation"): ((0, 0), (54, -0.035), (116, 0.027), (168, 0)),
        (LEFT_ARM, "rotation"): ((0, 0), (84, 0.018), (168, 0)),
        (RIGHT_ARM, "rotation"): ((0, 0), (84, -0.018), (168, 0)),
    }, loop="loop")

    anticipation = _timeline(artboard_id, 42, "anticipation", ANTICIPATION_FRAMES, {
        (BODY, "y"): ((0, 721), (13, 720), (26, 724), (33, 722)),
        (BODY, "scaleX"): ((0, 1), (13, 0.993), (27, 1.022), (33, 1.012)),
        (BODY, "scaleY"): ((0, 1), (13, 1.014), (27, 0.972), (33, 0.985)),
        (HEAD, "rotation"): ((0, 0), (14, -0.064 * turn), (33, 0.024 * turn)),
        (SPROUT, "rotation"): ((0, 0), (9, -0.18 * turn), (24, 0.085 * turn), (33, 0)),
        (LEFT_ARM, "rotation"): ((0, 0), (16, -0.080), (33, 0.045)),
        (RIGHT_ARM, "rotation"): ((0, 0), (18, 0.025), (33, -0.045)),
    })

    transform = _timeline(artboard_id, 43, "transform", TRANSFORM_FRAMES, {
        (BASE_MASTER, "opacity"): ((0, 1), (HEADWEAR_CUE, 1), (HEADWEAR_CUE + 4, 0)),
        (SKIN_MASTER, "opacity"): ((0, 0), (OUTFIT_CUE - 5, 0), (OUTFIT_CUE, 1)),
        (ORIGINAL_BODY, "opacity"): ((0, 0), (HEADWEAR_CUE, 1), (OUTFIT_CUE - 4, 1), (OUTFIT_CUE + 2, 0)),
        (TRAVEL_HEAD, "opacity"): ((0, 0), (HEADWEAR_CUE - 4, 0), (HEADWEAR_CUE, 1), (OUTFIT_CUE, 1), (OUTFIT_CUE + 2, 0)),
        (BODY, "y"): ((0, 722), (32, 718), (74, 721), (110, 716), (165, 728)),
        (BODY, "scaleX"): ((0, 1.012), (41, 0.995), (108, 0.998), (165, 1.052)),
        (BODY, "scaleY"): ((0, 0.985), (41, 1.005), (108, 1.011), (165, 0.943)),
        (HEAD, "rotation"): ((0, 0.024 * turn), (40, -0.047 * turn), (84, 0.035 * turn), (114, -0.02 * turn), (165, 0)),
        (SPROUT, "rotation"): ((0, 0), (55, 0.095 * turn), (82, -0.135 * turn), (120, 0.077 * turn), (165, 0.105 * turn)),
        (LEFT_ARM, "rotation"): ((0, 0.045), (41, -0.105), (103, 0.062), (165, 0.115)),
        (RIGHT_ARM, "rotation"): ((0, -0.045), (44, 0.120), (107, -0.064), (165, -0.115)),
    })

    reveal = _timeline(artboard_id, 44, "reveal", REVEAL_FRAMES, {
        (BODY, "y"): ((0, 728), (5, 718), (lift_frame, lift_y), (27, 723), (34, 719), (41, 721)),
        (BODY, "scaleX"): ((0, 1.052), (5, 0.982), (15, 0.976), (27, 1.031), (41, 1)),
        (BODY, "scaleY"): ((0, 0.943), (5, 1.022), (15, 1.006), (27, 0.961), (35, 1.004), (41, 1)),
        (HEAD, "rotation"): ((0, 0), (11, -0.065 * turn), (27, 0.037 * turn), (41, 0)),
        (SPROUT, "rotation"): ((0, 0.105 * turn), (12, -sprout_follow * turn), (27, 0.094 * turn), (41, 0)),
        (LEFT_ARM, "rotation"): ((0, 0.115), (13, -arm_open), (28, 0.065), (41, 0)),
        (RIGHT_ARM, "rotation"): ((0, -0.115), (14, arm_open), (28, -0.065), (41, 0)),
    })

    started_id = f"{artboard_id}:{MOTION_STARTED}"
    finished_id = f"{artboard_id}:{MOTION_FINISHED}"
    # Positive frame times keep both signals on the character clock, which
    # stays at zero while the runtime plays the Free export's preroll.
    _timeline_event(anticipation, started_id, 1)
    _timeline_event(reveal, finished_id, 41)
    started = Element("Event", id=started_id, name="MotionStarted")
    finished = Element("Event", id=finished_id, name="MotionFinished")
    animations = _reaction_timelines(artboard_id, skin, after_reveal=True)
    signature = animations["signature"]
    signature_id = f"{artboard_id}:{SIGNATURE_FINISHED}"
    signature_finished = Element("Event", id=signature_id, name="SignatureFinished")
    _timeline_event(signature, signature_id, int(signature.attrib["duration"]) - 1)
    elements = (started, finished, signature_finished, _machine(artboard_id), idle, anticipation, transform, reveal,
                *animations.values())
    return "\n".join(_xml(element) for element in elements)
