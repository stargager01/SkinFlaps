# SkinFlaps - Agent Guide

## 1. Project Overview

**Project Name:** SkinFlaps (v1.2.1)

**Purpose:** Soft tissue surgical simulation for skin flap design and surgical planning. Allows surgeons to experiment with their own surgical designs to solve soft tissue surgery problems, including facial skin flap procedures and cleft lip repair.

**Core Technology:** Projective Dynamics (Bouaziz et al.) based physics engine with multi-resolution tetrahedral mesh, AVX2/SIMD-optimized numerical kernels, and optional CUDA GPU acceleration.

**Authors:**
- Qisi Wang & Eftychios Sifakis (Physics Library) - University of Wisconsin, Madison
- Court Cutting MD (Surgical Interface/Graphics) - NYU Grossman School of Medicine

**License:** BSD-3-Clause with extended surgical disclaimer

**References:**
- Main paper: https://doi.org/10.1016/j.cmpb.2022.106730
- Physics paper (Wang Q et al.): https://onlinelibrary.wiley.com/doi/10.1111/cgf.14385
- Projective Dynamics: https://www.cs.utah.edu/~ladislav/bouaziz14projective/bouaziz14projective.html

---

## 2. Directory Structure

| Directory | Description |
|---|---|
| `SkinFlaps/src/` | Core simulation source: surgical tools, GUI, mesh cutting, physics integration |
| `PDTetPhysics/` | Projective Dynamics physics solver library (main solver + PDDeformer engine) |
| `PDTetPhysics/PDDeformer/` | Core tetrahedral FEM deformation engine with SIMD/CUDA support |
| `PhysBAM_subset/` | Subset of Stanford PhysBAM library: geometry, collision, math tools |
| `gl3wGraphics/` | OpenGL 3+ rendering: materials, scene graph, lighting, shaders |
| `imgui_glfw_nfd_lib/` | Dear ImGui + GLFW UI framework with native file dialogs |
| `simd-numeric-kernels-new/` | AVX2/SIMD-optimized linear algebra kernels (SVD, matrix multiply) |
| `Model/` | 3D models (.obj), textures (.jpg), shaders, and scene definitions (.smd) |
| `History/` | Pre-recorded surgical procedure examples (.hst files) |
| `Build/msvc_2022/` | Windows Visual Studio 2022 build configuration and solution files |

---

## 3. Installation and Build

### Prerequisites
- **Intel oneAPI Math Kernel Library (MKL)** - linear algebra, sparse solvers (PARDISO)
- **Intel Threading Building Blocks (TBB)** - multi-threaded task parallelism
- **GLFW 3** - window creation and input handling
- **CUDA Toolkit 11** (optional) - GPU acceleration
- **Eigen3** (optional) - for SIMD kernel tests

### Supported Platforms
- **Windows 10 (64-bit):** Visual Studio 2022 - primary platform, solution files in `Build/msvc_2022/`
- **Ubuntu Linux:** GCC/Clang - build instructions in `Build/` directory

### Platform Restriction
**macOS is not supported** due to AVX instruction set requirements and Intel MKL dependency, which are not available on Apple Silicon hardware.

### Build System
- **CMake 3.17+** for library components (`PDTetPhysics`, `gl3wGraphics`, `imgui_glfw_nfd_lib`, `simd-numeric-kernels-new`)
- **Visual Studio solution files** for the main application (`Build/msvc_2022/SkinFlaps.sln`)
- Library path configuration via `.props` files: `libPaths.props`, `libPathsCourt.props`, `libPathsQisi.props`

### Key Build Variants
- `SkinFlaps.sln` - Standard CPU build
- `SkinFlaps_CUDA.sln` - CUDA-enabled GPU-accelerated build

---

## 4. Architecture

### Entry Point
`SkinFlaps/src/main.cpp` (134 lines) - Initializes GLFW/OpenGL window, creates physics solver via `bccTetScene`, runs main event loop with TBB `task_arena` for async physics updates.

### Core Class Hierarchy

```
SurgicalSimGui (Main UI Container - imgui-based)
  |
  +-- surgicalActions (Surgical operation handler & UI callbacks)
  |     |
  |     +-- bccTetScene (Physics scene management)
  |     |     +-- vnBccTetrahedra (BCC tetrahedral lattice mesh)
  |     |     +-- pdTetPhysics (Physics solver wrapper)
  |     |     +-- vnBccTetCutter_tbb (TBB-parallel mesh cutting)
  |     |     +-- tetCollisions (Collision detection/response)
  |     |     +-- tetSubset (Multi-resolution physics regions)
  |     |     +-- remapTetPhysics (Topology change remapping)
  |     |
  |     +-- deepCut (Incision/deep cut operations)
  |     +-- skinCutUndermineTets (Tissue undermining)
  |     +-- sutures (Surgical suture constraints)
  |     +-- hooks (Tissue manipulation constraints)
  |     +-- fence (Boundary/constraint management)
  |     +-- surgGraphics (Surgical visualization)
  |
  +-- gl3wGraphics (Rendering engine)
        +-- materialTriangles (Textured surface rendering)
        +-- sceneNode (Scene graph nodes)
        +-- lightsShaders (GLSL shader & lighting management)
        +-- shapes (Primitive shape rendering)
        +-- trackball (Arcball camera control)
```

### Physics Pipeline
1. Physics paused while surgeon manipulates tissue
2. Forces applied -> TBB spawns async physics update
3. `pdTetPhysics` / `GridDeformerTet` solves using SIMD-optimized kernels
4. Results remapped to `vnBccTetrahedra` nodes
5. Collision detection/response via `tetCollisions`
6. Graphics updated on master thread
7. Next physics iteration spawned

