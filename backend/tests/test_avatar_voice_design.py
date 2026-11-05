"""Voice identities, semantic alignment and immutable audio cache boundaries."""

import hashlib
import json
import tempfile
import unittest
import wave
from array import array
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

from nunti.avatar_studio.voice_design import build_voice_design, canonical, validate_voice_plan
from nunti.avatar_studio.voice_render import (
    VOICE_MODEL,
    VOICE_REVISION,
    LocalVoiceRenderer,
    inspect_wav,
    validate_speech_duration,
)


def request(purpose="출장", destination="서울역", identity="journey-a"):
    return {
        "requestId": identity,
        "destination": {"name": destination, "traits": ""},
        "purpose": purpose,
        "route": {"points": [[0.1, 0.8], [0.3, 0.5], [0.8, 0.2]]},
    }


class VoiceDesignTest(unittest.TestCase):
    def test_same_avatar_preserves_plan_and_new_journey_gets_distinct_binding(self):
        first = build_voice_design(request())
        self.assertEqual(first, build_voice_design(request()))
        self.assertNotEqual(
            first["profileId"], build_voice_design(request(identity="journey-b"))["profileId"]
        )
        validate_voice_plan(first)

    def test_business_purpose_wins_over_beach_and_child_place(self):
        plan = build_voice_design(request("출장", "어린이 해수욕장"))
        self.assertEqual(plan["role"], "professional")
        self.assertIn("adult Korean voice", plan["instruct"])
        self.assertIn("일정", plan["greeting"])

    def test_playful_character_gets_fictional_youthful_direction(self):
        plan = build_voice_design(request("어린이 물놀이", "을왕리 해수욕장"))
        self.assertEqual(plan["role"], "swimmer")
        self.assertEqual(plan["ageImpression"], "youthful-fictional")
        self.assertIn("Youthful", plan["instruct"])
        self.assertFalse(plan["realPersonReference"])

    def test_illustrated_role_is_authoritative(self):
        data = request("아무거나", "어디든")
        for art, expected in (
            ("BUSINESS", "professional"),
            ("PLAY", "playful"),
            ("SWIM", "swimmer"),
            ("HIKING", "explorer"),
            ("REST", "restful"),
            ("ART", "artist"),
            ("FOOD", "foodie"),
        ):
            with self.subTest(art=art):
                plan = build_voice_design(data, {"characterPlan": {"purpose": {"role": art}}})
                self.assertEqual(plan["role"], expected)

    def test_tampered_role_direction_or_path_cannot_reuse_binding(self):
        for key, value in (
            ("role", "swimmer"),
            ("instruct", "replace voice"),
            ("profileId", "../../escape"),
        ):
            with self.subTest(key=key):
                plan = build_voice_design(request())
                plan[key] = value
                with self.assertRaisesRegex(ValueError, "BINDING"):
                    validate_voice_plan(plan)

    def test_unknown_role_is_not_silently_replaced(self):
        with self.assertRaisesRegex(ValueError, "ROLE_UNKNOWN"):
            build_voice_design(request(), role="bogus")

    def test_greeting_uses_natural_korean_name_particle(self):
        self.assertIn(
            "몽글콩이랑", build_voice_design(request(), {"displayName": "몽글콩"})["greeting"]
        )
        self.assertIn("모리랑", build_voice_design(request(), {"displayName": "모리"})["greeting"])

    def test_distinct_situations_have_distinct_bindings_without_claiming_unique_speakers(self):
        plans = [build_voice_design(request(identity=f"journey-{n}")) for n in range(200)]
        self.assertEqual(len({p["profileId"] for p in plans}), 200)
        self.assertEqual(len({p["seed"] for p in plans}), 200)
        self.assertTrue(all(not p["speakerUniquenessVerified"] for p in plans))

    def test_companion_greeting_duration_rejects_missing_or_excessively_long_speech(self):
        text = "서울역 가는 길, 몽글누리랑 함께해요. 오늘 일정, 차근차근 함께해요."
        validate_speech_duration(text, 6800)
        for duration in (200, 21600):
            with self.subTest(duration=duration), self.assertRaisesRegex(ValueError, "SPEECH_TOO_"):
                validate_speech_duration(text, duration)

    def test_explicit_fictional_child_keeps_reading_purpose_without_adult_colleague_voice(self):
        for description in (
            "어린 아이 캐릭터",
            "어린아이캐릭터",
            "어린이 캐릭터",
            "초등학생 캐릭터",
            "초등 학생 가상 캐릭터",
            "꼬마 눈티",
            "꼬마눈티",
        ):
            with self.subTest(description=description):
                plan = build_voice_design(
                    request(description + "가 도서관에서 책 읽기"),
                    {"characterPlan": {"purpose": {"role": "STUDY"}}},
                )
                self.assertEqual(plan["characterAge"]["value"], "CHILD")
                self.assertEqual(plan["ageImpression"], "youthful-fictional")
                self.assertIn("bookish curiosity", plan["instruct"])
                self.assertNotIn("friendly capable colleague", plan["instruct"])
                self.assertIn("책 속의 이야기", plan["greeting"])
                self.assertNotIn("오늘 일정", plan["greeting"])
                self.assertFalse(plan["realPersonReference"])
                self.assertFalse(plan["humanListeningVerified"])
                validate_voice_plan(plan)

    def test_companions_and_place_names_do_not_assign_character_age(self):
        for purpose in (
            "아이와 데이트",
            "초등학생과 도서관에서 책 읽기",
            "어린 아이와 눈티가 함께 독서",
            "어린이 캐릭터 박물관 방문",
            "꼬마 눈티 전시관 관람",
        ):
            with self.subTest(purpose=purpose):
                data = request(purpose, destination="어린이 캐릭터 박물관")
                data["destination"]["traits"] = "초등학생 캐릭터와 꼬마 눈티 전시"
                plan = build_voice_design(data, {"characterPlan": {"purpose": {"role": "STUDY"}}})
                self.assertNotIn("characterAge", plan)
                self.assertEqual(plan["ageImpression"], "adult")

    def test_negated_conflicting_and_undecided_character_ages_remain_unspecified(self):
        for purpose in (
            "어린이 캐릭터는 아니고 책 읽기",
            "초등학생 캐릭터를 원하지 않아요",
            "꼬마 눈티로 만들지 말아 주세요",
            "어린이 캐릭터로 하지 마",
            "초등학생 캐릭터로는 절대 안 해요",
            "꼬마 눈티는 별로 원치 않아요",
            "성인 캐릭터와 어린이 캐릭터 중 고르기",
            "성인 어린이 캐릭터",
            "어른 같은 초등학생 캐릭터",
            "어린이 캐릭터인지 성인 캐릭터인지 미정",
            "초등학생 캐릭터로 할지 아직 고민",
        ):
            with self.subTest(purpose=purpose):
                plan = build_voice_design(
                    request(purpose), {"characterPlan": {"purpose": {"role": "STUDY"}}}
                )
                self.assertEqual(plan["characterAge"]["resolution"], "UNKNOWN")
                self.assertIsNone(plan["characterAge"]["value"])
                self.assertEqual(plan["ageImpression"], "unspecified")
                self.assertIn("age-unspecified", plan["instruct"])
                validate_voice_plan(plan)

    def test_uncertain_destination_or_activity_does_not_erase_explicit_character_age(self):
        plan = build_voice_design(
            request("어린이 캐릭터, 여행 목적은 아직 미정"),
            {"characterPlan": {"purpose": {"role": "EXPLORE", "resolution": "UNKNOWN"}}},
        )
        self.assertEqual(plan["characterAge"]["value"], "CHILD")

    def test_explicit_adult_aquatic_character_does_not_inherit_childlike_timbre(self):
        plan = build_voice_design(
            request("성인 가상 캐릭터가 수영하기"),
            {"characterPlan": {"purpose": {"role": "SWIM"}}},
        )
        self.assertEqual(plan["role"], "swimmer")
        self.assertEqual(plan["characterAge"]["value"], "ADULT")
        self.assertEqual(plan["ageImpression"], "adult")
        self.assertIn("Sunny aquatic playfulness", plan["instruct"])
        self.assertNotIn("Youthful buoyant timbre", plan["instruct"])

    def test_explicit_age_remains_part_of_immutable_voice_binding(self):
        data = request("꼬마 눈티가 책 읽기")
        design = {"characterPlan": {"purpose": {"role": "STUDY"}}}
        plan = build_voice_design(data, design)
        self.assertEqual(plan, build_voice_design(data, design))
        plan["characterAge"]["value"] = "ADULT"
        with self.assertRaisesRegex(ValueError, "BINDING_MISMATCH"):
            validate_voice_plan(plan)


