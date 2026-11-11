package ai.nunti.score.journey

import ai.nunti.score.Scenarios
import ai.nunti.score.ScoreEngine
import ai.nunti.score.VehicleSample
import org.junit.Assert.*
import org.junit.Test

class JourneyAnalysisTest {
    @Test fun contextualDriveExplainsEventsAndKeepsSimulationProvenance() {
        val scenario=Scenarios.contextDrive
        val analysis=JourneyAnalysis()
        for(sample in scenario.samples) analysis.observe(sample,
            TripPosition.Simulation(sample.tMs/150000.0,.5),scenario.events.filter { it.tMs<=sample.tMs })
        val report=ScoreEngine().evaluate(scenario.samples,scenario.events)
        val result=analysis.build(report)
        assertEquals(setOf("급가속","급제동","급회전","회전 전 감속 부족"),result.events.map { it.label }.toSet())
        assertTrue(result.events.all { it.position is TripPosition.Simulation && it.evidence.isNotBlank() && it.advice.isNotBlank() })
        assertFalse(result.events.single { it.label=="급회전" }.includedInScore)
        assertTrue(result.habits.any { it.positive })
        assertTrue(result.habits.any { !it.positive })
        assertTrue(result.distanceKm>1)
        assertTrue(result.steeringAvailable)
    }

    @Test fun missingGpsIsNotInferredAndSampleGapDoesNotAddDistanceOrSteeringEvent() {
        val samples=listOf(VehicleSample(0,speedKmh=20f,steeringAngleDeg=0f),
            VehicleSample(1000,speedKmh=50f,steeringAngleDeg=0f),
            VehicleSample(6000,speedKmh=50f,steeringAngleDeg=180f))
        val analysis=JourneyAnalysis()
        samples.forEach { analysis.observe(it,null,emptyList()) }
        val result=analysis.build(ScoreEngine().evaluate(samples,emptyList()))
        assertEquals(35.0/3600,result.distanceKm,0.000001)
        assertTrue(result.events.all { it.position==null })
        assertFalse(result.events.any { it.label=="급회전" })
        assertTrue(analysis.track().isEmpty())
    }

    @Test fun entirelyMissingSignalsDoNotProduceScoreHabitPraiseOrLocations() {
        val samples=(0..20).map { VehicleSample(it*1000L) }
        val analysis=JourneyAnalysis()
        samples.forEach { analysis.observe(it,null,emptyList()) }
        val report=ScoreEngine().evaluate(samples,emptyList())
        val result=analysis.build(report)
        assertNull(report.total)
        assertTrue(result.events.isEmpty())
        assertTrue(result.habits.isEmpty())
        assertFalse(result.steeringAvailable)
        assertEquals(0.0,result.distanceKm,0.0)
    }
}
