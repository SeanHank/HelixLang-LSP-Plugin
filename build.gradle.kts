plugins {
    kotlin("jvm") version "1.8.22"
    id("org.jetbrains.intellij") version "1.14.1"
}

group = "com.helixlang"

val pluginVersion: String by project
version = pluginVersion

repositories {
    mavenCentral()
}

intellij {
    // PyCharm is published to the intellij-repository by product version, not
    // build number. 2022.2.3 == build 222.3345.118 (the PY-222.3345.118 baseline).
    version.set("2022.2.3")
    type.set("PY")
    // No `plugins`: PyCharm CE ships the python core (com.jetbrains.python.*) on
    // its own classpath; IPGP cannot resolve `com.intellij.modules.python` as a
    // builtin plugin for the PY SDK, and it is not needed for compilation.
    updateSinceUntilBuild.set(false) // since-build only; no until-build
}

tasks {
    buildPlugin { }
    verifyPlugin { }
    patchPluginXml {
        sinceBuild.set("222.0")
    }
}

kotlin {
    jvmToolchain(17)
}

tasks.test {
    useJUnitPlatform()
    systemProperty("idea.force.use.core.classloader", "true")
}

dependencies {
    testImplementation(kotlin("test"))
    testImplementation("org.junit.jupiter:junit-jupiter:5.9.3")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}
