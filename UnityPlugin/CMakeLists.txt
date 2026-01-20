##############################################################################
# SkinFlaps Unity Native Plugin CMake Build Configuration
#
# This CMakeLists.txt builds the SkinFlaps physics simulation as a Unity
# native plugin DLL. It compiles only the core physics and surgical operation
# components, excluding the GLFW-based GUI.
#
# Prerequisites:
#   - Intel oneAPI Base Toolkit (MKL + TBB)
#   - CMake 3.17+
#   - Visual Studio 2019/2022 (Windows) or GCC 9+ (Linux)
#   - CUDA Toolkit 11+ (optional, for GPU solver)
#
# Build Instructions:
#   mkdir build && cd build
#   cmake -DCMAKE_BUILD_TYPE=Release ..
#   cmake --build . --config Release
#
# The output DLL will be in: build/Release/SkinFlapsCore.dll (Windows)
#                            build/libSkinFlapsCore.so (Linux)
#                            build/libSkinFlapsCore.dylib (macOS)
##############################################################################

cmake_minimum_required(VERSION 3.17)

project(SkinFlapsUnityPlugin
    VERSION 1.0.0
    DESCRIPTION "SkinFlaps Unity Native Plugin"
    LANGUAGES CXX
)

# Build options
option(SKINFLAPS_USE_CUDA "Enable CUDA GPU solver" OFF)
option(SKINFLAPS_BUILD_TESTS "Build test executable" OFF)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Root directory
get_filename_component(SKINFLAPS_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/.. ABSOLUTE)

# Set module path for finding Intel libraries
list(APPEND CMAKE_MODULE_PATH "${SKINFLAPS_ROOT}/PDTetPhysics/cmake")

##############################################################################
# Find Dependencies
##############################################################################

# Intel oneAPI root
if(NOT DEFINED ONEAPI_ROOT)
    if(DEFINED ENV{ONEAPI_ROOT})
        set(ONEAPI_ROOT "$ENV{ONEAPI_ROOT}")
    elseif(WIN32)
        set(ONEAPI_ROOT "C:/Program Files (x86)/Intel/oneAPI")
    else()
        set(ONEAPI_ROOT "/opt/intel/oneapi")
    endif()
endif()
message(STATUS "ONEAPI_ROOT: ${ONEAPI_ROOT}")

# Intel MKL - Direct configuration (bypass FindMKL.cmake DLL search issues)
set(MKL_ROOT "${ONEAPI_ROOT}/mkl/latest")
set(MKL_INCLUDE "${MKL_ROOT}/include")

if(NOT EXISTS "${MKL_INCLUDE}/mkl.h")
    message(FATAL_ERROR "MKL not found at ${MKL_ROOT}. Please install Intel oneAPI Base Toolkit.")
endif()

message(STATUS "MKL_ROOT: ${MKL_ROOT}")
message(STATUS "MKL_INCLUDE: ${MKL_INCLUDE}")

# MKL library paths
if(WIN32)
    set(MKL_LIB_DIR "${MKL_ROOT}/lib")
    set(MKL_LINK_PREFIX
        "${MKL_LIB_DIR}/mkl_intel_lp64_dll.lib"
        "${MKL_LIB_DIR}/mkl_intel_thread_dll.lib"
        "${MKL_LIB_DIR}/mkl_core_dll.lib"
    )
    # Find MKL DLLs for deployment
    if(EXISTS "${MKL_ROOT}/bin")
        set(MKL_DLL_DIR "${MKL_ROOT}/bin")
    elseif(EXISTS "${MKL_ROOT}/redist/intel64")
        set(MKL_DLL_DIR "${MKL_ROOT}/redist/intel64")
    else()
        set(MKL_DLL_DIR "${MKL_ROOT}/../redist/intel64/mkl")
    endif()
    message(STATUS "MKL_DLL_DIR: ${MKL_DLL_DIR}")
else()
    set(MKL_LIB_DIR "${MKL_ROOT}/lib/intel64")
    set(MKL_LINK_PREFIX
        "-Wl,--start-group"
        "${MKL_LIB_DIR}/libmkl_intel_lp64.a"
        "${MKL_LIB_DIR}/libmkl_intel_thread.a"
        "${MKL_LIB_DIR}/libmkl_core.a"
        "-Wl,--end-group"
    )
endif()

