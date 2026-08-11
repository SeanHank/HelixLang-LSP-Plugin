rootProject.name = "helixlang-ide"

// IPGP registers its own repositories (intellijRepository, cache redirector) on
// the project; PREFER_PROJECT lets those win over the settings-level ones.
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.PREFER_PROJECT)
    repositories {
        mavenCentral()
    }
}
