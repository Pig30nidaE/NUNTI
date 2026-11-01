plugins { kotlin("jvm") }
java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}
kotlin {
    jvmToolchain(21)
    compilerOptions { jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17) }
}
tasks.register<JavaExec>("verifySpeech") {
    dependsOn(tasks.testClasses)
    classpath = sourceSets.test.get().runtimeClasspath
    mainClass.set("ai.nunti.tts.SpeechSystemTestKt")
}
tasks.check { dependsOn("verifySpeech") }
tasks.register<JavaExec>("demo") {
    classpath = sourceSets.main.get().runtimeClasspath
    mainClass.set("ai.nunti.tts.SpeechDemoKt")
}
