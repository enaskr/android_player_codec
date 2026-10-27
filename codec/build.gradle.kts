plugins { id("com.android.library") }

android {
    namespace = "com.enaskr.player.codec"
    compileSdk = 35
    ndkVersion = "28.2.13676358"

    defaultConfig {
        minSdk = 23
        // Local/debug ARM64 builds can run before the other three ABIs are compiled.
        if (providers.gradleProperty("codecOnlyArm64").orNull == "true") {
            ndk { abiFilters += "arm64-v8a" }
        }
        consumerProguardFiles("consumer-rules.pro")
        externalNativeBuild {
            cmake {
                cFlags += "-std=c11"
                arguments += listOf("-DANDROID_STL=none")
            }
        }
    }

    buildTypes {
        getByName("release") { isMinifyEnabled = false }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    externalNativeBuild {
        cmake { path = file("src/main/cpp/CMakeLists.txt"); version = "3.22.1" }
    }
    packaging {
        jniLibs {
            useLegacyPackaging = false
        }
    }
}

 
// Use the official VideoLAN AAR for compile-time API signatures only.
// The final distribution is assembled from the unchanged original LibVLC AAR
// plus this module's own Java/JNI output; no nested AAR dependency is packaged.
dependencies {
    compileOnly("org.videolan.android:libvlc-all:${providers.gradleProperty("libvlcVersion").orElse("3.7.7").get()}")
}
