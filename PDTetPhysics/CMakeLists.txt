cmake_minimum_required(VERSION 3.17)

project(PDTetPhysics
    VERSION 0.1 LANGUAGES CXX)

get_filename_component(PARENT_DIR ${CMAKE_CURRENT_SOURCE_DIR} DIRECTORY)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")

# ---------------------------------------------------------------------------
# Source files -- PDDeformer (previously referenced as PDGridDeformer)
# ---------------------------------------------------------------------------
set(PDDEFORMER_SOURCES
    ${CMAKE_CURRENT_SOURCE_DIR}/PDDeformer/src/Add_Force.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/PDDeformer/src/GridDeformerTet.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/PDDeformer/src/PardisoWrapper.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/PDDeformer/src/ReshapeDataStructure.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/PDDeformer/src/SchurSolver.cpp
)

set(PDTET_SOURCES
    src/PDTetSolver.cpp
    src/MergedLevelSet.cpp
)

# Optionally include CudaSolver when CUDA is enabled
if(SKINFLAPS_ENABLE_CUDA)
    list(APPEND PDDEFORMER_SOURCES
        ${CMAKE_CURRENT_SOURCE_DIR}/PDDeformer/src/CudaSolver.cpp
    )
endif()

add_library(PDTetPhysics STATIC
    ${PDDEFORMER_SOURCES}
    ${PDTET_SOURCES}
)

# ---------------------------------------------------------------------------
# MKL -- use custom FindMKL shipped with this project
# ---------------------------------------------------------------------------
if(NOT DEFINED TARGET_INTERFACE)
    set(TARGET_INTERFACE "lp64")
endif()
if(NOT DEFINED TARGET_THREADING)
    set(TARGET_THREADING "intel_omp")
endif()

find_package(MKL MODULE REQUIRED)
find_package(OpenMP REQUIRED)

target_include_directories(PDTetPhysics PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/PDDeformer/include>
    $<BUILD_INTERFACE:${PARENT_DIR}/simd-numeric-kernels-new>
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<BUILD_INTERFACE:${MKL_INCLUDE}>
    $<INSTALL_INTERFACE:include>
)

target_compile_options(PDTetPhysics PUBLIC ${MKL_COPT})
target_link_libraries(PDTetPhysics PUBLIC ${MKL_LINK_PREFIX})

message(STATUS "MKL_LINK_PREFIX: ${MKL_LINK_PREFIX}")

# ---------------------------------------------------------------------------
# CUDA (optional)
# ---------------------------------------------------------------------------
if(SKINFLAPS_ENABLE_CUDA)
    find_package(CUDAToolkit 11 REQUIRED)
    target_link_libraries(PDTetPhysics PUBLIC CUDA::cudart)
    target_link_libraries(PDTetPhysics PUBLIC CUDA::cusolver)
    target_link_libraries(PDTetPhysics PUBLIC CUDA::cusparse)
endif()

target_link_libraries(PDTetPhysics PUBLIC OpenMP::OpenMP_CXX)
target_link_libraries(PDTetPhysics PUBLIC Public_Library)

# ---------------------------------------------------------------------------
# Definitions
# ---------------------------------------------------------------------------
target_compile_definitions(PDTetPhysics PUBLIC ENABLE_AVX_INSTRUCTION_SET)
target_compile_definitions(PDTetPhysics PUBLIC
    COMPILE_ID_TYPES_AS_INT
    COMPILE_WITHOUT_DYADIC_SUPPORT
    COMPILE_WITHOUT_RLE_SUPPORT
    COMPILE_WITHOUT_ZLIB_SUPPORT
)

# ---------------------------------------------------------------------------
# Windows DLL install helpers (only relevant on Win32)
# ---------------------------------------------------------------------------
if(WIN32)
    file(GLOB MKL_DLL ${MKL_DLL_DIR}/mkl_avx*.dll)
    foreach(_link_term_ ${MKL_LINK_PREFIX})
        string(FIND ${_link_term_} _dll.lib _dll_lib_loc_)
        if(${_dll_lib_loc_} GREATER -1)
            string(SUBSTRING ${_link_term_} 0 ${_dll_lib_loc_} _dll_lib_name_)
            get_filename_component(_dll_lib_name_ ${_dll_lib_name_} NAME)
            file(GLOB _dll_ ${MKL_DLL_DIR}/${_dll_lib_name_}*.dll)
            list(APPEND MKL_DLL ${_dll_})
        endif()
    endforeach()
    list(APPEND MKL_DLL ${IOMP_DLL_DIR}/${OMP_DLLNAME})
    foreach(_dll_ ${MKL_DLL})
        install(FILES ${_dll_} TYPE BIN)
    endforeach()
    unset(MKL_DLL)
endif()

install(TARGETS PDTetPhysics DESTINATION lib)
