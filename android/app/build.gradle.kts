plugins { id("com.android.application"); kotlin("android"); kotlin("plugin.compose") }
android {
    namespace = "ai.nunti.app"
    compileSdk = 35
    useLibrary("android.car")
    defaultConfig { applicationId = "ai.nunti.avatar.demo"; minSdk = 28; targetSdk = 35; versionCode = 1; versionName = "0.1.0-mock" }
    buildFeatures { compose = true }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    if (findProject(":feature:tts") != null) sourceSets["main"].java.srcDir("src/voiceIntegration/kotlin")
}
kotlin { compilerOptions { jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17) } }
dependencies {
    implementation(project(":feature:avatar"))
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.compose.foundation:foundation:1.8.3")
    implementation("androidx.compose.runtime:runtime-saveable:1.8.3")
    if (findProject(":feature:tts") != null) implementation(project(":feature:tts"))
    if (findProject(":feature:voice") != null) implementation(project(":feature:voice"))
}
