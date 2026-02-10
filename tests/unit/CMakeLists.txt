cmake_minimum_required(VERSION 3.17)

# Fetch GoogleTest
include(FetchContent)
FetchContent_Declare(
    googletest
    GIT_REPOSITORY https://github.com/google/googletest.git
    GIT_TAG v1.14.0
)
FetchContent_MakeAvailable(googletest)

enable_testing()

# Include directories for project headers
set(SKINFLAPS_SRC_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../../SkinFlaps/src)
set(GL3W_GRAPHICS_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../../gl3wGraphics)

# --- test_vnBccTetrahedra ---
add_executable(test_vnBccTetrahedra test_vnBccTetrahedra.cpp)
target_include_directories(test_vnBccTetrahedra PRIVATE
    ${SKINFLAPS_SRC_DIR}
    ${GL3W_GRAPHICS_DIR}
)
target_link_libraries(test_vnBccTetrahedra PRIVATE GTest::gtest_main)
add_test(NAME VnBccTetrahedraTests COMMAND test_vnBccTetrahedra)

# --- test_tetCollisions ---
add_executable(test_tetCollisions test_tetCollisions.cpp)
target_include_directories(test_tetCollisions PRIVATE
    ${SKINFLAPS_SRC_DIR}
    ${GL3W_GRAPHICS_DIR}
)
target_link_libraries(test_tetCollisions PRIVATE GTest::gtest_main)
add_test(NAME TetCollisionsTests COMMAND test_tetCollisions)

# --- test_bccTetScene ---
add_executable(test_bccTetScene test_bccTetScene.cpp)
target_include_directories(test_bccTetScene PRIVATE
    ${SKINFLAPS_SRC_DIR}
    ${GL3W_GRAPHICS_DIR}
)
target_link_libraries(test_bccTetScene PRIVATE GTest::gtest_main)
add_test(NAME BccTetSceneTests COMMAND test_bccTetScene)
