pluginManagement { repositories { google(); mavenCentral(); gradlePluginPortal() } }
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google(); mavenCentral()
        maven("https://nexus-playground.pleos.ai/repository/maven-releases/")
    }
}
rootProject.name = "Nunti"
include(":app", ":feature:navigation", ":feature:emotion", ":feature:avatar")
// TTS owns these modules. A checkout override supports isolated team worktrees.
val voiceCheckout = providers.gradleProperty("nuntiTtsCheckout").orNull?.let(::file) ?: rootDir
if (file("$voiceCheckout/feature/tts/build.gradle.kts").exists() && file("$voiceCheckout/feature/voice/build.gradle.kts").exists()) {
    include(":feature:tts", ":feature:voice")
    project(":feature:tts").projectDir = file("$voiceCheckout/feature/tts")
    project(":feature:voice").projectDir = file("$voiceCheckout/feature/voice")
}
