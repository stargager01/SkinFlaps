##############################################################################
# SkinFlaps Unity Native Plugin - Using Pre-built Libraries
#
# This CMakeLists.txt creates a Unity plugin DLL by linking against
# the pre-built static libraries from the Visual Studio build.
#
# Prerequisites:
#   - Build the original SkinFlaps solution first (Build/msvc_2022/SkinFlaps.sln)
#   - Intel oneAPI Base Toolkit (MKL + TBB)
#
# Build Instructions:
#   mkdir build && cd build
#   cmake -G "Visual Studio 17 2022" -A x64 ../UnityPlugin
#   cmake --build . --config Release
##############################################################################

cmake_minimum_required(VERSION 3.17)

project(SkinFlapsUnityPlugin
    VERSION 1.0.0
    DESCRIPTION "SkinFlaps Unity Native Plugin"
    LANGUAGES CXX
)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Root directory
get_filename_component(SKINFLAPS_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/.. ABSOLUTE)

# Pre-built library directory (from Visual Studio build)
set(PREBUILT_LIB_DIR "${SKINFLAPS_ROOT}/Build/msvc_2022/x64/Debug")

# Check if pre-built libraries exist
if(NOT EXISTS "${PREBUILT_LIB_DIR}/PDTetPhysics_noCuda.lib")
    message(FATAL_ERROR
        "Pre-built libraries not found at ${PREBUILT_LIB_DIR}\n"
        "Please build the original SkinFlaps.sln first using Visual Studio.")
endif()

message(STATUS "Using pre-built libraries from: ${PREBUILT_LIB_DIR}")

##############################################################################
# Find Intel oneAPI Dependencies
##############################################################################

if(NOT DEFINED ONEAPI_ROOT)
    if(DEFINED ENV{ONEAPI_ROOT})
        set(ONEAPI_ROOT "$ENV{ONEAPI_ROOT}")
    elseif(WIN32)
        set(ONEAPI_ROOT "C:/Program Files (x86)/Intel/oneAPI")
    else()
        set(ONEAPI_ROOT "/opt/intel/oneapi")
    endif()
endif()

# Intel MKL
set(MKL_ROOT "${ONEAPI_ROOT}/mkl/latest")
set(MKL_INCLUDE "${MKL_ROOT}/include")
set(MKL_LIB_DIR "${MKL_ROOT}/lib")

if(WIN32)
    set(MKL_LIBS
        "${MKL_LIB_DIR}/mkl_intel_lp64_dll.lib"
        "${MKL_LIB_DIR}/mkl_intel_thread_dll.lib"
        "${MKL_LIB_DIR}/mkl_core_dll.lib"
    )
    if(EXISTS "${MKL_ROOT}/bin")
        set(MKL_DLL_DIR "${MKL_ROOT}/bin")
    endif()
endif()

# Intel OpenMP
set(COMPILER_ROOT "${ONEAPI_ROOT}/compiler/latest")
if(WIN32)
    set(IOMP_LIB "${COMPILER_ROOT}/lib/libiomp5md.lib")
    set(IOMP_DLL_DIR "${COMPILER_ROOT}/bin")
endif()

# Intel TBB
set(TBB_ROOT "${ONEAPI_ROOT}/tbb/latest")
set(TBB_INCLUDE "${TBB_ROOT}/include")
if(WIN32)
    if(EXISTS "${TBB_ROOT}/lib/tbb12.lib")
        set(TBB_LIB "${TBB_ROOT}/lib/tbb12.lib")
    endif()
    set(TBB_DLL_DIR "${TBB_ROOT}/bin")
endif()

# OpenMP
find_package(OpenMP REQUIRED)

##############################################################################
# Pre-built Libraries
##############################################################################