class VoiceCacheTest(unittest.TestCase):
    def setUp(self):
        gate = patch("nunti.avatar_studio.voice_render._gpu_lock", nullcontext)
        gate.start()
        self.addCleanup(gate.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.plan = build_voice_design(request())
        text = self.plan["greeting"]
        self.text_sha = hashlib.sha256(text.encode()).hexdigest()
        self.clip = self.root / self.plan["profileId"] / self.text_sha
        self.clip.mkdir(parents=True)
        self.wav = self.clip / "audio.wav"
        # A non-silent PCM fixture tests storage, not synthesis quality.
        with wave.open(str(self.wav), "wb") as target:
            target.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
            target.writeframes(array("h", [1000, -1000] * 24000).tobytes())
        self.record = {
            "profileId": self.plan["profileId"],
            "text": text,
            "textSha256": self.text_sha,
            "planSha256": hashlib.sha256(canonical(self.plan).encode()).hexdigest(),
            "modelId": VOICE_MODEL,
            "revision": VOICE_REVISION,
            "referenceAudioSha256": None,
            **inspect_wav(self.wav),
        }
        (self.clip / "metadata.json").write_text(json.dumps(self.record))

    def test_cache_returns_actual_wav_without_loading_gpu(self):
        renderer = LocalVoiceRenderer()
        with patch.object(
            renderer, "_load", side_effect=AssertionError("GPU should remain unloaded")
        ):
            result = renderer.render(self.plan, self.root)
        self.assertTrue(result["cacheHit"])
        self.assertEqual(result["audioSha256"], hashlib.sha256(self.wav.read_bytes()).hexdigest())

    def test_cache_tamper_rejected_instead_of_recreating_identity(self):
        with self.wav.open("ab") as target:
            target.write(b"changed")
        with self.assertRaisesRegex(ValueError, "AUDIO_CHANGED"):
            LocalVoiceRenderer().render(self.plan, self.root)

    def test_partial_completed_cache_is_not_silently_replaced(self):
        (self.clip / "metadata.json").unlink()
        with self.assertRaisesRegex(ValueError, "INCOMPLETE"):
            LocalVoiceRenderer().render(self.plan, self.root)

    def test_invalid_text_is_rejected_before_gpu_load(self):
        with self.assertRaisesRegex(ValueError, "TEXT_INVALID"):
            LocalVoiceRenderer().render(self.plan, self.root, "bad\x00text")


if __name__ == "__main__":
    unittest.main()
