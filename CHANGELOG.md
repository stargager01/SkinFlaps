# Changelog

All notable changes to the SkinFlaps surgical simulator are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/).

---

## [3.1.1] - 2026-02-12

Deployment readiness: GUI tool visibility filtering, CI pytest job, cleanup.

### Changed

- **GUI**: Shoulder tools (Anchor, Scope, Grasp) now only visible when a shoulder
  model is loaded (`AnatomyType::SHOULDER`); previously shown for all anatomies
- **CI**: Added `python-tests` job to GitHub Actions — runs all 172 pytest tests
  on every push/PR (no C++ build or Intel/CUDA dependencies needed)
- **`.plan`**: Updated obsolete `ShoulderPrototype.smd` reference to `ShoulderMinimal.smd`

---

## [3.1.0] - 2026-02-12

Major release: multi-anatomy generalization, shoulder surgery extension,
material layer configurability, and comprehensive test/CI infrastructure.

**43 commits | 70 files changed | +20,162 / -1,329 lines**

### Added

#### Shoulder Surgery Extension
- Shoulder anatomy model: 7 OBJ files (ShoulderSkin, ShoulderDeepBed, 3 bones, deltoid muscle, supraspinatus tendon)
- `ShoulderMinimal.smd` scene descriptor with shoulder-specific physics parameters
- `ShoulderSkin.bed` deep bed mapping (386 vertices, closest-point projection)
- `shoulderFragmentShader.txt` with procedural texturing for tendon (11), capsule (12), bone (13) materials
- Three new surgical tool states: Suture Anchor (8), Arthroscope (9), Grasper (10)
- `AnatomyType` enum (`FACIAL`, `SHOULDER`, `GENERIC`) with auto-detection from scene name
- `tissueRegionProperties` (renamed from `facialRegionProperties`) for generic region handling
- Shoulder-specific tissue regions: skin_deltoid, deltoid_muscle, supraspinatus_tendon, joint_capsule, bone

#### materialLayerConfig System
- `materialLayerConfig.h` standalone header with 13 configurable tissue layer fields
- Replaced 149 hardcoded material ID comparisons across 5 source files
  - `skinCutUndermineTets.cpp`: 72 replacements
  - `deepCut.cpp`: 50 replacements
  - `surgicalActions.cpp`: 20 replacements
  - `tetCollisions.cpp`: 4 replacements
  - `sutures.cpp`: 3 replacements
- 11 predicate helpers (`isSkinSurface()`, `isDeepBed()`, `isPeriosteal()`, etc.)
- `.smd` file loading with `HasKey()` optional override and defaults fallback
- `validateScene()` for material layer ID validation at load time

#### Testing Infrastructure
- 172 Python and C++ tests total
- `tests/test_shoulder_integration.py`: 36 shoulder model validation tests
- `tests/test_material_layers.py`: materialLayerConfig readiness tests
- `tests/test_loading_pipeline.py`: scene loading pipeline tests
- `tests/test_path_compatibility.py`: 20 Linux path compatibility tests
- `tests/validate_obj.py`: OBJ manifold/winding validation
- `tests/validate_history.py`: History file validation
- `tests/unit/test_bccTetScene.cpp`: BCC tet scene unit tests
- `tests/unit/test_tetCollisions.cpp`: collision detection unit tests
- `tests/unit/test_vnBccTetrahedra.cpp`: BCC tetrahedra unit tests
- `tests/run_regression_tests.sh`: regression test runner

#### Build & CI
- Top-level `CMakeLists.txt` with unified build system
- `PhysBAM_subset/CMakeLists.txt` for PhysBAM library component
- `.github/workflows/ci.yml` GitHub Actions CI pipeline (build + test)
- Updated `PDTetPhysics/CMakeLists.txt` and `imgui_glfw_nfd_lib/CMakeLists.txt`

#### Documentation
- `docs/DEVELOPER_GUIDE.md`: comprehensive developer onboarding guide
- `docs/FILE_FORMATS.md`: `.hst` and `.smd` JSON schema reference
- `docs/model_extension_guide.md`: step-by-step guide for adding new anatomy models
- `docs/shoulder_surgery_guide.md`: shoulder model user guide
- `docs/Doxyfile`: Doxygen configuration for API documentation
- `agent.md`: project documentation for AI-assisted development
- `tests/README.md`: test infrastructure documentation

