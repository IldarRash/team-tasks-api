package com.ildarrash.teamtasks.nativeimage

import org.springframework.aot.hint.RuntimeHints
import org.springframework.aot.hint.RuntimeHintsRegistrar

/** Resources that Flyway resolves from the runtime classpath. */
class TeamTasksRuntimeHints : RuntimeHintsRegistrar {
    override fun registerHints(hints: RuntimeHints, classLoader: ClassLoader?) {
        hints.resources().registerPattern("db/migration/*.sql")
    }
}