# Intel OpenMP (IOMP)
set(COMPILER_ROOT "${ONEAPI_ROOT}/compiler/latest")
if(WIN32)
    set(IOMP_LIB "${COMPILER_ROOT}/lib/libiomp5md.lib")
    set(IOMP_DLL_DIR "${COMPILER_ROOT}/bin")
    set(OMP_DLLNAME "libiomp5md.dll")
else()
    set(IOMP_LIB "${COMPILER_ROOT}/lib/libiomp5.so")
endif()

if(EXISTS "${IOMP_LIB}")
    list(APPEND MKL_LINK_PREFIX "${IOMP_LIB}")
    message(STATUS "IOMP found: ${IOMP_LIB}")
else()
    message(WARNING "IOMP not found at ${IOMP_LIB}, using system OpenMP")
endif()

set(MKL_COPT "")

# Intel TBB
set(TBB_ROOT "${ONEAPI_ROOT}/tbb/latest")
if(EXISTS "${TBB_ROOT}/lib/cmake/tbb/TBBConfig.cmake")
    set(TBB_DIR "${TBB_ROOT}/lib/cmake/tbb")
endif()
find_package(TBB QUIET)
if(NOT TBB_FOUND)
    message(STATUS "TBB not found via CMake, using direct paths")
    set(TBB_INCLUDE "${TBB_ROOT}/include")
    if(WIN32)
        set(TBB_LIB "${TBB_ROOT}/lib/tbb12.lib")
        set(TBB_DLL_DIR "${TBB_ROOT}/bin")
    else()
        set(TBB_LIB "${TBB_ROOT}/lib/intel64/gcc4.8/libtbb.so.12")
    endif()
endif()

# OpenMP
find_package(OpenMP REQUIRED)

# CUDA (optional)
if(SKINFLAPS_USE_CUDA)
    find_package(CUDAToolkit 11)
    if(CUDAToolkit_FOUND)
        message(STATUS "CUDA found: ${CUDAToolkit_VERSION}")
    else()
        message(WARNING "CUDA not found, disabling GPU solver")
        set(SKINFLAPS_USE_CUDA OFF)
    endif()
endif()

##############################################################################
# Source Files
##############################################################################

# PhysBAM subset (core geometry utilities)
set(PHYSBAM_SOURCES
    ${SKINFLAPS_ROOT}/PhysBAM_subset/Public_Library/Arrays/ARRAY_BASE.cpp
    ${SKINFLAPS_ROOT}/PhysBAM_subset/Public_Library/Geometry/BASIC_GEOMETRY.cpp
    ${SKINFLAPS_ROOT}/PhysBAM_subset/Public_Library/Geometry/PLANE.cpp
    ${SKINFLAPS_ROOT}/PhysBAM_subset/Public_Library/Geometry/SEGMENT_3D.cpp
    ${SKINFLAPS_ROOT}/PhysBAM_subset/Public_Library/Geometry/TETRAHEDRON.cpp
    ${SKINFLAPS_ROOT}/PhysBAM_subset/Public_Library/Geometry/TRIANGLE_3D.cpp
    ${SKINFLAPS_ROOT}/PhysBAM_subset/Public_Library/Matrices_And_Vectors/MATRIX_3X3.cpp
    ${SKINFLAPS_ROOT}/PhysBAM_subset/Public_Library/Matrices_And_Vectors/VECTOR_3D.cpp
    ${SKINFLAPS_ROOT}/PhysBAM_subset/Public_Library/Utilities/LOG.cpp
)

# PD Tet Physics (projective dynamics solver)
set(PDTETPHYSICS_SOURCES
    ${SKINFLAPS_ROOT}/PDTetPhysics/PDDeformer/src/GridDeformerTet.cpp
    ${SKINFLAPS_ROOT}/PDTetPhysics/PDDeformer/src/PardisoWrapper.cpp
    ${SKINFLAPS_ROOT}/PDTetPhysics/PDDeformer/src/ReshapeDataStructure.cpp
    ${SKINFLAPS_ROOT}/PDTetPhysics/PDDeformer/src/SchurSolver.cpp
    ${SKINFLAPS_ROOT}/PDTetPhysics/PDDeformer/src/Add_Force.cpp
    ${SKINFLAPS_ROOT}/PDTetPhysics/src/PDTetSolver.cpp
    ${SKINFLAPS_ROOT}/PDTetPhysics/src/MergedLevelSet.cpp
)

