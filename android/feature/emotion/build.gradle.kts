plugins { kotlin("jvm") }
java { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
kotlin { compilerOptions { jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17) } }
dependencies { implementation(project(":feature:navigation")) }

kotlin { jvmToolchain(21) }
tasks.register<JavaExec>("verifyEmotion") {
    dependsOn(tasks.testClasses)
    classpath = sourceSets.test.get().runtimeClasspath
    mainClass.set("ai.nunti.emotion.EmotionGoldenKt")
    args(file("src/test/resources/golden.txt").path, if (project.hasProperty("update")) "update" else "check")
}
tasks.check { dependsOn("verifyEmotion") }
