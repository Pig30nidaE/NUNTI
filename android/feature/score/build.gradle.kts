plugins {
    id("com.android.library")
    kotlin("android")
    kotlin("plugin.compose")
}

android {
    namespace = "ai.nunti.score"
    compileSdk = 35
    useLibrary("android.car")

    defaultConfig {
        minSdk = 28
    }
    buildFeatures {
        compose = true
    }
    sourceSets {
        getByName("main") { java.srcDirs("src/main/kotlin") }
        getByName("test") { java.srcDirs("src/test/kotlin") }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}

dependencies {
    // 점수 엔진(score/)은 순수 Kotlin. live/ 는 Pleos SDK, ui/ 는 Compose.
    implementation(platform("androidx.compose:compose-bom:2025.05.01"))
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("ai.pleos.playground:Vehicle:2.3.2")
    implementation("ai.pleos.playground:vehicle-aidl:1.1.1") // RawSpeedProbe: 공개 SDK에 없는 차속 직접 구독
    implementation("ai.pleos.playground:NaviHelper:3.0.5")
    // 눈티 음성: Pleos TextToSpeech SDK 래퍼(:feature:voice)와 발화 큐·정책(:feature:tts)
    implementation(project(":feature:tts"))
    implementation(project(":feature:voice"))
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20250517") // android.jar 의 org.json 은 JVM 시험에서 동작하지 않는다
}
