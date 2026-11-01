plugins { id("com.android.library"); kotlin("android"); kotlin("plugin.compose") }
android {
    namespace = "ai.nunti.avatar"
    compileSdk = 35
    defaultConfig { minSdk = 28 }
    useLibrary("android.car")
    buildFeatures { compose = true }
    sourceSets["main"].java.srcDirs("src/main/kotlin", "src/compose/kotlin")
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
}
kotlin { compilerOptions { jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17) } }
dependencies {
    api(project(":feature:navigation"))
    api(project(":feature:emotion"))
    implementation("androidx.compose.foundation:foundation:1.8.3")
    implementation("androidx.compose.ui:ui:1.8.3")
    implementation("androidx.compose.runtime:runtime:1.8.3")
    testImplementation("org.json:json:20250517")
}
