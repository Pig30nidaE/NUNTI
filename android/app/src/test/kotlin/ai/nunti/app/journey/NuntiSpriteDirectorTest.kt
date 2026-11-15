package ai.nunti.app.journey

import ai.nunti.app.journey.NuntiSpriteDirector.Stage
import org.junit.Assert.*
import org.junit.Test
import java.io.File
import java.security.MessageDigest

class NuntiSpriteDirectorTest {
    private val shot = NuntiSpriteDirector.Shot()
    private fun at(stage: Stage, t: Float, tap: Float = -1f, animated: Boolean = true, range: Float = 400f) =
        shot.also { NuntiSpriteDirector.sample(stage, t, tap, animated, range, it) }

    @Test fun drivingNeverMovesAndSits() {
        for (i in 0..200) {
            val s = at(Stage.DRIVING, i * .37f, animated = false)
            assertEquals(NuntiSpriteDirector.SIT, s.clip); assertEquals(0f, s.dx, 0f); assertEquals(0f, s.breath, 0f)
        }
    }

    @Test fun screensPickTheAgreedActions() {
        assertEquals(Stage.REPORT_GOOD, NuntiSpriteDirector.stageFor(false, false, true, 85.0))
        assertEquals(Stage.REPORT_LOW, NuntiSpriteDirector.stageFor(false, false, true, 62.0))
        assertEquals(Stage.REPORT_LOW, NuntiSpriteDirector.stageFor(false, false, true, null))
        assertEquals(Stage.PARKED, NuntiSpriteDirector.stageFor(true, false, false, null))
        assertEquals(Stage.EMPTY, NuntiSpriteDirector.stageFor(false, false, false, null))
        // 출발 준비 화면에 들어오면 먼저 한 번 뛴다.
        assertEquals(NuntiSpriteDirector.JUMP, at(Stage.PARKED, .2f).clip)
        // 점수가 낮으면 팔짱을 끼고 그대로 있는다.
        assertEquals(NuntiSpriteDirector.FOLD to NuntiSpriteDirector.FOLD_LAST, at(Stage.REPORT_LOW, 5f).let { it.clip to it.frame })
        assertEquals(NuntiSpriteDirector.JUMP, at(Stage.REPORT_GOOD, .5f).clip)
        assertEquals(NuntiSpriteDirector.SIT, at(Stage.EMPTY, 3f).clip)
        // 서 있을 때는 기본 눈티 원본 그림을 쓴다 (점프 끝·주차 중 정지 화면).
        assertEquals(NuntiSpriteDirector.STAND, at(Stage.PARKED, NuntiSpriteDirector.JUMP_SECONDS + 1f).clip)
        assertEquals(NuntiSpriteDirector.STAND, at(Stage.PARKED, 9f, animated = false).clip)
        assertEquals(NuntiSpriteDirector.STAND, at(Stage.REPORT_GOOD, 3f).clip)
    }

    @Test fun wanderWalksBothWaysFoldsArmsAndComesBackWithoutJumps() {
        val seen = HashSet<String>()
        var lastDx = 0f
        val dt = 1f / 60
        var t = NuntiSpriteDirector.JUMP_SECONDS
        while (t < 80f) {
            val s = at(Stage.PARKED, t)
            seen += s.clip
            // 한 화면에서 다음 화면으로 순간 이동하지 않는다 (걷기 속도 이하).
            assertTrue("t=$t", kotlin.math.abs(s.dx - lastDx) <= NuntiSpriteDirector.WALK_SPEED * dt + .01f || t < NuntiSpriteDirector.JUMP_SECONDS + dt * 2)
            // 정해 둔 범위 밖으로 걸어 나가지 않는다.
            assertTrue(kotlin.math.abs(s.dx) <= NuntiSpriteDirector.MAX_WANDER + .01f)
            lastDx = s.dx; t += dt
        }
        assertTrue(seen.containsAll(listOf(NuntiSpriteDirector.WALK_R, NuntiSpriteDirector.WALK_L, NuntiSpriteDirector.FOLD)))
    }

    @Test fun narrowScreenStaysInPlace() {
        var t = NuntiSpriteDirector.JUMP_SECONDS
        while (t < 60f) { val s = at(Stage.PARKED, t, range = 30f); assertEquals(0f, s.dx, 0f); assertFalse(s.clip.startsWith("walk")); t += .05f }
    }

    @Test fun tapJumpsInPlace() {
        val walking = at(Stage.PARKED, 10f).dx
        val s = at(Stage.PARKED, 10f, tap = .4f)
        assertEquals(NuntiSpriteDirector.JUMP, s.clip); assertEquals(walking, s.dx, 0f)
    }

    // ---- 에셋 ----
    private val root = generateSequence(File("").absoluteFile) { it.parentFile }
        .map { File(it, "prototypes/avatar_generator") }.first { it.isDirectory }
    private val manifest = File(root, "nunti-sprites/manifest.json").readText()

    @Test fun everyFrameExistsWithTheRecordedHashAndClipsHaveTheExpectedLength() {
        assertTrue(manifest.contains("\"version\": \"${NuntiSpriteRig.VERSION}\""))
        assertTrue("not approved until a person reviews it", Regex("\"humanQualityApproved\"\\s*:\\s*false").containsMatchIn(manifest))
        val counts = mapOf("walkR" to 8, "walkL" to 8, "fold" to 3, "jump" to 3, "sitChair" to 1, "sitBody" to 1, "stand" to 1)
        for ((clip, count) in counts) {
            for (i in 0 until count) {
                val path = "nunti-sprites/${clip}_$i.webp"
                val hash = Regex("\"path\"\\s*:\\s*\"${Regex.escape(path)}\"[^}]*\"sha256\"\\s*:\\s*\"([0-9a-f]{64})\"").find(manifest)!!.groupValues[1]
                val sha = MessageDigest.getInstance("SHA-256").digest(File(root, path).readBytes()).joinToString("") { "%02x".format(it) }
                assertEquals(path, hash, sha)
            }
            assertFalse("$clip has no extra frame", manifest.contains("nunti-sprites/${clip}_$count.webp"))
        }
    }
}
