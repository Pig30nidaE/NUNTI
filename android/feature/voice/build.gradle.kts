plugins { id("com.android.library"); kotlin("android") }
android {
    namespace = "ai.nunti.voice"
    compileSdk = 35
    useLibrary("android.car")
    defaultConfig { minSdk = 28 }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
}
kotlin {
    jvmToolchain(21)
    compilerOptions { jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17) }
}
dependencies {
    implementation(project(":feature:tts"))
    implementation("ai.pleos.playground:TextToSpeech:3.3.1")
}
