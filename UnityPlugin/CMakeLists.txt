##############################################################################
# SkinFlaps Unity Native Plugin - Stub Build
#
# This builds a stub DLL that provides the Unity plugin interface.
# The stub can be used to verify Unity integration before full physics
# implementation.
#
# Build Instructions:
#   mkdir build && cd build
#   cmake -G "Visual Studio 17 2022" -A x64 ../UnityPlugin
#   cmake --build . --config Release
##############################################################################

cmake_minimum_required(VERSION 3.17)

project(SkinFlapsUnityPlugin
    VERSION 1.0.0
    DESCRIPTION "SkinFlaps Unity Native Plugin (Stub)"
    LANGUAGES CXX
)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

##############################################################################
# Unity Export Wrapper (Stub)
##############################################################################

add_library(SkinFlapsCore SHARED
    ${CMAKE_CURRENT_SOURCE_DIR}/src/UnityExports.cpp
)

# Compile definitions
target_compile_definitions(SkinFlapsCore PRIVATE
    SKINFLAPS_DLL_EXPORT
    NOMINMAX
    WIN32_LEAN_AND_MEAN
)

# Include directories
target_include_directories(SkinFlapsCore PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

# Compiler options
if(MSVC)
    target_compile_options(SkinFlapsCore PRIVATE
        /W3
        /MP
    )
endif()

# Output settings
set_target_properties(SkinFlapsCore PROPERTIES
    OUTPUT_NAME "SkinFlapsCore"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib"
    ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib"
)

##############################################################################
# Summary
##############################################################################

message(STATUS "")
message(STATUS "SkinFlaps Unity Plugin (Stub) Configuration:")
message(STATUS "  Version:     ${PROJECT_VERSION}")
message(STATUS "  Output:      ${CMAKE_BINARY_DIR}/bin/SkinFlapsCore.dll")
message(STATUS "")
message(STATUS "This is a STUB build for Unity integration testing.")
message(STATUS "Full physics integration requires additional work to resolve")
message(STATUS "the complex header dependencies in the SkinFlaps codebase.")
message(STATUS "")
