plugins { id("com.android.application"); kotlin("android"); kotlin("plugin.compose") }
android {
    namespace = "ai.nunti.app"
    compileSdk = 36
    useLibrary("android.car")
    defaultConfig { applicationId = "ai.nunti.avatar.demo"; minSdk = 28; targetSdk = 35; versionCode = 1; versionName = "0.1.0-mock" }
    defaultConfig { testInstrumentationRunner = "ai.nunti.app.journey.CompanionRigInstrumentation" }
    buildFeatures { compose = true }
    // Ship the existing Studio UI with the app; only its data APIs require the server.
    sourceSets["main"].assets.srcDir("../../prototypes/avatar_generator")
    sourceSets["main"].assets.exclude("examples/**", "*.mjs")
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    if (findProject(":feature:tts") != null) sourceSets["main"].java.srcDir("src/voiceIntegration/kotlin")
}
kotlin { compilerOptions { jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17) } }
dependencies {
    testImplementation("junit:junit:4.13.2")
    implementation("ai.pleos.playground:NaviHelper:3.0.5")
    implementation("ai.pleos.playground:FusedLocation:1.1.3")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.3")
    implementation(project(":feature:avatar"))
    implementation(project(":feature:score"))
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.compose.foundation:foundation:1.8.3")
    implementation("androidx.compose.runtime:runtime-saveable:1.8.3")
    if (findProject(":feature:tts") != null) implementation(project(":feature:tts"))
    if (findProject(":feature:voice") != null) implementation(project(":feature:voice"))
}