### Key Source Files

| File | Lines | Purpose |
|---|---|---|
| `SkinFlaps/src/deepCut.cpp` | ~2650 | Surgical incision and deep cut through tissue layers |
| `SkinFlaps/src/surgicalActions.cpp` | ~2470 | Main surgical action handler and UI callback dispatch |
| `SkinFlaps/src/vnBccTetCutter_tbb.cpp` | ~2410 | TBB-parallel BCC tetrahedral mesh cutting |
| `SkinFlaps/src/skinCutUndermineTets.cpp` | ~2120 | Tissue undermining and cutting topology management |
| `SkinFlaps/src/vnBccTetrahedra.cpp` | ~1030 | Virtual-noded BCC tetrahedral lattice |
| `SkinFlaps/src/FacialFlapsGui.h` | ~890 | Main GUI interface (ImGui/GLFW) |
| `SkinFlaps/src/bccTetScene.cpp` | ~550 | Scene management for BCC tet simulation |
| `SkinFlaps/src/sutures.cpp` | ~540 | Surgical suture constraint system |

---

## 5. Feature Summary

### Multi-Resolution Tetrahedral Physics
- Initial model: **620,000** tetrahedra reduced to **17,000** at startup
- As surgeon operates, only the surgical subvolume is promoted to high resolution
- Fine incision detail rendered with high accuracy in active regions
- Peripheral areas remain at lower resolution for performance

### Surgical Tools
- **Hooks:** Tissue manipulation points with spring constraints
- **Sutures:** Tissue closure with sliding constraints
- **Deep Cut:** Incisions through multiple tissue layers
- **Undermining:** Tissue separation and flap creation
- **Fence:** Surgical boundary/constraint management

### Surgical Examples (History/)
**Skin Flap Procedures:**
- `AbbeEstlanderLip.hst` - Upper lip reconstruction via Abbe flap
- `cervicoFacialFlap.hst` - Cervicofacial rotation flap
- `cheekSplasty.hst` - Cheek augmentation/reduction
- `scalpDoubleRotation.hst` - Scalp defect closure with two rotation flaps
- `foreheadFlapToNose.hst` - Paramedian forehead flap to nasal defect
- `postAuricularEar.hst` - Post-auricular ear flap closure
- `AntiaBuch_ear.hst` - Antia-Buch ear procedure
- `TenzelEyelid.hst` - Tenzel eyelid reconstruction

**Cleft Lip Repair:**
- `cleft_CuttingRepair.hst` - Dr. Cutting's technique
- `cleft_FisherRepair.hst` - David Fisher's repair
- `cleft_RoseThompson.hst` - Rose/Thompson technique
- `cleft_TennisonRandall.hst` - Tennison/Randall technique
- `FurlowPalateRepair.hst` - Furlow palatal repair

---

## 6. Known Issues and Bugs

### From README (Known Issues for Future Work)
1. **Uniform stretch limits** - All flaps use the same stretch limit parameter. Different facial regions (cheek, eyelid, scalp, forehead) have different stretch characteristics in reality.
2. **Collision response** - Inadequate in areas where a tight flap closure is done over a very convex surface. Increased collision density is planned.

### From BugsNeedingFix.txt
1. Incision in/out to pre-existing incision begin/end
2. Change History mechanism and program motif to deterministic
3. Rewrite BCC tet embed program using a centroid motif
4. Deep cut open begin/end change to plane extension rather than bilinear extrapolation
5. Bug hunt mechanism for failed deep cuts
6. More consistent response and recovery from throws
7. Check code to remove infinite loop possibilities (giving a throw into item 6)

---

## 7. Code Owners

| Component | Owner |
|---|---|
| Physics Library (PDTetPhysics, PDDeformer) | Qisi Wang, Eftychios Sifakis |
| Surgical Interface, Tools, Graphics | Court Cutting MD (@ccuttingmd) |
| SIMD Numeric Kernels | Qisi Wang, Eftychios Sifakis |
| PhysBAM Subset | Stanford PhysBAM project (subset) |

---

## 8. Claude AI Skills for This Project

### Code Summarization
- Auto-summarize each directory's code functionality
- Convert function/class descriptions to natural language
- Generate inline documentation for complex algorithms

### Dependency Mapping
- Extract and document external library dependencies (MKL, TBB, GLFW, CUDA)
- Generate installation guides for each platform
- Track version compatibility

### Simulation Workflow
- Step-by-step procedure descriptions for surgical examples
- GUI operation sequence documentation (History file selection -> GUI manipulation -> result inspection)

### Known Issues Tracker
- Collect TODO/FIXME comments from source code
- Consolidate with BugsNeedingFix.txt items
- Generate improvement roadmap documentation

### Educational Guide
- Explain Projective Dynamics concepts for new contributors
- Document the multi-resolution tetrahedral mesh approach
- Describe the surgical tool pipeline and constraint system

---

## 9. Development Notes

### C++ Standards and Patterns
- C++11 standard with heavy use of templates
- SIMD AVX2 with 64-byte alignment and block width of 16
- Intel TBB for task-based parallelism
- Shared pointers for scene management
- Unordered maps for spatial lookup

### Key Compiler Flags
- AVX instruction set enabled (`/arch:AVX` on MSVC)
- `NOMINMAX` and `_ENABLE_EXTENDED_ALIGNED_STORAGE` defined on Windows
- `-qopenmp -std=gnu++11` for SIMD kernels on Linux

### Video Tutorials
- [Users Guide - Facial Flap Closure](https://youtu.be/xuKLgMS5gzk)
- [Cleft Lip Tutorial](https://youtu.be/CzBiVJ5Q508)
