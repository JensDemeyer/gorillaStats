import java.util.Properties

plugins {
    id("com.android.application")
}

val appSettings = Properties().apply {
    val file = rootProject.file("gorillastats.properties")
    if (file.exists()) file.inputStream().use { load(it) }
}
val appUrl = appSettings.getProperty("url")
    ?: error("Maak android/gorillastats.properties aan op basis van gorillastats.properties.example.")
val disconnectOnExit = appSettings.getProperty("disconnectOnExit", "true").toBoolean()

android {
    namespace = "com.gorillastats.app"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.gorillastats.app"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "1.0"
        buildConfigField("String", "APP_URL", "\"$appUrl\"")
        buildConfigField("boolean", "DISCONNECT_ON_EXIT", disconnectOnExit.toString())
    }

    buildFeatures {
        buildConfig = true
    }

    buildTypes {
        release {
            // Signed with the local debug key so the APK can be sideloaded and later updated in place.
            signingConfig = signingConfigs.getByName("debug")
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.16.0")
    implementation("androidx.activity:activity-ktx:1.10.1")
}
