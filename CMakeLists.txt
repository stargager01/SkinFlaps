cmake_minimum_required(VERSION 3.17)
project(SkinFlaps VERSION 1.2.1 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ===========================================================================
# Platform checks
# ===========================================================================
if(APPLE)
    message(FATAL_ERROR "macOS is not supported (requires AVX and Intel MKL)")
endif()

# ===========================================================================
# Build options
# ===========================================================================
option(SKINFLAPS_ENABLE_CUDA "Enable CUDA GPU acceleration" OFF)
option(SKINFLAPS_BUILD_TESTS "Build test suite" OFF)

# ===========================================================================
# Compiler flags
# ===========================================================================
if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU" OR CMAKE_CXX_COMPILER_ID STREQUAL "Clang")
    add_compile_options(-mavx -mfma)
elseif(MSVC)
    add_compile_options(/arch:AVX2)
endif()

# ===========================================================================
# Find required system packages
# ===========================================================================
find_package(OpenGL REQUIRED)
find_package(OpenMP REQUIRED)

if(WIN32)
    # On Windows the bundled FindGLFW3 module is used by imgui_glfw_nfd_lib
else()
    find_package(glfw3 REQUIRED)
endif()

# ---------------------------------------------------------------------------
# Intel MKL -- support both oneAPI layout and standalone installations.
# The custom FindMKL.cmake shipped in PDTetPhysics/cmake/ handles the
# actual discovery; we just make sure the module path contains it.
# ---------------------------------------------------------------------------
list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/PDTetPhysics/cmake")

# ---------------------------------------------------------------------------
# Intel TBB -- try the system / oneAPI config-file package first, then
# fall back to the custom FindTBB module that ships with PDTetPhysics.
# ---------------------------------------------------------------------------
find_package(TBB QUIET CONFIG)
if(NOT TBB_FOUND)
    find_package(TBB MODULE QUIET)
endif()

# ===========================================================================
# Subdirectory libraries (order matters -- dependees before dependents)
# ===========================================================================

# 1. imgui + GLFW + gl3w  (no internal deps)
add_subdirectory(imgui_glfw_nfd_lib)

# 2. gl3wGraphics (depends on imgui_glfw_ndf)
add_subdirectory(gl3wGraphics)

# 3. PhysBAM subset (no internal deps)
add_subdirectory(PhysBAM_subset)

# 4. simd-numeric-kernels-new is header-only; expose as an INTERFACE target
#    so downstream targets can simply link against it.
if(NOT TARGET simd_numeric_kernels)
    add_library(simd_numeric_kernels INTERFACE)
    target_include_directories(simd_numeric_kernels INTERFACE
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/simd-numeric-kernels-new>
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/simd-numeric-kernels-new/Common>
    )
endif()

# 5. PDTetPhysics (depends on Public_Library, MKL, optionally CUDA)
add_subdirectory(PDTetPhysics)

# ===========================================================================
# Main SkinFlaps application
# ===========================================================================

# Gather all application source files
set(SKINFLAPS_APP_SOURCES
    SkinFlaps/src/main.cpp
    SkinFlaps/src/bccTetScene.cpp
    SkinFlaps/src/deepCut.cpp
    SkinFlaps/src/FacialFlapsGui.cpp
    SkinFlaps/src/fence.cpp
    SkinFlaps/src/hooks.cpp
    SkinFlaps/src/json.cpp
    SkinFlaps/src/remapTetPhysics.cpp
    SkinFlaps/src/skinCutUndermineTets.cpp
    SkinFlaps/src/surgicalActions.cpp
    SkinFlaps/src/sutures.cpp
    SkinFlaps/src/tetCollisions.cpp
    SkinFlaps/src/tetSubset.cpp
    SkinFlaps/src/vnBccTetCutter_tbb.cpp
    SkinFlaps/src/vnBccTetrahedra.cpp
)

add_executable(SkinFlapsApp ${SKINFLAPS_APP_SOURCES})

# ---------------------------------------------------------------------------
# Include directories for the application
# ---------------------------------------------------------------------------
target_include_directories(SkinFlapsApp PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/SkinFlaps/src
    ${CMAKE_CURRENT_SOURCE_DIR}/SkinFlaps/src/CDT/include
)

# ---------------------------------------------------------------------------
# Link all libraries
# ---------------------------------------------------------------------------
target_link_libraries(SkinFlapsApp PRIVATE
    PDTetPhysics
    Public_Library
    gl3wGraphics
    imgui_glfw_ndf
    simd_numeric_kernels
    OpenGL::GL
    OpenMP::OpenMP_CXX
)

# TBB -- link through imported target when available
if(TARGET TBB::tbb)
    target_link_libraries(SkinFlapsApp PRIVATE TBB::tbb)
elseif(TBB_LIBRARIES)
    target_link_libraries(SkinFlapsApp PRIVATE ${TBB_LIBRARIES})
else()
    # Fallback: link tbb by name and let the linker resolve it
    target_link_libraries(SkinFlapsApp PRIVATE tbb)
endif()

# CUDA libraries (when enabled, already linked transitively via PDTetPhysics)

# System libraries on Linux
if(UNIX AND NOT APPLE)
    target_link_libraries(SkinFlapsApp PRIVATE dl pthread m)
endif()

# ---------------------------------------------------------------------------
# Compile definitions for the application
# ---------------------------------------------------------------------------
target_compile_definitions(SkinFlapsApp PRIVATE
    IMGUI_IMPL_OPENGL_LOADER_GL3W
    ENABLE_AVX_INSTRUCTION_SET
)

if(WIN32)
    target_compile_definitions(SkinFlapsApp PRIVATE
        NOMINMAX
        _CRT_SECURE_NO_WARNINGS
        _ENABLE_EXTENDED_ALIGNED_STORAGE
    )
endif()

# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------
install(TARGETS SkinFlapsApp RUNTIME DESTINATION bin)

# Copy Model and History data directories next to the binary
install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/Model   DESTINATION bin)
install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/History  DESTINATION bin)

message(STATUS "")
message(STATUS "=== SkinFlaps build configuration ===")
message(STATUS "  Version       : ${PROJECT_VERSION}")
message(STATUS "  CUDA          : ${SKINFLAPS_ENABLE_CUDA}")
message(STATUS "  Build tests   : ${SKINFLAPS_BUILD_TESTS}")
message(STATUS "  C++ compiler  : ${CMAKE_CXX_COMPILER_ID} ${CMAKE_CXX_COMPILER_VERSION}")
message(STATUS "  Build type    : ${CMAKE_BUILD_TYPE}")
message(STATUS "=====================================")
message(STATUS "")
