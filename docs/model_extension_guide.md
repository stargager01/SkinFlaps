# Model Extension Guide

How to create and extend surgical simulation models for the SkinFlaps simulator.
This guide documents the improvement process from hardcoded facial-only support
to a configurable multi-anatomy system, and provides a step-by-step procedure
for adding new anatomical models.

**Related documentation:**
- [FILE_FORMATS.md](FILE_FORMATS.md) — `.smd` and `.hst` JSON schema reference
- [shoulder_surgery_guide.md](shoulder_surgery_guide.md) — Shoulder model details
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

### Phase 3: Material Region Assignment

**Problem:** ShoulderMinimal's `ShoulderSkin.obj` originally had only material 2
(skin surface). Hook/knife operations crashed because the physics solver had no
fixed vertices (no boundary or periosteum faces).

**Solution:** Assign material regions to the existing single-shell dome OBJ,
matching the facial model architecture:

**Before (single-layer, broken):**
```
ShoulderSkin.obj: 386 verts, 768 faces, usemtl 2 only
```

**After (material regions assigned, working):**
```
ShoulderSkin.obj: 386 verts, 768 faces
  usemtl 1 →  24 faces (boundary: bottom fan at y=0 → peripheral anchors)
  usemtl 2 → 720 faces (skin surface: main body)
  usemtl 7 →  24 faces (periosteum: top fan near apex → fixed anchors)
```

**Deep bed:** Defined via `ShoulderSkin.bed` (386 entries mapping each skin
vertex to its deep bed position), NOT as OBJ faces. Material 5 is created
at runtime during undermining/deep cuts — identical to the facial model.

**Key insight:** The facial model `unilatCompleteCleft.obj` also has ONLY
materials {1, 2, 7} in the OBJ. Material 5 is never stored in the OBJ file.

**Lattice resolution** also increased (`nTetSizeLevels: 1→2`, `maxDimMegatetSubdivs: 10→16`)
to provide sub-megatet tetrahedra needed for topology operations.

---

### Phase 3a: Why Embedding Deep Bed in OBJ Fails

During development, an approach was attempted to merge the deep bed geometry
directly into the OBJ as material 5 faces. This created a dual-shell OBJ
(skin dome + deep bed dome) that crashed the BCC lattice builder.

**Root cause:** Two disconnected closed shells nested inside each other —
the BCC tet cutter's `getConnectedComponents()` assumes a single connected
surface. Two independent shells create ambiguous solid-ordering.

```
BROKEN: Two disconnected shells

  ╭─── skin shell (mat 1+2) ────╮     Shell 1: closed sphere
  │                              │     ← no connection
  │  ╭── deep bed shell ──╮     │     Shell 2: closed sphere
  │  │  (mat 5+7)         │     │     ← no connection
  │  ╰────────────────────╯     │     Shared vertices: 0
  ╰──────────────────────────────╯     → "Solid ordering error" crash
```

**Lesson learned:** Dynamic OBJ files must be a single closed surface with
materials {1, 2, 7} only. Deep bed is always defined via `.bed` file and
material 5 is assigned at runtime during cutting operations. This matches
the proven facial model architecture.

**Validation requirements for any dynamic OBJ:**
- Connected components = 1 (single manifold)
- Euler characteristic V-E+F = 2 (closed surface, genus 0)
- Boundary edges = 0 (every edge shared by exactly 2 faces)
- Consistent winding verified by `validate_obj.py`
- Materials: only 1 (boundary), 2 (skin), 7 (periosteum)

---

## 4. Dynamic OBJ Structure

### Material ID Assignment

The dynamic OBJ file uses `usemtl <id>` directives to assign tissue types to
face groups. All faces share a single vertex pool:

```
# Dynamic OBJ structure (single closed manifold)
v ...          ← all vertices in a single shell
vt ...         ← texture coordinates

usemtl 1       ← boundary faces (peripheral anchors)
f ...

usemtl 2       ← skin surface faces (surgical layer)
f ...

usemtl 7       ← periosteum faces (fixed anchors)
f ...
```

### Materials in OBJ vs. Runtime

| ID | Name | In OBJ? | Purpose |
|----|------|---------|---------|
| 1 | boundary | **Yes** | `fixPeriostealPeriferalVertices()` sets peripheral anchors |
| 2 | skinSurface | **Yes** | The layer users interact with (incisions, hooks) |
| 3 | incisionEdge | No (runtime) | Created dynamically during `skinCut()` |
| 4 | subcutaneous | No (runtime) | Created dynamically during `skinCut()` |
| 5 | deepBed | **No (runtime via .bed)** | Created from `.bed` mapping during undermining/deep cuts |
| 6 | muscle | No (runtime) | Intermediate tissue layer |
| 7 | periosteum | **Yes** | `fixPeriostealPeriferalVertices()` sets fixed anchors |
| 8 | periosteumUndermined | No (runtime) | Periosteum after undermining |
| 10 | undermineMarker | No (runtime) | Marks undermined boundaries |

