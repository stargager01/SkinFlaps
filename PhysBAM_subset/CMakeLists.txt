cmake_minimum_required(VERSION 3.8)

project(PhysBAM_subset
    VERSION 0.1 LANGUAGES CXX)

# ---------------------------------------------------------------------------
# Gather all .cpp files recursively from Public_Library
# ---------------------------------------------------------------------------
file(GLOB_RECURSE PHYSBAM_SOURCES
    "${CMAKE_CURRENT_SOURCE_DIR}/Public_Library/*.cpp"
)

# ---------------------------------------------------------------------------
# StackWalker is Windows-only; exclude on other platforms
# ---------------------------------------------------------------------------
if(NOT WIN32)
    list(FILTER PHYSBAM_SOURCES EXCLUDE REGEX "StackWalker")
endif()

# On Windows, include the StackWalker utility
if(WIN32)
    list(APPEND PHYSBAM_SOURCES
        "${CMAKE_CURRENT_SOURCE_DIR}/StackWalker/StackWalker.cpp"
    )
endif()

add_library(Public_Library STATIC ${PHYSBAM_SOURCES})

# ---------------------------------------------------------------------------
# Include directories
# ---------------------------------------------------------------------------
target_include_directories(Public_Library PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/Public_Library>
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/Common_Libraries>
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/Common_Libraries/Common_Tools>
    $<INSTALL_INTERFACE:include>
)

# ---------------------------------------------------------------------------
# Compile definitions (PhysBAM subset build flags from vcxproj)
# ---------------------------------------------------------------------------
target_compile_definitions(Public_Library PUBLIC
    COMPILE_ID_TYPES_AS_INT
    COMPILE_WITHOUT_DYADIC_SUPPORT
    COMPILE_WITHOUT_RLE_SUPPORT
    COMPILE_WITHOUT_ZLIB_SUPPORT
)

if(WIN32)
    target_compile_definitions(Public_Library PUBLIC NOMINMAX _CRT_SECURE_NO_WARNINGS)
endif()

install(TARGETS Public_Library DESTINATION lib)
