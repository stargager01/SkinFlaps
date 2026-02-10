# SkinFlaps Test Infrastructure

## Overview

This directory contains the test infrastructure for the SkinFlaps surgical
simulation project. Tests are organized into two categories:

1. **History file regression tests** -- headless validation of `.hst` files
   (no GPU or OpenGL context required)
2. **C++ unit tests** -- GoogleTest-based tests for core data structures
   (in the `unit/` subdirectory)

## History File Regression Tests

### Background

The SkinFlaps simulator records surgical procedures as `.hst` history files
in the `History/` directory. These are JSON arrays where each element is an
action object with a single key identifying the action type. During replay,
`surgicalActions::nextHistoryAction()` iterates through these actions to
reproduce the surgery step by step.

There are currently 13 history files covering procedures such as cleft lip
repairs, eyelid reconstruction, scalp rotation flaps, and ear reconstruction.

### Action Types

The following action types are recognized by the replay system (defined in
`SkinFlaps/src/surgicalActions.cpp`):

| Action Type                     | Value Format                                    |
|---------------------------------|-------------------------------------------------|
| `loadSceneFile`                 | String (`.smd` filename)                        |
| `addHook`                       | Object: material, hookNum, historyTexture, displacement |
| `moveHook`                      | Array: [hookNum, x, y, z]                       |
| `deleteHook`                    | Integer (hookNum)                               |
| `makeIncision`                  | Array: header + incisionPoint objects            |
| `undermine`                     | Array of underminePoint objects                  |
| `excise`                        | Object: material, historyTexture, displacement   |
| `addSuture`                     | Object: sutureNum, linked, material0/1, historyTexture0/1, displacement0/1 |
| `deleteSuture`                  | Integer or object with autoSuturesFor            |
| `makeDeepCut`                   | Array: header + deepCutPoint objects             |
| `periostealUndermine`           | Array of periostealTriangle objects              |
| `promoteSutureApproximations`   | Integer (value ignored)                          |
| `pausePhysics`                  | Integer (value ignored)                          |

### Running Headless Tests

The regression tests require only Python 3 and bash. No build step is needed.

```bash
# Run the full regression suite (JSON + structural validation)
bash tests/run_regression_tests.sh

# Run only the Python structural validator
python3 tests/validate_history.py

# Validate a single history file
python3 tests/validate_history.py History/AbbeEstlanderLip.hst

# Validate a specific directory
python3 tests/validate_history.py /path/to/History
```

### What the Tests Check

**Phase 1 -- JSON Validation** (`run_regression_tests.sh`):
- Every `.hst` file in `History/` parses as valid JSON

**Phase 2 -- Structural Validation** (`validate_history.py`):
- Top-level structure is a JSON array
- First action is `loadSceneFile` with a `.smd` filename
- Every action uses a recognized action type key
- Required fields are present for each action type
- Point counts match declared `pointNumber` values
- Texture coordinates are in the expected [0, 1] range
- Displacement vectors are within plausible magnitude
- Material IDs are in the expected set {2..8}

Errors cause a non-zero exit code. Warnings are reported but do not cause
failure.

## C++ Unit Tests

Located in `unit/`. Built with CMake and GoogleTest.

```bash
# From a build directory:
cmake /path/to/tests
cmake --build .
ctest --output-on-failure
```

## Full Simulation Replay Testing

Full replay of history files through the simulation engine requires:

1. **OpenGL context** -- The main loop in `main.cpp` uses GLFW + OpenGL 3
   for rendering. `nextHistoryAction()` calls `_gl3w->drawAll()` and
   `glfwSwapBuffers()` directly.
2. **Scene data files** -- The `.smd` model files referenced by
   `loadSceneFile` must be present in the model directory.
3. **Physics engine** -- TBB task arenas are used for asynchronous physics
   updates (Intel MKL, CUDA solvers).
4. **ImGui GUI** -- The `SurgicalSimGui` class manages the GUI frame loop
   and must be initialized.

### Roadmap for Headless Replay

To enable full automated replay without a display:

1. **EGL/OSMesa offscreen context** -- Replace GLFW window creation with an
   offscreen OpenGL context (EGL on Linux, OSMesa as fallback).
2. **Stub GUI** -- Create a headless `SurgicalSimGui` that skips ImGui
   rendering but still drives the action loop.
3. **Deterministic physics** -- Pin TBB thread count and floating-point
   mode to ensure reproducible results across CI runs.
4. **Golden output comparison** -- After each history replay, export the
   mesh (via `saveCurrentObj`) and compare against a stored reference
   using a geometric tolerance.

## CMake Integration

The top-level `tests/CMakeLists.txt` registers both C++ unit tests and
the Python-based history regression tests with CTest:

```bash
# From a build directory:
cmake /path/to/tests
ctest --output-on-failure
```

CTest test names:
- `HistoryFiles_JSONValidation` -- Python structural validator
- `HistoryFiles_RegressionSuite` -- Full bash regression suite
- `VnBccTetrahedraTests` -- C++ unit tests (from unit/)
- `TetCollisionsTests` -- C++ unit tests (from unit/)
- `BccTetSceneTests` -- C++ unit tests (from unit/)