**Minimum viable model:** Materials 1, 2, 7 must be present in the OBJ.
Material 5 (deep bed) is defined via the `.bed` file and assigned at runtime.

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

### Model Reference: Facial vs. ShoulderMinimal

Both models follow the same single-shell architecture with materials {1, 2, 7}
in the OBJ and deep bed defined via `.bed` file:

| Property | Facial (unilatCompleteCleft.obj) | Shoulder (ShoulderSkin.obj) |
|----------|----------------------------------|---------------------------|
| Vertices | 8,691 | 386 |
| Total faces | 17,378 | 768 |
| Material 1 (boundary) | 425 faces | 24 faces |
| Material 2 (skin) | 15,299 faces | 720 faces |
| Material 7 (periosteum) | 1,654 faces | 24 faces |
| Material 5 in OBJ | **No** | **No** |
| Deep bed source | `.bed` file | `.bed` file (386 entries) |
| Deep bed reference OBJ | `unilatCompleteCleft_deepBed.obj` | `ShoulderDeepBed.obj` |
| Scene file | `FacialFlaps.smd` | `ShoulderMinimal.smd` |
| Lattice: nTetSizeLevels | 4 | 2 |
| Lattice: maxDimMegatetSubdivs | 31 | 16 |

---

## 5. Step-by-Step: Adding a New Anatomy Model

### Prerequisites

- Python 3.6+ (for merge tools and tests)
- Existing skin surface OBJ with correct winding (outward-facing normals)
- Deep bed OBJ representing the tissue layer below skin
- `.bed` file mapping skin vertices to deep bed positions

### Procedure

#### Step 1: Prepare OBJ Files

Create the skin surface OBJ and a reference deep bed OBJ (for `.bed` generation):

```bash
# Example file structure
Model/
  NewSkin.obj          # Materials 1, 2, 7 (single closed manifold)
  NewDeepBed.obj       # Reference only (for .bed generation, not loaded at runtime)
  NewSkin.bed          # Closest-point projection from skin vertices to deep bed
```

**OBJ requirements:**
- Triangular faces only (no quads)
- Consistent outward winding (validate with `tests/validate_obj.py`)
- Vertex/texcoord format: `f vi/ti vi/ti vi/ti`

#### Step 2: Assign Material Regions to OBJ

Assign boundary (mat 1), skin (mat 2), and periosteum (mat 7) regions to the
single-shell OBJ. Use the merge tool or assign manually:

```bash
python3 tools/merge_shoulder_layers.py
```

The tool assigns material regions to a single closed manifold:
1. **Boundary (mat 1):** Faces at the edge/rim of the surgical field (peripheral anchors)
2. **Skin surface (mat 2):** Main body faces (user interaction layer)
3. **Periosteum (mat 7):** Faces near bone/immovable structures (fixed anchors)

**Do NOT embed deep bed geometry in the OBJ.** Material 5 is created at runtime
from the `.bed` file mapping. Embedding deep bed faces creates disconnected shells
that crash the BCC tet cutter (see Phase 3a).

**Validation after assignment:**
```bash
python3 tests/validate_obj.py Model/NewSkin.obj
# Must report: 1 connected component, Euler=2, 0 boundary edges
```

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
- [ ] OBJ has materials 1, 2, 7 (minimum) — **NO material 5 in OBJ**
- [ ] **Single connected component** (all faces reachable via shared edges)
- [ ] **Euler characteristic V-E+F = 2** (closed manifold, genus 0)
- [ ] **Zero boundary edges** (every edge shared by exactly 2 faces)
- [ ] Consistent face winding (outward-facing normals)
- [ ] All face vertex indices are in range
- [ ] No degenerate faces (duplicate vertex indices)
- [ ] `.bed` entry count matches OBJ vertex count
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

For knife operations, `createFlapTopBottomVertices()` needs deep bed data
(from the `.bed` file) to create material 5 faces at runtime for the bottom
layer of a skin flap. Without a `.bed` file, the incision topology operations fail.

### Q: How does the deep bed work if it's not in the OBJ?

The deep bed is defined via the `.bed` file, which maps each skin vertex to
its corresponding deep bed 3D position. During undermining and deep cut
operations, the system creates material 5 (deep bed) faces at runtime using
these positions. This is the same mechanism used by the facial model.

The deep bed reference OBJ (e.g., `ShoulderDeepBed.obj`) is used only during
`.bed` file generation via closest-point projection. It is NOT loaded by the
simulator at runtime.

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

*Document version: 2026-02-12 v3. Covers materialLayerConfig refactoring (Phase 1),
configurable .smd loading (Phase 2), material region assignment (Phase 3), and
single-shell architecture rule. Updated to reflect that material 5 (deep bed)
is runtime-assigned via .bed file, never stored in OBJ files.*
