import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    kotlin("jvm") version "2.1.20"
    kotlin("plugin.spring") version "2.1.20"
    id("org.springframework.boot") version "3.5.7"
    id("org.graalvm.buildtools.native") version "0.10.6"
    id("io.spring.dependency-management") version "1.1.7"
    id("io.gatling.gradle") version "3.13.5.3"
}

group = "com.example"
version = "1.0.0"

repositories { mavenCentral() }
java { toolchain { languageVersion = JavaLanguageVersion.of(17) } }
kotlin { compilerOptions { jvmTarget.set(JvmTarget.JVM_17); freeCompilerArgs.add("-Xjsr305=strict") } }

dependencies {
    implementation("org.springframework.boot:spring-boot-starter-web")
    implementation("org.springframework.boot:spring-boot-starter-jdbc")
    implementation("org.springframework.boot:spring-boot-starter-validation")
    implementation("org.springframework.boot:spring-boot-starter-actuator")
    implementation("com.fasterxml.jackson.module:jackson-module-kotlin")
    implementation("org.jetbrains.kotlin:kotlin-reflect")
    implementation("org.flywaydb:flyway-core")
    implementation("org.flywaydb:flyway-database-postgresql")
    runtimeOnly("org.postgresql:postgresql")
    testImplementation("org.springframework.boot:spring-boot-starter-test")
    testImplementation("org.jetbrains.kotlin:kotlin-test-junit5")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}

tasks.withType<Test> { useJUnitPlatform() }
tasks.bootJar { archiveFileName.set("team-tasks-api.jar") }
tasks.jar { enabled = false }

graalvmNative {
    binaries {
        named("main") {
            imageName.set("team-tasks-api")
            classpath.from(sourceSets.main.get().output)
            buildArgs.addAll("-J-Xmx8g", "-H:NumberOfThreads=4")
        }
    }
}

gatling {
    gatlingVersion = "3.13.5"
    includeMainOutput = false
    includeTestOutput = false
    jvmArgs = listOf("-Xms256m", "-Xmx512m", "-Dfile.encoding=UTF-8", "-Dio.netty.eventLoopThreads=8",
        "--add-opens=java.base/java.lang=ALL-UNNAMED", "--add-opens=java.base/jdk.internal.misc=ALL-UNNAMED")
    systemProperties = listOf("baseUrl", "teams", "users", "durationSeconds", "teamBaseId")
        .associateWith { System.getProperty(it, mapOf(
            "baseUrl" to "http://127.0.0.1:8084", "teams" to "1", "users" to "20",
            "durationSeconds" to "60", "teamBaseId" to "7000000000000"
        ).getValue(it)) }
}
