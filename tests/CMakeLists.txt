cmake_minimum_required(VERSION 3.17)

project(SkinFlapsTests LANGUAGES CXX)

enable_testing()

# ---------------------------------------------------------------------------
# Unit tests (C++ / GoogleTest)
# ---------------------------------------------------------------------------
add_subdirectory(unit)

# ---------------------------------------------------------------------------
# History file regression tests (headless, no OpenGL required)
# ---------------------------------------------------------------------------
# These tests validate the .hst history files used by the surgical replay
# system.  They require only Python 3 and run without a GPU or display.

# Phase 1 - JSON parse validation (quick)
add_test(
    NAME HistoryFiles_JSONValidation
    COMMAND ${CMAKE_COMMAND} -E env
        python3 ${CMAKE_CURRENT_SOURCE_DIR}/validate_history.py
                ${CMAKE_CURRENT_SOURCE_DIR}/../History
)

# Phase 2 - Full regression suite (bash wrapper for both phases)
add_test(
    NAME HistoryFiles_RegressionSuite
    COMMAND bash ${CMAKE_CURRENT_SOURCE_DIR}/run_regression_tests.sh
)

# Set a generous timeout for regression tests (they are I/O-bound, not
# compute-bound, but CI runners can be slow).
set_tests_properties(
    HistoryFiles_JSONValidation
    HistoryFiles_RegressionSuite
    PROPERTIES TIMEOUT 120
)
