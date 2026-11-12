package ai.nunti.app

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity

/** Production and Debug use the same parked avatar-generation host. */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val host = if (ai.nunti.app.journey.JourneyRuntime.isRunning) ai.nunti.app.journey.JourneyActivity::class.java
            else ai.nunti.app.studio.AvatarStudioActivity::class.java
        startActivity(Intent(this, host).addFlags(
            Intent.FLAG_ACTIVITY_REORDER_TO_FRONT or Intent.FLAG_ACTIVITY_SINGLE_TOP,
        ))
        finish()
    }
}