set(PREBUILT_LIBS
    "${PREBUILT_LIB_DIR}/SkinFlaps.lib"
    "${PREBUILT_LIB_DIR}/PDTetPhysics_noCuda.lib"
    "${PREBUILT_LIB_DIR}/PhysBAM_subset.lib"
    "${PREBUILT_LIB_DIR}/gl3wGraphics.lib"
    "${PREBUILT_LIB_DIR}/imgui_glfw_nfd_lib.lib"
)

##############################################################################
# Unity Export Wrapper
##############################################################################

add_library(SkinFlapsCore SHARED
    ${CMAKE_CURRENT_SOURCE_DIR}/src/UnityExports.cpp
)

# Compile definitions
target_compile_definitions(SkinFlapsCore PRIVATE
    SKINFLAPS_DLL_EXPORT
    NOMINMAX
    _ENABLE_EXTENDED_ALIGNED_STORAGE
    WIN32_LEAN_AND_MEAN
    NO_CUDA
)

# Include directories
target_include_directories(SkinFlapsCore PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${SKINFLAPS_ROOT}/SkinFlaps/src
    ${SKINFLAPS_ROOT}/gl3wGraphics
    ${SKINFLAPS_ROOT}/PDTetPhysics/include
    ${SKINFLAPS_ROOT}/PDTetPhysics/PDDeformer/include
    ${SKINFLAPS_ROOT}/PhysBAM_subset/Public_Library
    ${SKINFLAPS_ROOT}/simd-numeric-kernels-new
    ${SKINFLAPS_ROOT}/imgui_glfw_nfd_lib
    ${MKL_INCLUDE}
    ${TBB_INCLUDE}
)

# Compiler options
if(MSVC)
    target_compile_options(SkinFlapsCore PRIVATE
        /W3
        /arch:AVX2
        /fp:fast
        /MP
    )
endif()

# Link libraries
target_link_libraries(SkinFlapsCore PRIVATE
    ${PREBUILT_LIBS}
    ${MKL_LIBS}
    ${IOMP_LIB}
    ${TBB_LIB}
    OpenMP::OpenMP_CXX
)

# Additional Windows libraries
if(WIN32)
    target_link_libraries(SkinFlapsCore PRIVATE
        opengl32
        gdi32
        user32
        shell32
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
# Copy Runtime DLLs
##############################################################################

if(WIN32)
    # MKL DLLs
    if(EXISTS "${MKL_DLL_DIR}")
        file(GLOB MKL_DLLS "${MKL_DLL_DIR}/mkl_*.dll")
        foreach(DLL ${MKL_DLLS})
            add_custom_command(TARGET SkinFlapsCore POST_BUILD
                COMMAND ${CMAKE_COMMAND} -E copy_if_different "${DLL}" "$<TARGET_FILE_DIR:SkinFlapsCore>")
        endforeach()
    endif()

    # OpenMP DLL
    if(EXISTS "${IOMP_DLL_DIR}/libiomp5md.dll")
        add_custom_command(TARGET SkinFlapsCore POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_if_different
                "${IOMP_DLL_DIR}/libiomp5md.dll" "$<TARGET_FILE_DIR:SkinFlapsCore>")
    endif()

    # TBB DLLs
    if(EXISTS "${TBB_DLL_DIR}")
        file(GLOB TBB_DLLS "${TBB_DLL_DIR}/tbb*.dll")
        foreach(DLL ${TBB_DLLS})
            add_custom_command(TARGET SkinFlapsCore POST_BUILD
                COMMAND ${CMAKE_COMMAND} -E copy_if_different "${DLL}" "$<TARGET_FILE_DIR:SkinFlapsCore>")
        endforeach()
    endif()
endif()

##############################################################################
# Summary
##############################################################################

message(STATUS "")
message(STATUS "SkinFlaps Unity Plugin Configuration:")
message(STATUS "  Pre-built libs: ${PREBUILT_LIB_DIR}")
message(STATUS "  MKL:            ${MKL_ROOT}")
message(STATUS "  TBB:            ${TBB_ROOT}")
message(STATUS "")
