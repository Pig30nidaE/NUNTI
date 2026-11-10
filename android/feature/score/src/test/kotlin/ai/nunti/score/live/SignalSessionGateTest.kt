package ai.nunti.score.live

import org.junit.Assert.*
import org.junit.Test

class SignalSessionGateTest {
    @Test
    fun repeatedStartDoesNotClearReadingsOrCreateAnotherSubscription() {
        val gate = SignalSessionGate()
        var speed: Float? = null
        var resets = 0
        val epoch = gate.begin { resets++; speed = null }!!
        gate.accept(epoch) { speed = 30f }
        assertNull(gate.begin { resets++; speed = null })
        assertEquals(1, resets)
        assertEquals(30f, speed!!, 0f)
        assertEquals(epoch, gate.current())
    }

    @Test
    fun stoppedAndPreviousSessionCallbacksCannotRepopulateNewReadings() {
        val gate = SignalSessionGate()
        var speed: Float? = null
        val first = gate.begin { speed = null }!!
        gate.accept(first) { speed = 70f }
        assertTrue(gate.end { speed = null })
        assertFalse(gate.end { fail("Second stop must not run teardown twice") })
        assertFalse(gate.accept(first) { speed = 100f })
        val second = gate.begin { speed = null }!!
        assertNotEquals(first, second)
        assertFalse(gate.accept(first) { speed = 100f })
        assertNull(speed)
        assertTrue(gate.accept(second) { speed = 0f })
        assertEquals(0f, speed!!, 0f)
    }

    @Test
    fun partialDoorReadingsCannotClaimAllDoorsAreClosed() {
        val expected = setOf("frontLeft", "frontRight", "rearLeft", "rearRight")
        assertNull(aggregateDoorState(emptyMap(), expected))
        assertNull(aggregateDoorState(mapOf("frontLeft" to false), expected))
        assertEquals(true, aggregateDoorState(mapOf("rearLeft" to true), expected))
        assertEquals(false, aggregateDoorState(expected.associateWith { false }, expected))
        assertNull(aggregateDoorState(mapOf("unrelatedDoor" to true), expected))
    }
}
