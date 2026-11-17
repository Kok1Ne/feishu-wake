import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}
android {
    namespace = "dev.feishuwake"
    compileSdk = 35
    buildToolsVersion = "35.0.0"
    defaultConfig {
        applicationId = "dev.feishuwake"
        minSdk = 27
        targetSdk = 35
        versionCode = 1
        versionName = "1.0.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }
    buildFeatures { buildConfig = true }
    buildTypes {
        debug { applicationIdSuffix = ".debug" }
        release { isMinifyEnabled = false }
    }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
    lint { abortOnError = true; checkReleaseBuilds = true; warningsAsErrors = false }
}
dependencies {
    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.test:runner:1.6.2")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test.uiautomator:uiautomator:2.3.0")
}
// Release is intentionally unavailable before independently collected evidence exists.
val checkReleaseGate by tasks.registering(Exec::class) {
    workingDir(rootDir)
    commandLine(System.getenv("FEISHU_PYTHON") ?: "python", "tools/release_gate.py", "--check")
}
tasks.configureEach {
    if (name.contains("Release") && name != "checkReleaseGate") dependsOn(checkReleaseGate)
}
val signingFile = rootProject.file("signing.properties")
if (signingFile.exists()) {
    val props = Properties().apply { signingFile.inputStream().use { load(it) } }
    android.signingConfigs.create("stable") {
        storeFile = rootProject.file(props.getProperty("storeFile"))
        storePassword = props.getProperty("storePassword")
        keyAlias = props.getProperty("keyAlias")
        keyPassword = props.getProperty("keyPassword")
    }
    android.buildTypes.getByName("release").signingConfig = android.signingConfigs.getByName("stable")
}