if(SKINFLAPS_USE_CUDA)
    list(APPEND PDTETPHYSICS_SOURCES
        ${SKINFLAPS_ROOT}/PDTetPhysics/PDDeformer/src/CudaSolver.cpp
    )
endif()

# Graphics (only mesh handling, no OpenGL rendering)
set(GRAPHICS_SOURCES
    ${SKINFLAPS_ROOT}/gl3wGraphics/materialTriangles.cpp
    ${SKINFLAPS_ROOT}/gl3wGraphics/surgGraphics.cpp
    ${SKINFLAPS_ROOT}/gl3wGraphics/shapes.cpp
    ${SKINFLAPS_ROOT}/gl3wGraphics/sceneNode.cpp
)

# Core SkinFlaps simulation
set(SKINFLAPS_SOURCES
    ${SKINFLAPS_ROOT}/SkinFlaps/src/bccTetScene.cpp
    ${SKINFLAPS_ROOT}/SkinFlaps/src/vnBccTetrahedra.cpp
    ${SKINFLAPS_ROOT}/SkinFlaps/src/vnBccTetCutter_tbb.cpp
    ${SKINFLAPS_ROOT}/SkinFlaps/src/tetCollisions.cpp
    ${SKINFLAPS_ROOT}/SkinFlaps/src/tetSubset.cpp
    ${SKINFLAPS_ROOT}/SkinFlaps/src/remapTetPhysics.cpp
    ${SKINFLAPS_ROOT}/SkinFlaps/src/skinCutUndermineTets.cpp
    ${SKINFLAPS_ROOT}/SkinFlaps/src/deepCut.cpp
    ${SKINFLAPS_ROOT}/SkinFlaps/src/sutures.cpp
    ${SKINFLAPS_ROOT}/SkinFlaps/src/hooks.cpp
    ${SKINFLAPS_ROOT}/SkinFlaps/src/fence.cpp
    ${SKINFLAPS_ROOT}/SkinFlaps/src/surgicalActions.cpp
    ${SKINFLAPS_ROOT}/SkinFlaps/src/boundingBox.cpp
)

# Unity Plugin interface
set(UNITYPLUGIN_SOURCES
    ${CMAKE_CURRENT_SOURCE_DIR}/src/UnityExports.cpp
)

##############################################################################
# Build Library
##############################################################################

add_library(SkinFlapsCore SHARED
    ${PHYSBAM_SOURCES}
    ${PDTETPHYSICS_SOURCES}
    ${GRAPHICS_SOURCES}
    ${SKINFLAPS_SOURCES}
    ${UNITYPLUGIN_SOURCES}
)

# Compile definitions
target_compile_definitions(SkinFlapsCore PRIVATE
    SKINFLAPS_DLL_EXPORT
    ENABLE_AVX_INSTRUCTION_SET
    _USE_MATH_DEFINES
)

if(WIN32)
    target_compile_definitions(SkinFlapsCore PRIVATE
        NOMINMAX
        _ENABLE_EXTENDED_ALIGNED_STORAGE
        WIN32_LEAN_AND_MEAN
    )
endif()

if(NOT SKINFLAPS_USE_CUDA)
    target_compile_definitions(SkinFlapsCore PRIVATE NO_CUDA)
endif()

# Include directories
target_include_directories(SkinFlapsCore PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${SKINFLAPS_ROOT}/SkinFlaps/src
    ${SKINFLAPS_ROOT}/gl3wGraphics
    ${SKINFLAPS_ROOT}/PDTetPhysics/include
    ${SKINFLAPS_ROOT}/PDTetPhysics/PDDeformer/include
    ${SKINFLAPS_ROOT}/PhysBAM_subset/Public_Library
    ${SKINFLAPS_ROOT}/simd-numeric-kernels-new
    ${MKL_INCLUDE}
)

# Compiler options
target_compile_options(SkinFlapsCore PRIVATE ${MKL_COPT})

if(MSVC)
    target_compile_options(SkinFlapsCore PRIVATE
        /W3
        /arch:AVX2
        /fp:fast
        /MP
    )
else()
    target_compile_options(SkinFlapsCore PRIVATE
        -Wall
        -mavx2
        -mfma
        -ffast-math
        -O3
    )
endif()

# Link libraries
target_link_libraries(SkinFlapsCore PRIVATE
    ${MKL_LINK_PREFIX}
    OpenMP::OpenMP_CXX
)

