package ai.nunti.score.ui

import ai.nunti.score.Emotion
import ai.nunti.score.R
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.height
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/** 감정별 눈티 캐릭터 컷. 기준 시트: docs/design/avatar-v6/assets/nunti-base-character.png */
fun Emotion.avatarRes(): Int = when (this) {
    Emotion.NEUTRAL -> R.drawable.nunti_neutral
    Emotion.WORRY -> R.drawable.nunti_worry
    Emotion.RELIEF -> R.drawable.nunti_relief
    Emotion.JOY -> R.drawable.nunti_joy
}

@Composable
fun NuntiFace(emotion: Emotion, modifier: Modifier = Modifier, height: Dp = 120.dp) {
    Image(
        painter = painterResource(emotion.avatarRes()),
        contentDescription = "눈티 ${emotion.label}",
        modifier = modifier.height(height),
    )
}
