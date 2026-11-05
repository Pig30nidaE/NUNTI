package ai.nunti.app.navigation

import ai.pleos.playground.navi.constants.NaviErrorCode
import ai.pleos.playground.navi.constants.NavigationStatus
import ai.pleos.playground.navi.constants.RouteOption
import ai.pleos.playground.navi.data.CurrentLocationInfo
import ai.pleos.playground.navi.data.DestinationInfo
import ai.pleos.playground.navi.data.NavigationScreenRequest
import ai.pleos.playground.navi.data.RouteInfo
import ai.pleos.playground.navi.data.RouteOverviewShowInfo
import ai.pleos.playground.navi.data.RouteStartInfo
import ai.pleos.playground.navi.data.RouteStateInfo
import ai.pleos.playground.navi.data.TBTInfo
import ai.pleos.playground.navi.data.TripInfo
import ai.pleos.playground.navi.data.TripRequest
import ai.pleos.playground.navi.helper.NaviHelper
import ai.pleos.playground.navi.helper.listener.NaviHelperEventListener
import android.content.Context
import android.os.Handler
import android.os.Looper
import java.io.File
import java.time.Instant
import java.util.UUID
import java.util.concurrent.Executors
import kotlinx.serialization.SerializationStrategy
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json
import org.json.JSONArray
import org.json.JSONObject

