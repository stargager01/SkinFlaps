# SkinFlaps Developer Guide

A practical onboarding reference for building, running, and contributing to the
SkinFlaps soft-tissue surgical simulator.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Building on Windows (Visual Studio)](#building-on-windows-visual-studio)
3. [Building on Linux (Ubuntu)](#building-on-linux-ubuntu)
4. [Running the Application](#running-the-application)
5. [Project Structure Overview](#project-structure-overview)
6. [Development Workflow](#development-workflow)
7. [Common Tasks](#common-tasks)

---

## Prerequisites

SkinFlaps is a C++ desktop application that uses projective dynamics for
real-time soft-tissue simulation. It requires an Intel CPU with AVX support and
several external libraries.

### Required Software

| Dependency | Version | Purpose | Download |
|---|---|---|---|
| **Intel oneAPI Base Toolkit** | 2022.0 or later (MKL + TBB) | Math Kernel Library for sparse linear solvers; Threading Building Blocks for parallelism | [Intel oneAPI Base Toolkit](https://www.intel.com/content/www/us/en/developer/tools/oneapi/base-toolkit-download.html) |
| **GLFW 3** | 3.3+ | Cross-platform windowing, input, and OpenGL context | [glfw.org](https://www.glfw.org/) |
| **CMake** | 3.17+ | Build system generator (Linux builds) | [cmake.org](https://cmake.org/download/) |
| **Visual Studio 2022** | v143 toolset (Windows) | C++ compiler and IDE | [Visual Studio](https://visualstudio.microsoft.com/) |
| **GCC** | 9+ (Linux) | C++ compiler with AVX and OpenMP support | System package manager |
| **OpenGL** | 3.x+ | GPU rendering | Included with OS / GPU drivers |
| **Python 3** | 3.6+ | Running history-file regression tests | [python.org](https://www.python.org/) |

### Optional Software

| Dependency | Version | Purpose | Download |
|---|---|---|---|
| **CUDA Toolkit** | 11+ | GPU-accelerated physics solver (cusparse, cusolver) | [NVIDIA CUDA](https://developer.nvidia.com/cuda-toolkit) |
| **Eigen3** | 3.x | Header-only linear algebra (used by some CI configurations) | `apt install libeigen3-dev` or [eigen.tuxfamily.org](https://eigen.tuxfamily.org/) |

### Intel oneAPI Installation Notes

The physics engine (`PDTetPhysics`) depends on Intel MKL for sparse matrix
factorization (Pardiso) and Intel TBB for multithreaded tet cutting. Both are
included in the Intel oneAPI Base Toolkit.

**Windows:**
1. Download the offline installer from the link above.
2. During installation, at minimum select "Intel oneAPI Math Kernel Library" and
   "Intel oneAPI Threading Building Blocks".
3. The default installation path is:
   ```
   C:\Program Files (x86)\Intel\oneAPI
   ```
4. After installation the Visual Studio integration plugin will be available,
   which adds "Intel oneMKL" and "Intel oneTBB" options to the project property
   pages. The `.vcxproj` files already reference these integrations.

**Linux (Ubuntu):**
```bash
# Import Intel GPG key and add the APT repository
wget -O- https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB \
  | gpg --dearmor | sudo tee /usr/share/keyrings/oneapi-archive-keyring.gpg > /dev/null
echo "deb [signed-by=/usr/share/keyrings/oneapi-archive-keyring.gpg] \
  https://apt.repos.intel.com/oneapi all main" \
  | sudo tee /etc/apt/sources.list.d/oneAPI.list
sudo apt-get update
sudo apt-get install -y intel-oneapi-mkl-devel intel-oneapi-tbb-devel
```

Before every build session on Linux you must source the environment script:
```bash
source /opt/intel/oneapi/setvars.sh
```
This sets `MKLROOT`, `TBBROOT`, and adjusts `LD_LIBRARY_PATH` so CMake and the
linker can find the libraries.

### GLFW 3 Installation

**Windows:**
- Download the pre-compiled Windows binaries from [glfw.org/download](https://www.glfw.org/download.html).
- Extract the archive. The project expects the headers and `lib-vc2022/` folder.
  The bundled `imgui_glfw_nfd_lib/extLibs/glfw/` directory already contains the
  required GLFW headers (`include/`) and the static library (`lib-vc2022/glfw3_mt.lib`).
  If building with CMake on Windows, set the environment variable `GLFW3_ROOT`
  to the extracted directory, or use vcpkg: `vcpkg install glfw3:x64-windows`.

**Linux (Ubuntu):**
```bash
sudo apt-get install -y libglfw3-dev
```

---

## Building on Windows (Visual Studio)

This is the primary development platform. The repository ships pre-configured
Visual Studio 2022 solution and project files.

### Step-by-Step from Fresh Clone

1. **Clone the repository:**
   ```
   git clone https://github.com/stargager01/SkinFlaps.git
   cd SkinFlaps
   ```

2. **Install prerequisites** (see [Prerequisites](#prerequisites)):
   - Intel oneAPI Base Toolkit (MKL + TBB)
   - GLFW 3 (bundled under `imgui_glfw_nfd_lib/extLibs/glfw/`)
   - Visual Studio 2022 with the "Desktop development with C++" workload

3. **Create a personal `.props` file** (see next section).

4. **Open the solution:**
   ```
   Build\msvc_2022\SkinFlaps.sln
   ```
   This solution contains five projects with correct dependency ordering:
   - `PhysBAM_subset` -- PhysBAM utility library (no dependencies)
   - `imgui_glfw_nfd_lib` -- Dear ImGui + GLFW + gl3w + file dialog (no dependencies)
   - `gl3wGraphics` -- OpenGL rendering layer (depends on `imgui_glfw_nfd_lib`)
   - `PDTetPhysics_noCuda` -- Projective dynamics physics (depends on `PhysBAM_subset`)
   - `SkinFlaps` -- Main application (depends on all four above)

5. **Select build configuration:**
   - Set the solution platform to **x64** (required -- the AVX/MKL code is 64-bit only).
   - Set the configuration to **Release** for normal use or **Debug** for development.

6. **Build the solution:**
   - `Build > Build Solution` (Ctrl+Shift+B).
   - The output executable lands in `Build\msvc_2022\x64\Release\SkinFlaps.exe`
     (or `x64\Debug\` for Debug builds).

7. **Set the working directory** for debugging:
   - Right-click the `SkinFlaps` project > Properties > Debugging > Working Directory.
   - Set it to the repository root (e.g., `$(SolutionDir)..\..`) so the
     application can find the `Model/` and `History/` directories.

### How to Create a Personal .props File

The repository includes several `.props` (MSBuild property sheet) files that
define machine-specific paths. These files should **not** be committed to source
control with your personal paths. The canonical template is `libPaths.props`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <ImportGroup Label="PropertySheets" />
  <PropertyGroup Label="UserMacros">
    <!-- Path to any external libraries you keep outside the repo -->
    <EXT_LIB>C:\YourName\vsExternalLibraries</EXT_LIB>
    <!-- Root of the Intel oneAPI installation -->
    <INTEL_LIB>C:\Program Files (x86)\Intel\oneAPI</INTEL_LIB>
    <!-- Auto-computed: two directories above the .vcxproj file = repo root -->
    <SFG_DIR>$([System.IO.Directory]::GetParent(
      $([System.IO.Directory]::GetParent($(ProjectDir)).ToString())))</SFG_DIR>
  </PropertyGroup>
  <PropertyGroup />
  <ItemDefinitionGroup />
  <ItemGroup>
    <BuildMacro Include="EXT_LIB"><Value>$(EXT_LIB)</Value></BuildMacro>
    <BuildMacro Include="INTEL_LIB"><Value>$(INTEL_LIB)</Value></BuildMacro>
    <BuildMacro Include="SFG_DIR"><Value>$(SFG_DIR)</Value></BuildMacro>
  </ItemGroup>
</Project>
```

**Macros explained:**
- `EXT_LIB` -- Where you keep external libraries (e.g., GLFW, Eigen). Not
  currently referenced by the `.vcxproj` files directly, but can be used for
  custom configurations.
- `INTEL_LIB` -- Points to the oneAPI root so the project can find
  `$(INTEL_LIB)\mkl\2022.0.0\include` and `$(INTEL_LIB)\tbb\2021.5.0\include`.
  Adjust the version subdirectories if you installed a different oneAPI version.
- `SFG_DIR` / `CLEFTSIM_DIR` -- Automatically resolves to the repository root.

To use a `.props` file: open any project's Property Manager (View > Other
Windows > Property Manager), right-click a configuration, and "Add Existing
Property Sheet". Alternatively, each user can add a `.props` import to
`Build\msvc_2022\SkinFlaps.vcxproj` inside the appropriate `PropertySheets`
import group (the file already has placeholder slots for this).

### CUDA Build Variant

If you have CUDA Toolkit 11+ installed and want GPU-accelerated physics:
- Open `Build\msvc_2022\SkinFlaps_CUDA.sln` instead of `SkinFlaps.sln`.
- This solution references `PDTetPhysics.vcxproj` (with CUDA) instead of
  `PDTetPhysics_noCuda.vcxproj`.
- Set the `$(Cuda_Path)` macro in your `.props` file to your CUDA install root
  (e.g., `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8`).

### Common Windows Build Errors

| Error | Cause | Fix |
|---|---|---|
| `fatal error LNK1181: cannot open input file 'mkl_rt.lib'` | MKL not found | Install Intel oneAPI; verify `INTEL_LIB` path in your `.props` file. Ensure the MKL VS integration is active (VS Installer > Modify > check Intel oneAPI integration). |
| `Cannot open include file: 'tbb/task_arena.h'` | TBB headers not found | Verify `$(INTEL_LIB)\tbb\2021.5.0\include` exists. If your TBB version differs, update the include path in the `.vcxproj` or `.props`. |
| `error C2039: 'avx'...` or illegal instruction at runtime | CPU lacks AVX | SkinFlaps requires AVX instruction set support. Check your CPU (must be Sandy Bridge or newer). |
| `LINK : fatal error LNK1104: cannot open file 'glfw3_mt.lib'` | GLFW static lib missing | Ensure `imgui_glfw_nfd_lib\extLibs\glfw\lib-vc2022\glfw3_mt.lib` exists. Re-download GLFW if needed. |
| `error LNK2019: unresolved external symbol` in PhysBAM | Project build order wrong | Confirm the SkinFlaps project has dependencies on all four library projects in Solution Explorer. |
| `warning C4267: conversion from 'size_t' to 'int'` | Expected; suppressed | The codebase uses `#pragma warning(disable : 4267)` where needed. These are not errors. |

---

## Building on Linux (Ubuntu)

The CMake build system supports Ubuntu 20.04+ with GCC 9+.

### Step 1: Install System Dependencies

```bash
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    cmake \
    libglfw3-dev \
    libeigen3-dev \
    libgl-dev \
    libxrandr-dev \
    libxinerama-dev \
    libxcursor-dev \
    libxi-dev \
    python3
```

### Step 2: Install Intel oneAPI (MKL + TBB)

```bash
# Add Intel APT repository
wget -O- https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB \
  | gpg --dearmor | sudo tee /usr/share/keyrings/oneapi-archive-keyring.gpg > /dev/null
echo "deb [signed-by=/usr/share/keyrings/oneapi-archive-keyring.gpg] \
  https://apt.repos.intel.com/oneapi all main" \
  | sudo tee /etc/apt/sources.list.d/oneAPI.list

sudo apt-get update
sudo apt-get install -y intel-oneapi-mkl-devel intel-oneapi-tbb-devel
```

### Step 3: Source the oneAPI Environment

This must be done in **every terminal session** before configuring or building:
```bash
source /opt/intel/oneapi/setvars.sh
```

You can add this to your `~/.bashrc` for convenience:
```bash
echo 'source /opt/intel/oneapi/setvars.sh > /dev/null 2>&1' >> ~/.bashrc
```

### Step 4: Configure and Build

```bash
cd /path/to/SkinFlaps

# Configure (Release mode recommended for usable frame rates)
cmake -B build -DCMAKE_BUILD_TYPE=Release

# Build (use all available cores)
cmake --build build --parallel $(nproc)
```

The executable will be at `build/SkinFlapsApp`.

### Optional: Enable CUDA

```bash
cmake -B build \
    -DCMAKE_BUILD_TYPE=Release \
    -DSKINFLAPS_ENABLE_CUDA=ON
cmake --build build --parallel $(nproc)
```

Requires CUDA Toolkit 11+ to be installed and on PATH.

### Optional: Build and Run Tests

```bash
cmake -B build \
    -DCMAKE_BUILD_TYPE=Release \
    -DSKINFLAPS_BUILD_TESTS=ON
cmake --build build --parallel $(nproc)
cd build && ctest --output-on-failure
```

The test suite includes:
- **HistoryFiles_JSONValidation** -- validates that all `.hst` files parse as JSON.
- **HistoryFiles_RegressionSuite** -- structural validation of action types and fields.
- **VnBccTetrahedraTests**, **TetCollisionsTests**, **BccTetSceneTests** -- C++ unit tests.

### Common Linux Build Issues

| Symptom | Cause | Fix |
|---|---|---|
| `Could NOT find MKL` | `MKLROOT` not set | Run `source /opt/intel/oneapi/setvars.sh` before cmake. |
| `Could NOT find TBB` | TBB package missing or env not sourced | Install `intel-oneapi-tbb-devel` and source `setvars.sh`. |
| `Could not find GLFW` | `libglfw3-dev` not installed | `sudo apt install libglfw3-dev` |
| `error: 'avx' ...` or `illegal instruction` | GCC not using AVX flags | The top-level CMakeLists.txt adds `-mavx -mfma` automatically. Ensure your CPU supports AVX. |
| `cannot find -lGL` | OpenGL dev headers missing | `sudo apt install libgl-dev` |
| Linker errors about `dlopen`, `pthread` | Missing system libs | These are linked automatically by the CMakeLists.txt (`dl pthread m`). If issues persist, install `libc6-dev`. |
| `fatal error: GLFW/glfw3.h: No such file` | GLFW include path wrong | Verify `libglfw3-dev` is installed: `dpkg -l libglfw3-dev` |

---

## Running the Application

### First Launch

1. **Ensure `Model/` and `History/` directories are accessible.** The
   application expects these directories to be in its working directory (the
   repository root). On Linux, run from the repo root:
   ```bash
   cd /path/to/SkinFlaps
   ./build/SkinFlapsApp
   ```
   On Windows, set the working directory to the repo root in Visual Studio's
   debug properties, or copy the executable next to the `Model/` and `History/`
   directories.

2. **The application opens a GLFW window** showing the Dear ImGui toolbox
   overlaid on the 3D viewport (black background).

3. **Load a model** by selecting a `.smd` scene file from the `Model/`
   directory through the GUI file dialog. The main models are:
   - `FacialFlaps.smd` -- full face model for skin flap simulation
   - `unilatCleftLip_complete.smd` -- complete unilateral cleft lip model
   - `unilatCleftLip_Incomplete.smd` -- incomplete unilateral cleft lip model

### Loading a Model (.smd File)

The `.smd` (Surgical Model Data) file is a JSON-formatted scene description that
references OBJ meshes, texture images, deep bed geometry, and physics parameters
(tetrahedralProperties such as stretch limits and stiffness weights). When a
model is loaded:

1. The surface mesh (`materialTriangles`) is built from the OBJ references.
2. A BCC tetrahedral lattice is created around the surface (`vnBccTetrahedra`).
3. The projective dynamics physics solver is initialized (`pdTetPhysics`).
4. Textures and shaders are loaded for rendering.

### Playing a History File

History files (`.hst`) are JSON arrays that record a sequence of surgical
actions. To play one:

1. Launch the application and load the default model (or press **NEXT** which
   will auto-load the model referenced in the history file).
2. Open a history file from the `History/` directory via the GUI.
3. Press **NEXT** repeatedly to step through the surgical actions, or set the
   counter to advance multiple steps automatically.

Available history files and their procedures:
- `AbbeEstlanderLip.hst` -- Abbe-Estlander lip reconstruction
- `cervicoFacialFlap.hst` -- cervicofacial rotation flap
- `cheekSplasty.hst` -- cheek S-plasty
- `scalpDoubleRotation.hst` -- scalp double rotation flap
- `foreheadFlapToNose.hst` -- paramedian forehead flap to nose
- `TenzelEyelid.hst` -- Tenzel eyelid reconstruction
- `postAuricularEar.hst` -- post-auricular ear flap
- `cleft_CuttingRepair.hst` -- Cutting cleft lip repair
- `cleft_FisherRepair.hst` -- Fisher cleft lip repair
- `cleft_RoseThompson.hst` -- Rose-Thompson cleft lip repair
- `cleft_TennisonRandall.hst` -- Tennison-Randall cleft lip repair

### Basic Surgical Tool Usage

The GUI toolbox provides these interactive tools:

| Tool | Description |
|---|---|
| **Hooks** | Click on the skin surface to place a tissue hook. Drag to stretch and reposition tissue. Right-click to select/move existing hooks. |
| **Fence / Incision** | Click to place fence posts along a desired incision line on the skin surface. The fence posts define a cutting path. |
| **Deep Cut** | After placing a fence, performs a full-thickness incision through the tissue, splitting the tetrahedral mesh along the cutting plane. |
| **Undermine** | Select triangles to separate the skin flap from the deep bed, allowing the flap to be mobilized. |
| **Periosteal Undermine** | Undermines at the periosteal level (deeper layer), allowing wider flap mobilization. |
| **Excise** | Removes a selected patch of tissue (creates a wound defect). |
| **Sutures** | Click on incision edges to place sutures that pull wound edges together. Two clicks define the paired attachment points. |

The physics engine runs asynchronously via TBB. After each tool action the
solver iterates to find a new equilibrium. An hourglass icon appears while
physics is computing.

---

## Project Structure Overview

```
SkinFlaps/
|-- CMakeLists.txt              Top-level CMake build (Linux/cross-platform)
|-- README.md                   Project overview and paper references
|-- LICENSE                     BSD-2-Clause license
|-- libPaths.props              Template .props for machine-specific paths
|-- libPathsCourt.props         Court Cutting's personal .props (reference)
|-- libPathsQisi.props          Qisi Wang's personal .props (reference)
|
|-- Build/
|   `-- msvc_2022/
|       |-- SkinFlaps.sln       Main VS2022 solution (no CUDA)
|       |-- SkinFlaps_CUDA.sln  VS2022 solution with CUDA physics
|       `-- SkinFlaps.vcxproj   Main application project file
|
|-- SkinFlaps/
|   `-- src/                    ** Main application source code **
|       |-- main.cpp            Entry point: GLFW window + ImGui frame loop
|       |-- FacialFlapsGui.h/cpp  GUI layer (Dear ImGui): toolbox, callbacks, file dialogs
|       |-- surgicalActions.h/cpp Orchestrates all surgical tool operations
|       |-- deepCut.h/cpp       Full-thickness incision through tetrahedral mesh
|       |-- skinCutUndermineTets.h/cpp  Base class: surface incision + undermining
|       |-- fence.h/cpp         Interactive fence-post incision path UI
|       |-- hooks.h/cpp         Tissue hook placement and physics constraints
|       |-- sutures.h/cpp       Suture placement and auto-suture line generation
|       |-- bccTetScene.h/cpp   Interface between physics library and surgical code
|       |-- tetCollisions.h/cpp Soft-body collision detection (vertex rays + midpoint rays)
|       |-- tetSubset.h/cpp     Region-specific tet clusters with distinct physics properties
|       |-- vnBccTetrahedra.h/cpp  Virtual-noded BCC tetrahedral mesh data structure
|       |-- vnBccTetCutter_tbb.h/cpp  TBB-parallel tetrahedral mesh cutting
|       |-- remapTetPhysics.h/cpp  Remaps physics state when tet topology changes
|       |-- json.h/cpp          Lightweight JSON parser for .smd and .hst files
|       `-- CDT/                Constrained Delaunay Triangulation (header-only library)
|
|-- PDTetPhysics/               ** Projective dynamics physics engine **
|   |-- CMakeLists.txt          Builds the PDTetPhysics static library
|   |-- include/                Public headers (pdTetPhysics.h, etc.)
|   |-- src/                    PDTetSolver, MergedLevelSet
|   |-- PDDeformer/             Grid deformer, Pardiso wrapper, Schur solver, CUDA solver
|   `-- cmake/                  FindMKL.cmake, FindTBB.cmake, FindIOMP.cmake
|
|-- gl3wGraphics/               ** OpenGL rendering library **
|   |-- CMakeLists.txt
|   |-- gl3wGraphics.h/cpp      Main graphics context and draw loop
|   |-- materialTriangles.h/cpp Triangle mesh with material IDs and texture coords
|   |-- surgGraphics.h/cpp      Surgical scene rendering (surface, tets, instruments)
|   |-- lightsShaders.h/cpp     Shader program management
|   |-- GLmatrices.h/cpp        View/projection matrix stack
|   |-- shapes.h/cpp            Procedural shapes (spheres, cylinders for tools)
|   |-- trackball.h/cpp         Mouse-driven camera rotation
|   `-- Vec3f.h, Mat3x3f.h...  Lightweight math types (used throughout the project)
|
|-- imgui_glfw_nfd_lib/         ** Dear ImGui + GLFW + gl3w + file dialog **
|   |-- CMakeLists.txt
|   |-- imgui*.cpp/h            Dear ImGui core and backends
|   |-- ImGuiFileDialog.h/cpp   Native file dialog integration
|   |-- extLibs/glfw/           Bundled GLFW headers and Windows static libs
|   `-- extLibs/gl3w/           gl3w OpenGL loader
|
|-- PhysBAM_subset/             ** PhysBAM utility library (Fedkiw/Teran/Sifakis) **
|   |-- CMakeLists.txt
|   |-- Public_Library/         Core data structures, math, geometry utilities
|   |-- Common_Libraries/       Common tools
|   `-- StackWalker/            Windows-only stack trace utility
|
|-- simd-numeric-kernels-new/   ** Header-only SIMD numeric kernels **
|                               AVX-optimized matrix/vector operations
|
|-- Model/                      Scene data: .smd files, OBJ meshes, textures (.jpg)
|-- History/                    Recorded surgical procedures (.hst JSON files)
|
|-- tests/                      ** Test infrastructure **
|   |-- CMakeLists.txt          CTest registration (unit + regression)
|   |-- README.md               Detailed test documentation
|   |-- run_regression_tests.sh Bash runner for history file validation
|   |-- validate_history.py     Python structural validator for .hst files
|   `-- unit/                   GoogleTest C++ unit tests
|
`-- .github/workflows/ci.yml   GitHub Actions CI pipeline
```

### How the Components Connect

```
main.cpp
  |
  v
FacialFlapsGui  ------>  gl3wGraphics (rendering)
  |                          |
  v                          v
surgicalActions          materialTriangles (mesh data)
  |    |    |    |
  v    v    v    v
hooks sutures fence deepCut/skinCutUndermineTets
  |    |              |
  +----+--------------+
  |
  v
bccTetScene  -------->  vnBccTetrahedra (tet mesh)
  |    |                vnBccTetCutter_tbb (parallel cutting)
  |    |                tetCollisions (collision detection)
  |    |                tetSubset (region-specific properties)
  |    |                remapTetPhysics (topology change remapping)
  |    v
  |  pdTetPhysics  --->  PDTetPhysics library
  |                       |-- PardisoWrapper (MKL sparse solver)
  |                       |-- SchurSolver
  |                       `-- CudaSolver (optional GPU path)
  v
PhysBAM_subset (utility math, geometry)
simd-numeric-kernels (AVX-optimized operations)
```

The main loop in `main.cpp` alternates between:
1. **GUI frame**: ImGui rendering via `FacialFlapsGui::InstanceCleftGui()`
2. **Physics update**: dispatched asynchronously to a TBB task arena via
   `bccTetScene::updatePhysics()`
3. **Graphics draw**: `gl3wGraphics::drawAll()` renders the surface mesh,
   tools, and surgical instruments

Surgical tool actions flow through `surgicalActions`, which coordinates between
the GUI callbacks, the mesh data structures, and the physics engine.

---

## Development Workflow

### How to Make Changes

1. **Create a feature branch** from `main` or `develop`:
   ```bash
   git checkout -b feature/my-change
   ```

2. **Edit source files** in the relevant subdirectory. Most surgical logic lives
   in `SkinFlaps/src/`. Physics modifications go in `PDTetPhysics/`. Graphics
   changes go in `gl3wGraphics/`.

3. **Build and test locally** (see build instructions above).

4. **Run the regression tests** before committing:
   ```bash
   # Quick: validate history files (no build needed)
   python3 tests/validate_history.py

   # Full: run all tests via CTest (requires build)
   cd build && ctest --output-on-failure
   ```

5. **Open a pull request** against `main`. The CI pipeline will run history
   validation automatically.

### How to Test Changes

- **Interactive testing**: Launch the application, load a model, and manually
  exercise the affected tool. Try replaying relevant history files to verify
  nothing regresses.
- **History regression**: Run `bash tests/run_regression_tests.sh` to validate
  all `.hst` files parse correctly and have valid structure.
- **Unit tests**: The `tests/unit/` directory contains GoogleTest tests for
  `vnBccTetrahedra`, `tetCollisions`, and `bccTetScene`. Build with
  `-DSKINFLAPS_BUILD_TESTS=ON` and run via `ctest`.
- **Visual regression**: For changes to rendering or physics, replay a known
  history file and visually compare the result to expected behavior. You can
  export the mesh state with `surgicalActions::saveCurrentObj()` and diff the
  OBJ output.

### Coding Style Guidelines

The following conventions are observed throughout the existing codebase:

**Naming:**
- Class names: `camelCase` starting lowercase (e.g., `deepCut`, `bccTetScene`,
  `surgicalActions`). Some classes start uppercase when they are acronym-heavy
  (e.g., `FacialFlapsGui`, `GLmatrices`).
- Member variables: prefixed with underscore `_` (e.g., `_deepPosts`,
  `_diagnosticLog`, `_mt`).
- Methods: `camelCase` starting lowercase (e.g., `cutDeep()`, `loadScene()`,
  `addHook()`).
- Static members: prefixed with underscore `_` (e.g., `_springConstant`,
  `_fenceSize`).
- Preprocessor guards: `__DOUBLE_UNDERSCORE_NAME__` style (e.g., `__DEEP_CUT__`,
  `__HOOKS_H__`).
- Typedef/using declarations: ALL_CAPS for map types (e.g., `HOOKMAP`,
  `SUTUREMAP`).

**Formatting:**
- Tabs for indentation (not spaces).
- Opening braces on the same line as the control statement.
- `inline` used liberally for small accessor methods, often defined directly in
  the header.
- Forward declarations preferred over includes where possible.

**File Organization:**
- Each class has a paired `.h`/`.cpp` file named after the class.
- File headers include Author, Date, and Purpose comments.
- `#pragma warning(disable : 4267)` is used to suppress size_t-to-int warnings
  on Windows.

**Error Handling:**
- `std::logic_error` and `std::runtime_error` are thrown for unrecoverable
  errors.
- The main loop catches all exception types and routes them through
  `FacialFlapsGui::handleThrow()` for user display.
- Atomic flags (`physicsDone`, `newTopology`, `taskThreadError`) coordinate
  between the GUI thread and the TBB physics thread.

**Memory Management:**
- Raw pointers for non-owning references (e.g., `materialTriangles *_mt`).
- `std::shared_ptr<sceneNode>` for graphics scene nodes.
- Copy constructors and assignment operators are explicitly deleted on
  classes that should not be copied (e.g., `deepCut`, `skinCutUndermineTets`,
  `tetSubset`).

### How to Use the Diagnostic Logging in deepCut

The `deepCut` class has a built-in diagnostic logging system controlled by the
`_diagnosticLog` boolean flag. When enabled, it writes detailed trace
information to `std::cerr` at key decision points in the cutting algorithm.

**Enabling diagnostic logging:**
```cpp
// In your code (e.g., surgicalActions.cpp before a cut operation):
_incisions.setDiagnosticLog(true);
```

**What gets logged:**
- Entry/exit of `cutDeep()` with post counts and open/closed state.
- Topological connection problems (logged just before an exception is thrown).
- `connectOpenEnd()` entry with post number and intersection counts.
- `surfacePath()` entry with from/to post numbers and ray indices.
- Failed triangle lookups with vertex and material details.

**Example diagnostic output:**
```
deepCut::cutDeep() entry, deepPosts count: 5, frontClosed: 0, backClosed: 1
deepCut::surfacePath() entry, from.postNum: 0, from.rayIndex: 2, to.postNum: 1
deepCut::connectOpenEnd() entry, postNum: 0, totalPosts: 5, triIntersects: 3
```

This is invaluable for debugging cut failures. When a cut throws an exception,
enable the diagnostic log and reproduce the operation to get a detailed trace
leading up to the failure.

---

## Common Tasks

### Adding a New Surgical Tool

1. **Create a new class** in `SkinFlaps/src/` with a `.h`/`.cpp` pair. Follow
   the pattern of `hooks.h/cpp` or `sutures.h/cpp`:
   - Store a pointer to `materialTriangles`, `vnBccTetrahedra`, and
     `pdTetPhysics` for mesh/physics access.
   - Store a pointer to `shapes` and `GLmatrices` for graphics.
   - Provide `setGLmatrices()`, `setShapes()`, `setPhysicsLattice()`,
     `setVnBccTetrahedra()` setter methods.

2. **Add the tool to `surgicalActions`:**
   - Include your header in `surgicalActions.h`.
   - Add a member instance of your tool class.
   - Wire up the `rightMouseDown()`, `rightMouseUp()`, `mouseMotion()`,
     `onKeyDown()` dispatch based on `_toolState`.

3. **Add a GUI button** in `FacialFlapsGui::InstanceCleftGui()` that sets the
   tool state via `setToolState()`. Look at how existing tools are toggled.

4. **Register the tool** in the history system:
   - Define a new action type string in `surgicalActions::nextHistoryAction()`.
   - Implement serialization in `saveSurgicalHistory()`.
   - Implement deserialization in the `nextHistoryAction()` dispatch.
   - Update `tests/validate_history.py` to recognize the new action type.

5. **Add the new `.cpp` file** to both:
   - `CMakeLists.txt` (in the `SKINFLAPS_APP_SOURCES` list)
   - `Build/msvc_2022/SkinFlaps.vcxproj` (in the `<ClCompile>` ItemGroup)

### Modifying Physics Parameters

Physics parameters are configured at several levels:

- **Global stretch limits**: Set in the `.smd` scene file under the
  `tetrahedralProperties` section. These are loaded by `bccTetScene::loadScene()`
  and stored in `_globalStretchMin` / `_globalStretchMax`.

- **Region-specific stretch limits**: Use the `bccTetScene` API:
  ```cpp
  bccTetScene* bts = sa->getBccTetScene();
  // Set per-region properties
  bts->setRegionStretchLimit("cheek", 0.7f, 1.8f);
  bts->setRegionStretchLimit("scalp", 0.9f, 1.15f);

  // Or set full properties including stiffness weights
  facialRegionProperties props("eyelid", 0.6f, 2.0f, 0.5f, 1.0f, "eyelidRegion.obj");
  bts->setRegionProperties(props);

  // Or get clinically-informed defaults
  auto defaults = bccTetScene::getDefaultRegionProperties();
  ```

- **Hook spring constant**: `hooks::setSpringConstant(float k)` -- controls how
  stiff the tissue hooks feel.

- **Suture spacing**: `sutures::setAutoSutureSpacing(float spacing)` -- controls
  the gap between auto-generated sutures in a suture line.

- **Collision density**: `tetCollisions::setCollisionDensity(float multiplier)` --
  values above 1.0 add midpoint collision rays on convex surfaces. Useful for
  tight closures over convex geometry (see README Known Issues #2).

- **Cut spacing**: `deepCut::setCutSpacingInv(float spacing)` -- inverse of the
  deep cut interior point spacing. Default is 15.0. Higher values give finer
  cuts but are more expensive.

- **Low tet weight**: Controlled per-region via `facialRegionProperties` or
  globally through the `.smd` file. Affects stiffness of the low-resolution
  multiresolution tets.

### Adding a New Facial Region for Stretch Limits

The region-based stretch limit system (`bccTetScene`) allows different parts of
the face to have different mechanical properties. To add a new region:

1. **Create a closed manifold OBJ file** that encloses the desired region's
   tetrahedra. Place it in the `Model/` directory. The OBJ must be a closed
   surface so the inside/outside test works (uses ray casting via `tetSubset`).

2. **Register the region** in code. In `bccTetScene.cpp`, add an entry to
   `getDefaultRegionProperties()`:
   ```cpp
   defaults.emplace_back("myRegion", 0.8f, 1.5f, 0.0f, 0.0f, "myRegion.obj");
   ```

3. **Reference the OBJ in the scene file** (`.smd`). Add a region entry in the
   `tetrahedralProperties` section with the OBJ filename, stretch min/max, and
   optional stiffness weights.

4. **The region is applied during `loadScene()`**. The method
   `bccTetScene::applyRegionSubsets()` iterates over all regions with a
   `subsetObjFile`, creates a `tetSubset` for each, and passes the per-region
   strain limits and weights to the physics solver.

### Recording a New History File

History files capture a surgical procedure for replay and training:

1. **Launch the application** and load the desired model.

2. **Perform the surgical procedure** interactively using the tools (hooks,
   fence/incision, undermine, sutures, etc.).

3. **Save the history** through the GUI's file save dialog. This calls
   `surgicalActions::saveSurgicalHistory()` which serializes the recorded action
   sequence as a JSON array.

4. **Place the `.hst` file** in the `History/` directory.

5. **Validate the new file:**
   ```bash
   python3 tests/validate_history.py History/myNewProcedure.hst
   ```

6. **Test replay** by loading the history file and stepping through with NEXT.

**History file format:**
The file is a JSON array. The first element must be a `loadSceneFile` action:
```json
[
  {"loadSceneFile": "FacialFlaps.smd"},
  {"addHook": {"material": 2, "hookNum": 0, "historyTexture": [0.5, 0.3], "displacement": [0.0, 0.0, 0.0]}},
  {"makeIncision": [{"startOpen": false, "endOpen": false, "pointNumber": 3}, ...]},
  ...
]
```

Recognized action types: `loadSceneFile`, `addHook`, `moveHook`, `deleteHook`,
`makeIncision`, `undermine`, `excise`, `addSuture`, `deleteSuture`,
`makeDeepCut`, `periostealUndermine`, `promoteSutureApproximations`,
`pausePhysics`.

---

## Further Resources

- **Paper (implementation details)**: [Computer Methods and Programs in Biomedicine, 2022](https://doi.org/10.1016/j.cmpb.2022.106730)
- **Projective dynamics**: [Bouaziz et al., 2014](https://www.cs.utah.edu/~ladislav/bouaziz14projective/bouaziz14projective.html)
- **Physics library paper**: [Wang Q. et al., Computer Graphics Forum](https://onlinelibrary.wiley.com/doi/10.1111/cgf.14385)
- **User guide video**: [YouTube -- SkinFlaps Users Guide](https://youtu.be/xuKLgMS5gzk)
- **Cleft lip tutorial**: [YouTube -- Cleft Lip Tutorial](https://youtu.be/CzBiVJ5Q508)
- **GLFW documentation**: [glfw.org](https://www.glfw.org/)
- **Intel oneAPI**: [Intel oneAPI Base Toolkit](https://www.intel.com/content/www/us/en/developer/tools/oneapi/base-toolkit-download.html)
