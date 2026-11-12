package ai.nunti.app.journey

import ai.nunti.app.studio.NuntiSkinStyle
import org.junit.Assert.*
import org.junit.Test
import kotlin.math.abs
import kotlin.math.hypot

class NuntiCompanionMotionTest {
    @Test fun gesturesMoveIndependentJointsAndSettle() {
        val pose = NuntiCompanionMotion.Pose()
        NuntiCompanionMotion.sample(1f, "wave-right", .45f, 0f, 0f, pose)
        assertTrue(pose.rightArm < -20f)
        assertEquals(0f, pose.leftArm, .001f)
        val mesh = NuntiCompanionMesh()
        val before = mesh.vertices.copyOf()
        mesh.deform(floatArrayOf(pose.head, pose.leftArm, pose.rightArm, pose.leftLeg, pose.rightLeg))
        fun displacement(col: Int, row: Int): Float {
            val i = (row * (NuntiCompanionMesh.GRID + 1) + col) * 2
            return hypot(mesh.vertices[i] - before[i], mesh.vertices[i + 1] - before[i + 1])
        }
        assertTrue("right sleeve changes pose, not just the whole image", displacement(28, 26) > 25f)
        assertTrue("opposite sleeve stays put", displacement(12, 26) < .01f)
        assertTrue("torso stays pinned", displacement(20, 25) < .01f)
        NuntiCompanionMotion.sample(1f, "wave-left", .45f, 0f, 0f, pose)
        mesh.deform(floatArrayOf(pose.head, pose.leftArm, pose.rightArm, pose.leftLeg, pose.rightLeg))
        assertTrue("the crossbody bag is not stretched by the hand gesture", displacement(15, 28) < .01f)
        mesh.deform(floatArrayOf(pose.head, pose.leftArm, pose.rightArm, pose.leftLeg, pose.rightLeg), rigidArms = true)
        assertTrue("cutout arms are not warped a second time by the body mesh", displacement(11, 27) < .01f)
        NuntiCompanionMotion.sample(1f, "wave-right", 1f, 0f, 0f, pose)
        assertEquals(0f, pose.rightArm, .001f)
        assertEquals(0f, pose.expressionAmount, .001f)
    }

    @Test fun naturalIdleHasQuietGapsAttentionAndWeightChanges() {
        val pose = NuntiCompanionMotion.Pose()
        NuntiCompanionMotion.sample(1f, "idle", 0f, 0f, 0f, pose)
        assertEquals("rest", pose.action)
        NuntiCompanionMotion.sample(4.5f, "idle", 0f, 0f, 0f, pose)
        assertEquals("look", pose.action)
        assertTrue(pose.head < -3f)
        NuntiCompanionMotion.sample(14f, "idle", 0f, 0f, 0f, pose)
        assertEquals("weight-shift", pose.action)
        assertTrue(pose.leftLeg < -3f)
        NuntiCompanionMotion.sample(20f, "idle", 0f, 0f, 0f, pose)
        assertEquals("rest", pose.action)
    }

    @Test fun everyReactionIsFiniteBoundedAndReturnsToRest() {
        val pose = NuntiCompanionMotion.Pose()
        val mesh = NuntiCompanionMesh()
        val angles = FloatArray(5)
        for (reaction in NuntiCompanionMotion.reactions) for (frame in 0..180) {
            NuntiCompanionMotion.sample(26f, reaction, frame / 180f, 1f, -1f, pose)
            angles[0] = pose.head; angles[1] = pose.leftArm; angles[2] = pose.rightArm
            angles[3] = pose.leftLeg; angles[4] = pose.rightLeg
            assertTrue(angles.all { it.isFinite() && abs(it) <= 40f })
            assertTrue(pose.blink in 0f..1f)
            assertTrue(pose.gazeX in -1f..1f && pose.gazeY in -1f..1f)
            mesh.deform(angles)
            assertTrue(mesh.vertices.all { it.isFinite() })
        }
        NuntiCompanionMotion.sample(1f, "pat", .5f, 0f, 0f, pose)
        assertEquals("pat", pose.action)
        assertTrue(pose.blink > .5f)
    }

    @Test fun corruptCoordinatesAreRejectedBeforeDeformation() {
        assertThrows(IllegalArgumentException::class.java) {
            NuntiCompanionMotion.sample(0f, "idle", 0f, Float.NaN, 0f, NuntiCompanionMotion.Pose())
        }
        assertThrows(IllegalArgumentException::class.java) {
            NuntiCompanionMesh().deform(floatArrayOf(0f, 0f, Float.POSITIVE_INFINITY, 0f, 0f))
        }
    }

    @Test fun sharedSkinBindsBothItsImageAndItsRigManifest() {
        val image = "a".repeat(64); val rig = "b".repeat(64)
        val skin = "wardrobe-shared1-$image-$rig"
        assertTrue(NuntiSkinStyle.isWardrobe(skin))
        assertEquals(image, NuntiSkinStyle.imageHash(skin))
        assertEquals(rig, NuntiSkinStyle.rigHash(skin))
        assertFalse(NuntiSkinStyle.isWardrobe("wardrobe-shared1-$image"))
        assertTrue(NuntiSkinStyle.isWardrobe("wardrobe-formal-$image"))
    }
}
