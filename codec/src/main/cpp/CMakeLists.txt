cmake_minimum_required(VERSION 3.22.1)
project(android_player_codec LANGUAGES C)

set(FFMPEG_INCLUDE "${CMAKE_CURRENT_LIST_DIR}/../ffmpeg-include")
set(FFMPEG_LIBS "${CMAKE_CURRENT_LIST_DIR}/../jniLibs/${ANDROID_ABI}")
foreach(lib avutil swresample swscale avcodec avformat)
    if(NOT EXISTS "${FFMPEG_LIBS}/lib${lib}.so")
        message(FATAL_ERROR "Missing LGPL FFmpeg lib${lib}.so for ${ANDROID_ABI}. Run scripts/build_ffmpeg.sh first.")
    endif()
    add_library(${lib} SHARED IMPORTED)
    set_target_properties(${lib} PROPERTIES IMPORTED_LOCATION "${FFMPEG_LIBS}/lib${lib}.so")
endforeach()
if(NOT EXISTS "${FFMPEG_INCLUDE}/libavcodec/avcodec.h")
    message(FATAL_ERROR "FFmpeg header directory missing. Run scripts/build_ffmpeg.sh first.")
endif()

add_library(android_player_codec SHARED codec_jni.c)
target_include_directories(android_player_codec PRIVATE "${FFMPEG_INCLUDE}")
target_compile_options(android_player_codec PRIVATE -Wall -Wextra -Werror=return-type)
target_link_options(android_player_codec PRIVATE
    "-Wl,-z,max-page-size=16384"
    "-Wl,-z,common-page-size=16384")
target_link_libraries(android_player_codec PRIVATE
    avformat avcodec swscale swresample avutil log)
