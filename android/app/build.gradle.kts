import com.chaquo.python.PythonExtension
import org.gradle.api.plugins.ExtensionAware
import org.gradle.kotlin.dsl.configure

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

android {
    namespace = "com.claudecat.urayaha.alarm"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.claudecat.urayaha.alarm"
        minSdk = 24
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"

        ndk {
            // Python ランタイムを ABI ごとに同梱するため、3つ入れると APK が 40MB を超える。
            // -Pabi=arm64-v8a のように渡すと絞れる(配布用)。
            val requested = (project.findProperty("abi") as String?)
                ?.split(",")?.map { it.trim() }?.filter { it.isNotEmpty() }
            abiFilters += requested ?: listOf("arm64-v8a", "armeabi-v7a", "x86_64")
        }

        (this as ExtensionAware).extensions.configure<PythonExtension>("python") {
            version = "3.10"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        viewBinding = true
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.activity:activity-ktx:1.9.3")
}

// urayaha/ 本体(../../urayaha)を Python ソースとして同梱する。手でコピーして
// 二重管理にしないよう、Sync タスクで preBuild の前に毎回同期する。
val syncUrayahaSource = tasks.register<Sync>("syncUrayahaSource") {
    from(rootProject.projectDir.parentFile.resolve("urayaha")) {
        include("**/*.py")
    }
    into(layout.projectDirectory.dir("src/main/python/urayaha"))
}

tasks.named("preBuild") {
    dependsOn(syncUrayahaSource)
}

// Chaquopy の Python ソース集約タスクは syncUrayahaSource の出力(app/src/main/python/urayaha)
// を読むが、preBuild 経由の暗黙順序だけでは Gradle のタスク検証に引っかかるので明示する。
tasks.matching { it.name.matches(Regex("merge[A-Za-z0-9]*PythonSources")) }.configureEach {
    dependsOn(syncUrayahaSource)
}