# TBB linking
if(TBB_FOUND)
    target_link_libraries(SkinFlapsCore PRIVATE TBB::tbb)
else()
    target_include_directories(SkinFlapsCore PRIVATE ${TBB_INCLUDE})
    target_link_libraries(SkinFlapsCore PRIVATE ${TBB_LIB})
endif()

if(SKINFLAPS_USE_CUDA)
    target_link_libraries(SkinFlapsCore PRIVATE
        CUDA::cudart
        CUDA::cusolver
        CUDA::cusparse
    )
endif()

# Output name and properties
set_target_properties(SkinFlapsCore PROPERTIES
    OUTPUT_NAME "SkinFlapsCore"
    VERSION ${PROJECT_VERSION}
    SOVERSION 1
)

# Platform-specific output settings
if(WIN32)
    set_target_properties(SkinFlapsCore PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
        LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib"
        ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib"
    )
elseif(APPLE)
    set_target_properties(SkinFlapsCore PROPERTIES
        SUFFIX ".bundle"
        INSTALL_RPATH "@loader_path"
    )
else()
    set_target_properties(SkinFlapsCore PROPERTIES
        INSTALL_RPATH "$ORIGIN"
    )
endif()

##############################################################################
# Install Rules
##############################################################################

install(TARGETS SkinFlapsCore
    RUNTIME DESTINATION bin
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
)

install(FILES
    ${CMAKE_CURRENT_SOURCE_DIR}/include/UnityExports.h
    DESTINATION include
)

# Copy runtime DLLs (Windows) - post-build step
if(WIN32)
    # Create a script to copy DLLs after build
    add_custom_command(TARGET SkinFlapsCore POST_BUILD
        COMMENT "Copying runtime DLLs..."
    )

    # MKL DLLs
    if(EXISTS "${MKL_DLL_DIR}")
        file(GLOB MKL_DLLS "${MKL_DLL_DIR}/mkl_*.dll")
        foreach(DLL_FILE ${MKL_DLLS})
            add_custom_command(TARGET SkinFlapsCore POST_BUILD
                COMMAND ${CMAKE_COMMAND} -E copy_if_different
                    "${DLL_FILE}"
                    "$<TARGET_FILE_DIR:SkinFlapsCore>"
            )
        endforeach()
    endif()

    # OpenMP DLL
    if(EXISTS "${IOMP_DLL_DIR}/${OMP_DLLNAME}")
        add_custom_command(TARGET SkinFlapsCore POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_if_different
                "${IOMP_DLL_DIR}/${OMP_DLLNAME}"
                "$<TARGET_FILE_DIR:SkinFlapsCore>"
        )
    endif()

    # TBB DLLs
    if(DEFINED TBB_DLL_DIR AND EXISTS "${TBB_DLL_DIR}")
        file(GLOB TBB_DLLS "${TBB_DLL_DIR}/tbb*.dll")
        foreach(DLL_FILE ${TBB_DLLS})
            add_custom_command(TARGET SkinFlapsCore POST_BUILD
                COMMAND ${CMAKE_COMMAND} -E copy_if_different
                    "${DLL_FILE}"
                    "$<TARGET_FILE_DIR:SkinFlapsCore>"
            )
        endforeach()
    endif()

    message(STATUS "")
    message(STATUS "Runtime DLLs will be copied to output directory after build")
endif()

##############################################################################
# Test Executable (optional)
##############################################################################

if(SKINFLAPS_BUILD_TESTS)
    add_executable(SkinFlapsTest
        ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_main.cpp
    )

    target_link_libraries(SkinFlapsTest PRIVATE SkinFlapsCore)

    target_include_directories(SkinFlapsTest PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include
    )
endif()

##############################################################################
# Print Configuration Summary
##############################################################################

message(STATUS "")
message(STATUS "SkinFlaps Unity Plugin Configuration:")
message(STATUS "  Version:        ${PROJECT_VERSION}")
message(STATUS "  Build Type:     ${CMAKE_BUILD_TYPE}")
message(STATUS "  C++ Standard:   ${CMAKE_CXX_STANDARD}")
message(STATUS "  CUDA Support:   ${SKINFLAPS_USE_CUDA}")
message(STATUS "  MKL Include:    ${MKL_INCLUDE}")
message(STATUS "  TBB Found:      ${TBB_FOUND}")
message(STATUS "")
