plugins {
    id("com.android.application") version "8.10.1" apply false
    id("com.android.library") version "8.10.1" apply false
    kotlin("jvm") version "2.2.21" apply false
    kotlin("android") version "2.2.21" apply false
    kotlin("plugin.compose") version "2.2.21" apply false
}
// Keep external module build output in this checkout, never in another session's worktree.
subprojects { layout.buildDirectory.set(rootProject.layout.projectDirectory.dir("build/${path.replace(':', '/')}")) }
