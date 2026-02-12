# Model Extension Guide

How to create and extend surgical simulation models for the SkinFlaps simulator.
This guide documents the improvement process from hardcoded facial-only support
to a configurable multi-anatomy system, and provides a step-by-step procedure
for adding new anatomical models.

**Related documentation:**
- [FILE_FORMATS.md](FILE_FORMATS.md) — `.smd` and `.hst` JSON schema reference
- [shoulder_surgery_guide.md](shoulder_surgery_guide.md) — Shoulder prototype details
- [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) — Build environment setup

---

## Table of Contents

1. [Overview](#1-overview)
2. [Background: Why Multi-Layer Models?](#2-background-why-multi-layer-models)
3. [Improvement Phases](#3-improvement-phases)
   - [Phase 1: materialLayerConfig Introduction](#phase-1-materiallayerconfig-introduction)
   - [Phase 2: Configurable .smd Structure](#phase-2-configurable-smd-structure)
   - [Phase 3: Multi-Layer OBJ Merge](#phase-3-multi-layer-obj-merge)
   - [Phase 3a: Disconnected Shells Fix](#phase-3a-disconnected-shells-fix)
4. [Multi-Layer OBJ Structure](#4-multi-layer-obj-structure)
5. [Step-by-Step: Adding a New Anatomy Model](#5-step-by-step-adding-a-new-anatomy-model)
6. [Lattice Configuration](#6-lattice-configuration)
7. [Glossary](#7-glossary)
8. [FAQ](#8-faq)

---

## 1. Overview

The SkinFlaps simulator was originally designed for facial soft tissue surgery.
All tissue layer identifiers (boundary, skin surface, deep bed, periosteum, etc.)
were hardcoded as integer constants throughout the codebase. This made it
impossible to add non-facial anatomy models without modifying source code.

Through a three-phase refactoring process, the system was generalized to support
any anatomical region via configuration:

```
Phase 1: Replace 149 hardcoded material IDs with materialLayerConfig references
Phase 2: Load materialLayers from .smd scene files (JSON config)
Phase 3: Create multi-layer OBJ meshes with proper physics anchoring
```

**Result:** New anatomy models (shoulder, knee, etc.) can be added by preparing
model files and writing a `.smd` configuration — no C++ code changes required.

---

## 2. Background: Why Multi-Layer Models?

The physics solver requires a mesh with multiple tissue layers to function:

```
┌──────────────────────────────────────────┐
│  Material 2: Skin Surface                │  ← Visible surgical surface
│  (user interacts with this layer)        │
├──────────────────────────────────────────┤
│  Material 1: Boundary                    │  ← Peripheral edge anchors
│  (prevents mesh from floating freely)    │  ← periferalWeight in physics
├──────────────────────────────────────────┤
│  Material 5: Deep Bed                    │  ← Undermining target layer
│  (flap bottom surface during incision)   │
├──────────────────────────────────────────┤
│  Material 7: Periosteum                  │  ← Fixed bone-surface anchors
│  (immovable reference for physics)       │  ← fixedWeight in physics
└──────────────────────────────────────────┘
```

**Why a single-layer model fails:**

| Problem | Cause | Effect |
|---------|-------|--------|
| Physics solver singular matrix | No material 1 or 7 triangles | `fixPeriostealPeriferalVertices()` finds no anchors → `setFixedVertices()` receives empty data → solver cannot converge |
| Hook tool crash | No fixed vertices | `initPdPhysics()` fails when initializing solver constraints |
| Knife tool crash | No deep bed topology | `createFlapTopBottomVertices()` cannot create flap bottom surface without material 5 faces |

**Key insight:** All tissue layers must be in the **same dynamic OBJ file**. Static
objects are GPU-only (rendering) and do not participate in `materialTriangles`
or physics simulation.

---

## 3. Improvement Phases

### Phase 1: materialLayerConfig Introduction

**Problem:** 149 hardcoded integer comparisons like `mat == 2`, `mat > 6`,
`addTriangle(V, 3, T)` scattered across 5 source files.

**Solution:** Extracted a standalone configuration struct and predicate helpers.

**File: `SkinFlaps/src/materialLayerConfig.h`**
```cpp
struct materialLayerConfig {
    // Core layers (facial defaults)
    int boundary = 1;
    int skinSurface = 2;
    int incisionEdge = 3;      // created at runtime during skinCut()
    int subcutaneous = 4;      // created at runtime during skinCut()
    int deepBed = 5;
    int muscle = 6;
    int periosteum = 7;
    int periosteumUndermined = 8;
    int undermineMarker = 10;
    // Extension fields for non-facial anatomies
    int tendon = -1;           // -1 = not used
    int jointCapsule = -1;
    int boneSurface = -1;
    int arthroscopicPortal = -1;
};
```

**Predicate helpers** (in `skinCutUndermineTets.h`, protected):
```cpp
bool isSkinSurface(int mat) const { return mat == _matLayers.skinSurface; }
bool isIncisionEdge(int mat) const { return mat == _matLayers.incisionEdge; }
bool isDeepBed(int mat) const { return mat == _matLayers.deepBed; }
bool isPeriosteal(int mat) const {
    return mat == _matLayers.periosteum || mat == _matLayers.periosteumUndermined;
}
bool isDeepTissue(int mat) const {
    return mat == _matLayers.deepBed || mat == _matLayers.muscle
        || mat == _matLayers.periosteum || mat == _matLayers.periosteumUndermined;
}
// ... 11 predicates total
```

**Replacement counts by file:**

| File | Replacements | Pattern examples |
|------|-------------|-----------------|
| `skinCutUndermineTets.cpp` | 72 | `mat == 2` → `isSkinSurface(mat)` |
| `deepCut.cpp` | 50 | `addTriangle(V, 6, T)` → `addTriangle(V, _matLayers.muscle, T)` |
| `surgicalActions.cpp` | 20 | `> 3 && < 7` → `== subcutaneous \|\| == deepBed \|\| == muscle` |
| `tetCollisions.cpp` | 4 | `== 5` → `== _matLayers.deepBed` |
| `sutures.cpp` | 3 | `== 2` → `== _matLayers.skinSurface` |
| **Total** | **149** | |

**Important:** Default values match the original hardcoded values, so the
facial model behavior is unchanged.

---

### Phase 2: Configurable .smd Structure

**Problem:** materialLayerConfig defaults work for facial models, but new
anatomies need different layer mappings.

**Solution:** Load `materialLayers` section from `.smd` scene files. Each field
uses `HasKey()` for optional override with defaults fallback.

**Loading code** (`bccTetScene.cpp`):
```cpp
if ((oit = scnObj.find("materialLayers")) != scnObj.end()) {
    json::Object mlObj = oit->second.ToObject();
    if (mlObj.HasKey("boundary"))    _materialLayers.boundary = mlObj["boundary"].ToInt();
    if (mlObj.HasKey("skinSurface")) _materialLayers.skinSurface = mlObj["skinSurface"].ToInt();
    // ... all 13 fields with HasKey pattern
}
// If no materialLayers section → defaults used (facial model behavior)
```

**Plumbing:** The config is propagated after lattice creation:
```
bccTetScene::loadScene()
  → deepCut.setMaterialLayers(_materialLayers)
  → tetCollisions.setMaterialLayers(_materialLayers)
  → sutures.setMaterialLayers(_materialLayers)
```

**Validation** (`validateScene()`): Checks that core IDs are positive and unique.

---

### Phase 3: Multi-Layer OBJ Merge

**Problem:** ShoulderMinimal's `ShoulderSkin.obj` had only material 2 (skin surface).
Hook/knife operations crashed because the physics solver had no fixed vertices
and the incision system had no deep bed topology.

**Solution:** Merge skin and deep bed OBJ files into a single multi-layer mesh.

**Before (single-layer, broken):**
```
ShoulderSkin.obj:    386 verts, 768 faces, usemtl 2 only
ShoulderDeepBed.obj: 242 verts, 480 faces, usemtl 5 only (separate file)
```

**After (multi-layer, working):**
```
ShoulderSkin.obj: 628 verts, 1248 faces
  usemtl 1 →  24 faces (boundary: skin bottom fan → peripheral anchors)
  usemtl 2 → 744 faces (skin surface: main skin mesh)
  usemtl 5 → 460 faces (deep bed: inner tissue surface)
  usemtl 7 →  20 faces (periosteum: deep bed bottom fan → fixed anchors)
```

**Merge strategy:**
1. Skin vertices (1–386) kept as-is
2. Deep bed vertices appended (387–628) with index offset
3. Skin bottom fan faces (24) relabeled from material 2 → material 1
4. Deep bed bottom fan faces (20) relabeled from material 5 → material 7
5. `.bed` file unchanged (maps skin vertex indices 0–385 only)

**Lattice resolution** also increased (`nTetSizeLevels: 1→2`, `maxDimMegatetSubdivs: 10→16`)
to provide sub-megatet tetrahedra needed for topology operations.

---

### Phase 3a: Disconnected Shells Fix

**Problem:** The Phase 3 merge created a valid multi-material OBJ, but the BCC
lattice builder crashed during `getConnectedComponents()` with a
`Solid ordering error`.

**Root cause:** The merged OBJ contained **two disconnected closed shells**
nested inside each other — the skin dome and the deep bed dome had no shared
vertices or edges. Each was a topologically independent closed sphere
(Euler characteristic V-E+F = 2, zero boundary edges).

```
Phase 3 merge (BROKEN):

  ╭─── skin shell (mat 1+2) ────╮     Shell 1: 768 faces, 386 verts
  │  closed sphere, Euler=2     │     ← no connection
  │                              │
  │  ╭── deep bed shell ──╮     │     Shell 2: 480 faces, 242 verts
  │  │  (mat 5+7)         │     │     ← no connection
  │  │  closed sphere     │     │
  │  ╰────────────────────╯     │     Shared vertices: 0
  ╰──────────────────────────────╯     Shared edges: 0
```

**Why the BCC tet cutter fails:** The `getConnectedComponents()` function
(vnBccTetCutter_tbb.cpp:1608) processes triangles within each BCC tetrahedron.
When a tet edge passes through both shells, the algorithm finds 4 intersection
points and attempts to determine solid/outside alternation. Two independent
nested shells create ambiguous solid-ordering — especially where both bottom
caps overlap at the y=0 plane and the two pole vertices coincide at the
origin (0,0,0).

```
Tet edge crossing two shells:
  outside → skin_enter → solid → skin_exit → gap → deepbed_enter → solid → deepbed_exit

The algorithm expects a SINGLE connected solid, not nested independent shells.
The coincident bottom-cap geometry at y=0 makes intersection ordering ambiguous.
```

**Diagnosis log** (scene loading stops here):
```
makeFirstVnTets: getConnectedComponents (tetTriVec.size=969)
<-- crash: Solid ordering error in getConnectedComponents()
```

**Solution:** Convert the two shells into a **single closed manifold** by:

1. **Remove bottom caps** — delete the 24 skin fan faces (mat 1) and 20 deep bed
   fan faces (mat 7), plus the two pole vertices (v386 at origin, v628 at origin).
   This opens both domes at the bottom rim.

2. **Reverse deep bed face winding** — the deep bed is the inner surface of the
   tissue volume. For a consistent closed manifold, its normals must point inward
   (toward the body center), which is the opposite of the original outward winding.
   Reverse each face's vertex order: `f a/a b/b c/c` → `f a/a c/c b/b`.

3. **Add connecting boundary strip** — stitch the skin rim (24 vertices, radius
   ~10/6) to the deep bed rim (20 vertices, radius ~8.5/4.5) with triangulated
   faces using angle-based vertex matching. Label these as material 1 (boundary).

4. **Reassign periosteum** — with the bottom fan removed, designate some deep bed
   faces near the apex (top 1-2 rings) as material 7 (periosteum) for fixed
   physics anchoring.

```
Phase 3a fix (CORRECT):

  ╭──── skin (mat 2) ──────────╮     Open dome (no bottom cap)
  │                              │
  ├── boundary strip (mat 1) ──┤     Connecting strip rim-to-rim
  │  (skin rim ↔ deep bed rim) │     ~44 triangles stitching 24↔20 verts
  │                              │
  │  periosteum (mat 7) apex    │     Top ring(s) of deep bed
  ├── deep bed (mat 5) ────────┤     Reversed winding (inward normals)
  ╰──────────────────────────────╯
  Single closed manifold, Euler=2, 1 connected component
```

**Validation requirements after fix:**
- Connected components = 1 (single manifold)
- Euler characteristic V-E+F = 2 (closed surface, genus 0)
- Boundary edges = 0 (every edge shared by exactly 2 faces)
- Consistent winding verified by `validate_obj.py`

---

## 4. Multi-Layer OBJ Structure

### Material ID Assignment

The OBJ file uses `usemtl <id>` directives to assign tissue types to face groups.
All layers share a single vertex pool:

```
# Merged multi-layer OBJ structure
v ...          ← skin vertices (1 to N_skin)
v ...          ← deep bed vertices (N_skin+1 to N_total)
vt ...         ← texture coordinates (same ordering)

usemtl 1       ← boundary faces (edge anchors)
f ...

usemtl 2       ← skin surface faces (surgical layer)
f ...

usemtl 5       ← deep bed faces (undermining layer)
f ...

usemtl 7       ← periosteum faces (fixed anchors)
f ...
```

### Required vs. Optional Materials

| ID | Name | Required? | Purpose |
|----|------|-----------|---------|
| 1 | boundary | **Yes** | `fixPeriostealPeriferalVertices()` sets peripheral anchors |
| 2 | skinSurface | **Yes** | The layer users interact with (incisions, hooks) |
| 3 | incisionEdge | No (runtime) | Created dynamically during `skinCut()` |
| 4 | subcutaneous | No (runtime) | Created dynamically during `skinCut()` |
| 5 | deepBed | **Yes** | Flap bottom topology for `topDeepSplit()` |
| 6 | muscle | No | Intermediate tissue layer |
| 7 | periosteum | **Yes** | `fixPeriostealPeriferalVertices()` sets fixed anchors |
| 8 | periosteumUndermined | No | Periosteum after undermining |
| 10 | undermineMarker | No | Marks undermined boundaries |

**Minimum viable model:** Materials 1, 2, 5, 7 must be present in the OBJ.

### Critical: Single Manifold Requirement

All faces in the dynamic OBJ **must form one connected component**. The BCC
tet cutter's `getConnectedComponents()` assumes a single connected surface
when determining solid/outside regions. Two or more disconnected shells —
even if they contain all required materials — will cause a `Solid ordering
error` crash.

```
WRONG: Two disconnected shells          CORRECT: Single connected manifold
(each shell closed independently)       (all faces edge-connected)

  ╭── skin ──╮                            ╭── skin ──╮
  │          │   ← no shared edges        │          │
  │ ╭─bed─╮ │                             ├─boundary─┤   ← shared edges
  │ ╰─────╯ │                             │          │
  ╰──────────╯                            ╰── bed ───╯
  2 components → CRASH                    1 component → OK
```

**How to verify:** Run a connected-component analysis on the face adjacency
graph. Every face must be reachable from any other face by traversing shared
edges. The Euler characteristic should be V-E+F = 2 for a closed genus-0
surface.

### How Layers Connect to Physics

```
fixPeriostealPeriferalVertices() in bccTetScene.cpp:
  ┌─────────────────────────────────────────────┐
  │ Scan all triangles:                         │
  │   mat == periosteum (7)  → fixedTets[]      │  ← immovable nodes
  │   mat == boundary (1)    → peripheralTets[] │  ← soft-constrained nodes
  │                                              │
  │ Call _ptp.setFixedVertices(                  │
  │     fixedTets, fixedWeights, fixedPos,       │
  │     peripheralTets, peripheralWeights, ...)  │
  └─────────────────────────────────────────────┘

If both arrays are empty → solver has no constraints → CRASH
```

### Facial Model Reference

The working facial OBJ files demonstrate the expected multi-layer structure:

```
unilatCompleteCleft_3.obj:
  usemtl 1  →    425 faces (boundary)
  usemtl 2  → 15,299 faces (skin surface)
  usemtl 7  →  1,654 faces (periosteum)
  Total: 8,691 shared vertices, 17,378 faces
```

---

## 5. Step-by-Step: Adding a New Anatomy Model

### Prerequisites

- Python 3.6+ (for merge tools and tests)
- Existing skin surface OBJ with correct winding (outward-facing normals)
- Deep bed OBJ representing the tissue layer below skin
- `.bed` file mapping skin vertices to deep bed positions

### Procedure

#### Step 1: Prepare OBJ Files

Create separate OBJ files for each tissue layer:

```bash
# Example file structure
Model/
  NewSkin.obj          # Material 2 (skin surface)
  NewDeepBed.obj       # Material 5 (deep bed)
  NewSkin.bed           # Closest-point projection from skin to deep bed
```

**OBJ requirements:**
- Triangular faces only (no quads)
- Consistent outward winding (validate with `tests/validate_obj.py`)
- Vertex/texcoord format: `f vi/ti vi/ti vi/ti`

#### Step 2: Merge into Single-Manifold Multi-Layer OBJ

Use the merge tool or create a custom script:

```bash
python3 tools/merge_shoulder_layers.py
```

The merge produces a **single closed manifold** (not two separate shells):
1. Reads skin OBJ (material 2) and deep bed OBJ (material 5)
2. Removes bottom caps (fan faces around pole vertices) from both
3. Reverses deep bed face winding (inner surface normals must point inward)
4. Creates boundary strip (material 1) connecting skin rim to deep bed rim
5. Relabels deep bed apex faces as periosteum (material 7)
6. Outputs a single connected OBJ with all layers edge-connected

**Validation after merge:**
```bash
# Must report: 1 connected component, Euler=2, 0 boundary edges
python3 -c "... connected-component analysis ..."
```

**For non-dome geometries**, identify boundary and periosteum faces manually:
- **Boundary (mat 1):** Faces that bridge the skin and deep bed layers at the rim
- **Periosteum (mat 7):** Deep bed faces adjacent to bone or immovable structures
- **Critical:** All layers must be edge-connected into one manifold

#### Step 3: Create the .bed File

The `.bed` file maps each skin vertex to its corresponding deep bed position.
Format: one line per skin vertex.

```
vertex_index x y z
0 1.234567 2.345678 3.456789
1 1.345678 2.456789 3.567890
...
```

**Generation method:** For each skin vertex, find the closest point on the
deep bed surface. The `tools/fix_obj_winding.py` script contains helper geometry
functions that can be adapted for closest-point projection.

#### Step 4: Write the .smd Scene File

```json
{
    "sceneName" : "NewAnatomyModel",
    "fragmentShader" : "shoulderFragmentShader.txt",
    "textureFiles" : {
        "diffuse.jpg" : 1,
        "normal.jpg" : 2
    },
    "dynamicObjects" : {
        "NewSkin.obj" : {
            "textureMaps": [1, 2, 1, 2]
        }
    },
    "tetrahedralProperties" : {
        "minStrain" : 0.7,
        "maxStrain" : 1.4,
        "lowTetWeight" : 300.0,
        "highTetWeight" : 800.0,
        "nTetSizeLevels" : 2,
        "maxDimMegatetSubdivs" : 16
    },
    "materialLayers" : {
        "boundary" : 1,
        "skinSurface" : 2,
        "incisionEdge" : 3,
        "subcutaneous" : 4,
        "deepBed" : 5,
        "muscle" : 6,
        "periosteum" : 7,
        "periosteumUndermined" : 8,
        "undermineMarker" : 10
    },
    "fixedCollisionSets" : {
    }
}
```

**Anatomy auto-detection:** The `sceneName` field determines anatomy type.
Names containing "Shoulder" trigger shoulder-specific tool states.

#### Step 5: Validate

```bash
# Validate OBJ winding and structure
python3 tests/validate_obj.py Model/NewSkin.obj

# Run all tests
python3 -m pytest tests/ -v
```

**Validation checklist:**
- [ ] OBJ has materials 1, 2, 5, 7 (minimum)
- [ ] **Single connected component** (all faces reachable via shared edges)
- [ ] **Euler characteristic V-E+F = 2** (closed manifold, genus 0)
- [ ] **Zero boundary edges** (every edge shared by exactly 2 faces)
- [ ] Consistent face winding (outward on skin, inward on deep bed)
- [ ] All face vertex indices are in range
- [ ] No degenerate faces (duplicate vertex indices)
- [ ] `.bed` entry count matches skin vertex count
- [ ] `.bed` coordinates are inside the OBJ bounding box
- [ ] `.smd` JSON is valid and references existing files
- [ ] `nTetSizeLevels >= 2` for topology operations
- [ ] `maxDimMegatetSubdivs >= 16` for adequate lattice resolution

#### Step 6: Test with Simulator

1. Load the model via File → Open Scene
2. **Hook test:** Click skin surface with hook tool → physics solver should
   initialize without errors
3. **Knife test:** Draw an incision line → flap should separate with
   visible top and bottom surfaces

---

## 6. Lattice Configuration

The tetrahedral lattice determines the physics simulation resolution.

### Key Parameters

| Parameter | Description | Minimum | Recommended |
|-----------|-------------|---------|-------------|
| `nTetSizeLevels` | Number of subdivision levels below megatets | 2 | 2–4 |
| `maxDimMegatetSubdivs` | Divisions along longest dimension | 16 | 16–31 |

### How Resolution Affects Operations

```
nTetSizeLevels = 1 (megatets only):
  ┌───────────────────┐
  │                   │  Very coarse. topDeepSplit() may fail.
  │    Single tet     │  vnCentroids could be 0.
  │                   │
  └───────────────────┘

nTetSizeLevels = 2 (one subdivision):
  ┌─────────┬─────────┐
  │  sub-   │  sub-   │  Fine enough for basic incisions.
  │  tet    │  tet    │  Adequate for most prototypes.
  ├─────────┼─────────┤
  │  sub-   │  sub-   │
  │  tet    │  tet    │
  └─────────┴─────────┘

nTetSizeLevels = 4 (production):
  ┌──┬──┬──┬──┬──┬──┬──┬──┐
  │  │  │  │  │  │  │  │  │  High resolution for complex surgery.
  ├──┼──┼──┼──┼──┼──┼──┼──┤  Used by facial model (620K tets
  │  │  │  │  │  │  │  │  │  at finest level).
  └──┴──┴──┴──┴──┴──┴──┴──┘
```

### Trade-offs

- **Higher resolution:** More accurate physics, better incision detail, but
  slower computation and more memory usage
- **Lower resolution:** Faster but may fail on topology operations
- Start with `nTetSizeLevels=2` for prototyping, increase as needed

---

## 7. Glossary

| Term | Definition |
|------|-----------|
| **materialTriangles** | The core mesh data structure holding all triangle faces with material IDs. Only dynamic objects contribute to this. |
| **Material ID** | Integer assigned to each triangle face identifying its tissue type. Stored as `usemtl <id>` in OBJ files. |
| **Dynamic object** | An OBJ loaded into `materialTriangles` — participates in physics, incisions, and collision. |
| **Static object** | An OBJ rendered on GPU only — visual decoration, does NOT participate in physics or incisions. |
| **BCC lattice** | Body-Centered Cubic tetrahedral grid that discretizes the space around the mesh for physics simulation. |
| **Megatet** | The coarsest-level tetrahedron in the multi-resolution BCC lattice. Subdivided into smaller tets based on `nTetSizeLevels`. |
| **Deep bed** | The tissue surface below the skin layer. During undermining, the skin flap separates from this surface. |
| **Periosteum** | The membrane covering bone. In physics, periosteum vertices are fixed (immovable) anchor points. |
| **Boundary** | Edge triangles of the surgical field. In physics, boundary vertices are peripherally constrained (soft anchors). |
| **`.bed` file** | Text file mapping each skin vertex index to its corresponding 3D position on the deep bed surface. |
| **`.smd` file** | Scene Model Definition — JSON file describing the complete surgical scene (objects, textures, physics parameters, material layers). |
| **Projective Dynamics** | The physics solver algorithm used by the simulator. Requires fixed/constrained vertices to produce a well-posed system. |
| **`topDeepSplit()`** | Core function that splits mesh topology to create a flap with separate top (skin) and bottom (deep bed) surfaces during incision. |
| **`fixPeriostealPeriferalVertices()`** | Initialization function that scans all triangles for boundary (mat 1) and periosteum (mat 7) to establish physics anchor points. |
| **Closed manifold** | A surface mesh with no boundary edges where every edge is shared by exactly 2 faces. Required by the BCC tet cutter for solid-region determination. Euler characteristic V-E+F = 2 for genus 0. |
| **Connected component** | A maximal set of faces where any face can be reached from any other by traversing shared edges. The dynamic OBJ must have exactly 1 connected component. |
| **`getConnectedComponents()`** | BCC tet cutter function that splits triangles within each tetrahedron into solid-connected patches. Fails with "Solid ordering error" if the mesh has multiple disconnected shells. |
| **Face winding** | The vertex ordering of a triangle face, which determines the surface normal direction (right-hand rule). In a closed manifold, outward-facing normals point away from the enclosed solid volume. |

---

## 8. FAQ

### Q: Why did the single-layer ShoulderSkin.obj crash on hook/knife?

The physics solver (Projective Dynamics) needs constrained vertices to produce
a valid solution. `fixPeriostealPeriferalVertices()` scans for material 1
(boundary) and material 7 (periosteum) triangles to set these constraints.
With only material 2 (skin), both arrays were empty, making the stiffness
matrix singular.

For knife operations, `createFlapTopBottomVertices()` needs a deep bed surface
(material 5) to create the bottom layer of a skin flap. Without it, the
incision topology operations fail.

### Q: Can I load the deep bed as a separate static object?

No. Static objects are sent to the GPU for rendering only. They are never
added to `materialTriangles` (`_mt`), which is the data structure used by the
incision system, physics solver, and collision detection. The deep bed
geometry **must** be part of the same dynamic OBJ file as the skin surface.

### Q: How do I write a `.smd` file from scratch?

See [FILE_FORMATS.md](FILE_FORMATS.md) for the full JSON schema. The minimum
required sections are:
- `sceneName` — determines anatomy type
- `dynamicObjects` — the multi-layer OBJ file
- `tetrahedralProperties` — physics lattice parameters
- `materialLayers` — maps tissue type names to integer IDs

If `materialLayers` is omitted, the facial model defaults are used automatically.

### Q: What happens if I change the material ID values?

The IDs are arbitrary integers — what matters is consistency between the OBJ
file's `usemtl` directives and the `.smd` file's `materialLayers` mapping.
The code uses predicates like `isSkinSurface(mat)` that compare against the
configured value, not hardcoded numbers.

**Important:** All core IDs must be positive and unique. The system validates
this at scene load via `validateScene()`.

### Q: How do I determine which faces should be boundary vs. periosteum?

- **Boundary (mat 1):** Faces at the edge/rim of the surgical field. These are
  softly constrained — they can move slightly but resist displacement. Typically
  the outermost ring of the mesh.
- **Periosteum (mat 7):** Faces at the bone surface or deepest tissue layer.
  These are rigidly fixed — they do not move at all during simulation. Typically
  the central/deepest region of the mesh.

For dome-shaped meshes:
- **Boundary (mat 1):** The strip of faces connecting the skin rim to the
  deep bed rim (bridges the two layers at the surgical field edge).
- **Periosteum (mat 7):** The top ring(s) of the deep bed dome near the apex
  (closest to bone, serves as fixed reference).

**Warning:** Do NOT use bottom fan caps as boundary/periosteum — this creates
disconnected shells. Instead, boundary faces must physically connect the two
layers via shared edges.

### Q: Why did the multi-layer merge still crash with "Solid ordering error"?

The initial merge approach (Phase 3) simply stacked two OBJ files together —
skin dome + deep bed dome — without connecting them. This created two
independent closed shells (each with Euler characteristic 2). The BCC tet
cutter's `getConnectedComponents()` assumes a single connected surface and
cannot handle nested independent shells.

**Diagnostic clue:** The debug log stops at:
```
makeFirstVnTets: getConnectedComponents (tetTriVec.size=969)
```

**Fix:** The two shells must be joined into a single manifold by:
1. Removing bottom caps (opening both domes)
2. Reversing deep bed face winding (inner surface normals inward)
3. Adding a boundary strip connecting the two rims
4. Relocating periosteum faces to the deep bed apex

See [Phase 3a: Disconnected Shells Fix](#phase-3a-disconnected-shells-fix)
for the full solution.

### Q: How do I verify my OBJ is a single manifold?

Run connected-component analysis on the face adjacency graph. Check:
- **Components = 1** (single connected mesh)
- **Euler V-E+F = 2** (closed surface, no holes)
- **Boundary edges = 0** (every edge shared by exactly 2 faces)

If components > 1, the two layers are disconnected and need a boundary
strip to connect them.

### Q: Can I extend this to other body parts (arm, leg, knee)?

Yes. The system is fully configurable through `.smd` files. Follow the
5-step procedure in Section 5 above. The shoulder extension fields (tendon,
jointCapsule, boneSurface, arthroscopicPortal) demonstrate how to add
anatomy-specific material types beyond the core facial set.

---

*Document version: 2026-02-12 v2. Covers materialLayerConfig refactoring (Phase 1),
configurable .smd loading (Phase 2), multi-layer OBJ merge (Phase 3), and
disconnected shells fix (Phase 3a).*