#### Minimal Test Model
- `Model/MinimalTest.obj`, `MinimalTest.bed`, `MinimalTest.smd` for loading pipeline tests
- `Model/FacialFlaps.smd` scene descriptor for facial model

### Changed

#### Code Generalization
- `SurgicalSimGui` (renamed from `FacialFlapsGui` class) for anatomy-agnostic GUI
- GUI header refactored: 887 -> 123 lines (`FacialFlapsGui.h`), static -> instance members
- Scene loader now auto-detects anatomy type and configures shaders/tools per anatomy
- Configurable fragment shader selection per anatomy type

#### Stability & Safety
- Loop guards added to 9 potentially infinite loops
- 17 structured exception catch blocks throughout the codebase
- Thread safety: mutex protection on `taskThreadErrorStr`
- 99 `assert()` calls converted to catchable exceptions in incision code
- `loadScene` pipeline wrapped with try-catch to prevent `abort()` crashes
- Defensive bounds checks for MSVC vector assertions
- JSON parser fix: empty objects with whitespace no longer parsed as `NULLVal`
- JSON `mValueType==ObjectVal` crash fixed with defensive type checks
- Barycentric weight assert crash fixed: floating-point precision errors clamped
- `macrotetRecutCore` skipped when no virtual-noded centroids exist
- ImGui assertion fix: `EndFrame()` added to catch blocks in main loop

#### Bug Fixes
- Deep cut path handling improvements
- Incision T-in detection logic corrected
- Deterministic history replay via canonicalization
- Collision density improvements for convex surfaces
- Vector out-of-bounds fix in `linkMicrotetsToMegatets` for simple models
- Load error diagnostics: specific failure reason shown in one dialog
- Physics lattice error messages now show specific cause instead of generic text

#### Linux Compatibility
- 6 hardcoded `"\\"` path separators replaced with `PATH_SEP`/`PATH_SEP_CHAR` macros
- Linux default directories: `$HOME/SkinFlaps` (was `C:\Users\SkinFlaps`)
- File existence checks before texture/shader/OBJ loading in `bccTetScene`
- `tetrahedralProperties`: initialized defaults with range validation
- Error messages now include specific file paths

#### OBJ Model Architecture
- ShoulderSkin.obj consolidated to single-shell architecture (materials {1, 2, 7})
- 5 OBJs fixed: inverted face winding corrected (2282 faces flipped via BFS)
- Unused pole vertices removed (Euler characteristic 4 -> 2)
- Deep bed defined via `.bed` file only; material 5 runtime-assigned (not in OBJ)
- `sscanf` format fix: `%ld` -> `%d` in `setDeepBed()` for `int topVert`

### Removed

- `Model/ShoulderPrototype.smd` (replaced by `ShoulderMinimal.smd`)
- `Model/ShoulderSkin_single_layer.obj` (merged into multi-layer `ShoulderSkin.obj`)
- Hardcoded material ID constants throughout codebase (replaced by `materialLayerConfig`)
- `facialRegionProperties` name (renamed to `tissueRegionProperties`)
- Static member variables in GUI header (converted to instance members)

---

## [1.2.1] - 2024 (prior release)

Baseline version before this development branch.

- Multi-resolution tetrahedral physics (620K -> 17K tetrahedra)
- Facial skin flap surgery simulation
- Cleft lip repair simulation
- Projective Dynamics solver with AVX2/SIMD optimization
- 13 pre-recorded surgical procedure examples
- Windows 10 (VS 2022) and Ubuntu Linux support

---

[3.1.1]: https://github.com/stargager01/SkinFlaps/compare/v3.1.0...claude/setup-skinflaps-project-yg4Ne
[3.1.0]: https://github.com/stargager01/SkinFlaps/compare/main...v3.1.0
[1.2.1]: https://github.com/stargager01/SkinFlaps/releases/tag/v1.2.1
