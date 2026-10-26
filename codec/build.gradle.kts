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