/** Public NaviHelper calls only. Route summary POIs are never exposed as a road polyline. */
class PleosNavigationAdapter(
    context: Context,
    private val onChanged: (String) -> Unit,
) : AutoCloseable {
    private val context = context.applicationContext
    private val main = Handler(Looper.getMainLooper())
    private val writer = Executors.newSingleThreadExecutor()
    private val lock = Any()
    private val json = Json { encodeDefaults = true }
    private val sessionId = UUID.randomUUID().toString()
    private val startedAt = now()
    private var helper: NaviHelper? = null
    private var connection = "DISCONNECTED"
    private var closed = false
    private var sequence = 0L
    private var revision = 0L
    private var receivedCallbacks = 0L
    private var updatedAt = startedAt
    private var destination: JSONObject? = null
    private var currentLocation: JSONObject? = null
    private var routeState: JSONObject? = null
    private var trip: JSONObject? = null
    private var tbt = JSONArray()
    private var latestError: JSONObject? = null
    private var routeLifecycle = "UNKNOWN"
    private val events = ArrayDeque<JSONObject>()

    private fun now(): String = Instant.now().toString()
    private fun <T> encode(serializer: SerializationStrategy<T>, value: T) =
        json.encodeToString(serializer, value)

    private val listener = object : NaviHelperEventListener {
        override fun onDestinationInfo(destinationInfo: DestinationInfo) = receive(
            "onDestinationInfo", JSONObject(encode(DestinationInfo.serializer(), destinationInfo)),
        ) { destination = it }

        override fun onCurrentLocationInfo(currentLocationInfo: CurrentLocationInfo) = receive(
            "onCurrentLocationInfo", JSONObject(encode(CurrentLocationInfo.serializer(), currentLocationInfo)),
        ) { currentLocation = it }

        override fun onRouteStateInfo(routeStateInfo: RouteStateInfo) = receive(
            "onRouteStateInfo", JSONObject(encode(RouteStateInfo.serializer(), routeStateInfo)),
        ) { routeState = it }

        override fun onTripInfo(tripInfo: TripInfo) = receive(
            "onTripInfo", JSONObject(encode(TripInfo.serializer(), tripInfo)),
        ) { trip = it }

        override fun onTBTInfo(tbtInfoList: List<TBTInfo>) {
            val values = JSONArray(encode(ListSerializer(TBTInfo.serializer()), tbtInfoList))
            receive("onTBTInfo", JSONObject().put("items", values)) { tbt = it.getJSONArray("items") }
        }

        override fun onRouteStarted(routeStartInfo: RouteStartInfo) = routeEvent(
            "onRouteStarted", JSONObject(encode(RouteStartInfo.serializer(), routeStartInfo)), "ROUTING_STARTED",
        )
        override fun onRoutingCompleted() = routeEvent("onRoutingCompleted", JSONObject(), "READY")
        override fun onReRouteEnded() = routeEvent("onReRouteEnded", JSONObject(), "REROUTED")
        override fun onRouteOptionChanged(routeOption: RouteOption) = routeEvent(
            "onRouteOptionChanged", JSONObject().put("option", routeOption.name), "OPTION_CHANGED",
        )
        override fun onDestinationChanged() = routeEvent("onDestinationChanged", JSONObject(), "DESTINATION_CHANGED")
        @Deprecated("Use onRoutingCompleted() instead")
        override fun onRouteEnded() = routeEvent("onRouteEnded", JSONObject(), "READY")
        override fun onRouteCancelled() = routeEvent("onRouteCancelled", JSONObject(), "CANCELLED")
        override fun onNavigationStatus(status: NavigationStatus) = receive(
            "onNavigationStatus", JSONObject().put("status", status.name),
        ) {}
        override fun onError(errorCode: NaviErrorCode) = receive(
            "onError", JSONObject().put("code", errorCode.name),
        ) { latestError = it }
    }

    fun start() {
        main.post {
            synchronized(lock) {
                if (closed || connection == "CONNECTING" || connection == "CONNECTED") return@post
                connection = "CONNECTING"
                latestError = null
            }
            publish("CONNECTING", JSONObject())
            try {
                helper?.release()
                val next = NaviHelper(context)
                helper = next
                next.initialize({
                    main.post {
                        if (synchronized(lock) { closed } || helper !== next) return@post
                        synchronized(lock) { connection = "CONNECTED" }
                        next.addListener(listener)
                        publish("CONNECTED", JSONObject())
                        queryCurrent(next)
                    }
                }, { error -> main.post { fail("CONNECTION_FAILED", error) } })
                main.postDelayed({
                    if (synchronized(lock) { !closed && connection == "CONNECTING" } && helper === next) {
                        synchronized(lock) {
                            connection = "FAILED"
                            latestError = JSONObject().put("code", "CONNECTION_TIMEOUT")
                        }
                        publish("CONNECTION_TIMEOUT", JSONObject())
                    }
                }, 12_000)
            } catch (error: Exception) { fail("INITIALIZE_FAILED", error) }
        }
    }

    /** Thread-safe JSON for the WebView bridge and the emulator's app-private diagnostic file. */
    fun snapshot(): String = synchronized(lock) {
        JSONObject()
            .put("schemaVersion", 1)
            .put("source", "PLEOS_NAVI_HELPER_API")
            .put("sdkVersion", "3.0.5")
            .put("sessionId", sessionId)
            .put("sessionStartedAt", startedAt)
            .put("status", connection)
            .put("connected", connection == "CONNECTED")
            .put("sequence", sequence)
            .put("revision", revision)
            .put("updatedAt", updatedAt)
            .put("receivedCallbackCount", receivedCallbacks)
            .put("routeLifecycle", routeLifecycle)
            .put("destination", destination ?: JSONObject.NULL)
            .put("currentLocation", currentLocation ?: JSONObject.NULL)
            .put("routeState", routeState ?: JSONObject.NULL)
            .put("trip", trip ?: JSONObject.NULL)
            .put("tbt", tbt)
            .put("geometryStatus", "NOT_PROVIDED_BY_PUBLIC_SDK")
            .put("tripRoutePointsRole", "WAYPOINT_DESTINATION_SUMMARY_NOT_ROAD_POLYLINE")
            .put("coordinateSystem", "WGS84_LATITUDE_LONGITUDE")
            .put("units", JSONObject().put("distance", "m").put("time", "s").put("heading", "degrees").put("ratioOnRoute", "percent_0_100"))
            .put("lastError", latestError ?: JSONObject.NULL)
            .put("eventCapacity", 256)
            .put("events", JSONArray(events.toList()))
            .toString()
    }

    /** Returns command receipt, not a fabricated SDK result. Results arrive through real callbacks. */
    fun dispatch(command: String, payloadJson: String = "{}"): String {
        val action = try { parse(command, payloadJson) }
        catch (_: Exception) { return JSONObject().put("accepted", false).put("error", "INVALID_NAVIGATION_COMMAND").toString() }
        if (synchronized(lock) { closed }) return JSONObject().put("accepted", false).put("error", "NAVIGATION_CLOSED").toString()
        val requestId = UUID.randomUUID().toString()
        main.post {
            if (action is Command.Connect) { start(); return@post }
            val sdk = helper
            if (sdk == null || synchronized(lock) { connection != "CONNECTED" }) {
                publish("COMMAND_REJECTED", JSONObject().put("requestId", requestId).put("command", command).put("code", "NOT_CONNECTED"))
                return@post
            }
            try {
                when (action) {
                    Command.Connect -> Unit
                    Command.Refresh -> queryCurrent(sdk)
                    is Command.Route -> sdk.requestRoute(action.info)
                    is Command.Trip -> sdk.requestTrip(action.info)
                    is Command.Option -> sdk.changeRouteOption(action.option)
                    Command.Reroute -> sdk.requestReRoute()
                    is Command.Overview -> sdk.requestNavigationScreen(NavigationScreenRequest.OverviewRoute(RouteOverviewShowInfo(action.durationMs)))
                    Command.Foreground -> sdk.requestNavigationScreen(NavigationScreenRequest.Foreground)
                    Command.Cancel -> sdk.cancelRoute()
                }
                publish("COMMAND_DISPATCHED", JSONObject().put("requestId", requestId).put("command", command))
            } catch (error: Exception) { fail("SDK_CALL_FAILED", error, requestId) }
        }
        return JSONObject().put("accepted", true).put("status", "QUEUED").put("requestId", requestId).put("command", command).toString()
    }

    private sealed interface Command {
        data object Connect : Command
        data object Refresh : Command
        data class Route(val info: RouteInfo) : Command
        data class Trip(val info: TripRequest) : Command
        data class Option(val option: RouteOption) : Command
        data object Reroute : Command
        data class Overview(val durationMs: Int) : Command
        data object Foreground : Command
        data object Cancel : Command
    }

    private fun parse(command: String, payloadJson: String): Command {
        require(payloadJson.length <= 16_384)
        val p = JSONObject(payloadJson)
        fun coordinate(key: String, maximum: Double): Double = p.getDouble(key).also { require(it.isFinite() && it in -maximum..maximum) }
        fun text(key: String, fallback: String = ""): String = p.optString(key, fallback).also { require(it.length <= 240 && it.none { c -> c.code < 32 }) }
        return when (command) {
            "connect" -> Command.Connect
            "refresh" -> Command.Refresh
            "requestRoute" -> Command.Route(RouteInfo(
                latitude = coordinate("latitude", 90.0), longitude = coordinate("longitude", 180.0),
                poiName = text("name").also { require(it.isNotBlank()) }, poiId = text("poiId"), address = text("address"), poiSubId = text("poiSubId"),
                poiProvider = text("poiProvider"), routeOption = RouteOption.valueOf(p.optString("option", "RECOMMENDED")),
            ))
            "requestTrip" -> Command.Trip(TripRequest(
                latitude = coordinate("latitude", 90.0), longitude = coordinate("longitude", 180.0),
                poiName = text("name").also { require(it.isNotBlank()) }, poiId = text("poiId"), poiSubId = text("poiSubId").ifBlank { null },
            ))
            "changeRouteOption" -> Command.Option(RouteOption.valueOf(p.getString("option")))
            "reroute" -> Command.Reroute
            "overview" -> Command.Overview(p.optInt("durationMs", 15_000).also { require(it in 1_000..120_000) })
            "foreground" -> Command.Foreground
            "cancelRoute" -> Command.Cancel
            else -> error("UNKNOWN_COMMAND")
        }
    }

    private fun queryCurrent(sdk: NaviHelper) {
        try {
            sdk.getDestinationInfo()
            sdk.getRouteStateInfo()
            sdk.getCurrentLocationInfo()
            sdk.getTBTInfo()
        } catch (error: Exception) { fail("SDK_QUERY_FAILED", error) }
    }

    private fun receive(type: String, payload: JSONObject, apply: (JSONObject) -> Unit) {
        main.post {
            if (synchronized(lock) { closed }) return@post
            synchronized(lock) { receivedCallbacks++; apply(payload) }
            publish(type, payload)
        }
    }

    private fun routeEvent(type: String, payload: JSONObject, lifecycle: String) = receive(type, payload) {
        revision++
        routeLifecycle = lifecycle
        if (lifecycle == "CANCELLED") { destination = null; trip = null; tbt = JSONArray() }
        main.post { helper?.let(::queryCurrent) }
    }

    private fun fail(code: String, error: Throwable, requestId: String? = null) {
        synchronized(lock) {
            if (closed) return
            if (code.startsWith("CONNECTION") || code == "INITIALIZE_FAILED") connection = "FAILED"
            latestError = JSONObject().put("code", code).put("kind", error.javaClass.simpleName)
            if (requestId != null) latestError?.put("requestId", requestId)
        }
        publish(code, JSONObject().put("kind", error.javaClass.simpleName).put("requestId", requestId ?: JSONObject.NULL))
    }

    private fun publish(type: String, payload: JSONObject) {
        val event = synchronized(lock) {
            sequence++
            updatedAt = now()
            JSONObject().put("sequence", sequence).put("at", updatedAt).put("type", type).put("source", "PLEOS_NAVI_HELPER_API").put("payload", payload).also {
                events.addLast(it)
                while (events.size > 256) events.removeFirst()
            }
        }
        val body = snapshot()
        writer.execute {
            runCatching {
                val file = File(context.filesDir, "navigation-api-snapshot.json")
                val pending = File(context.filesDir, "navigation-api-snapshot.pending")
                pending.writeText(body)
                check(pending.renameTo(file))
                val journal = File(context.filesDir, "navigation-api-events.jsonl")
                if (journal.length() > 4 * 1024 * 1024) {
                    val previous = File(context.filesDir, "navigation-api-events.previous.jsonl")
                    previous.delete()
                    check(journal.renameTo(previous))
                }
                journal.appendText(event.toString() + "\n")
            }
        }
        if (Looper.myLooper() == Looper.getMainLooper()) onChanged(body) else main.post { onChanged(body) }
    }

    override fun close() {
        main.post {
            if (synchronized(lock) { closed }) return@post
            runCatching { helper?.removeListener(listener) }
            runCatching { helper?.release() }
            helper = null
            synchronized(lock) { closed = true; connection = "CLOSED" }
            publish("CLOSED", JSONObject())
            writer.shutdown()
        }
    }
}
