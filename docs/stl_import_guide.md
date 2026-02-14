# STL Import Guide

How to import external STL models into the SkinFlaps surgical simulator.

**Related documentation:**
- [model_extension_guide.md](model_extension_guide.md) — Adding new anatomy models
- [FILE_FORMATS.md](FILE_FORMATS.md) — `.smd` and `.hst` JSON schema reference
- [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) — Build environment setup

---

## Table of Contents

1. [Overview](#1-overview)
2. [Prerequisites](#2-prerequisites)
3. [Quick Start](#3-quick-start)
4. [Step-by-Step Workflow](#4-step-by-step-workflow)
5. [Command Reference](#5-command-reference)
6. [Material Assignment](#6-material-assignment)
7. [Deep Bed Configuration](#7-deep-bed-configuration)
8. [Troubleshooting](#8-troubleshooting)
9. [Mesh Simplification (Size Optimization)](#9-mesh-simplification-size-optimization)
10. [Limitations](#10-limitations)

---

## 1. Overview

SkinFlaps uses OBJ files internally for mesh representation. STL files (common
output from 3D scanners, CAD software, and medical imaging) must be converted
to a specific OBJ format before the simulator can load them.

**The conversion pipeline:**

```
STL file
  │
  ▼
convert_stl_to_obj.py    ← vertex dedup, UV synthesis, material assign
  │
  ▼
OBJ file ({1,2,7})       ← single closed manifold
  │
  ├─→ validate_obj.py    ← manifold, winding, Euler check
  │
  ▼
generate_bed.py           ← deep bed vertex mapping
  │
  ▼
.bed file
  │
  ▼
generate_smd.py           ← scene definition (physics params, layers)
  │
  ▼
.smd file
  │
  ├─→ quick_test.py --validate-smd
  │
  ▼
Ready for simulator
```

**Key principle:** The converter produces OBJ files that conform to the same
architecture as built-in models (unilatCompleteCleft.obj, ShoulderSkin.obj).
No C++ code changes are needed.

---

## 2. Prerequisites

### Software

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Python | 3.6+ | Converter and validation scripts |
| trimesh | 3.x+ | STL parsing, mesh repair, UV generation |
| numpy | 1.19+ | Geometry calculations |

Install dependencies:
```bash
pip install trimesh numpy
```

### STL File Requirements

Your STL file should be:
- **Watertight** (closed surface, no holes) — the converter can attempt repair
- **Single component** (one connected mesh, not multiple loose parts)
- **Reasonable size** (under 20,000 faces recommended; larger meshes may need decimation)

Both ASCII and binary STL formats are supported.

---

## 3. Quick Start

Minimal workflow to get an STL model running in the simulator:

```bash
# 1. Convert STL → OBJ (auto material assignment)
python3 tools/convert_stl_to_obj.py Model/MyModel.stl --material-mode auto

# 2. Validate the OBJ
python3 tests/validate_obj.py Model/MyModel.obj

# 3. Generate deep bed mapping
python3 tools/generate_bed.py Model/MyModel.obj --offset -5.0

# 4. Generate scene file
python3 tools/generate_smd.py Model/MyModel.obj --anatomy generic

# 5. Validate scene file
python3 scripts/quick_test.py --validate-smd Model/MyModel.smd

# 6. Load in simulator: File → Open Scene → MyModel.smd
```

---

## 4. Step-by-Step Workflow

### Step 1: Convert STL to OBJ

```bash
python3 tools/convert_stl_to_obj.py <input.stl> [options]
```

The converter performs these operations automatically:
1. Loads STL (ASCII or binary)
2. Removes degenerate faces (zero-area triangles)
3. Merges duplicate vertices (STL stores per-face vertices)
4. Repairs non-manifold geometry if possible
5. Unifies face normals (outward-facing)
6. Generates texture coordinates (UV)
7. Assigns material IDs
8. Writes OBJ with `s 1` smoothing group

**Output location:** Same directory as input, with `.obj` extension.

### Step 2: Validate the OBJ

```bash
python3 tests/validate_obj.py Model/MyModel.obj
```

The validator checks:
- Materials are only {1, 2, 7} (no material 5 in OBJ)
- Single connected component
- Euler characteristic V-E+F = 2 (closed manifold)
- Zero boundary edges
- Consistent face winding
- No degenerate faces

**If validation fails**, see [Troubleshooting](#8-troubleshooting).

### Step 3: Generate Deep Bed Mapping

The deep bed (material 5) is NOT stored in the OBJ. Instead, a `.bed` file
maps each skin vertex to a point on the underlying tissue surface.

**Option A: Offset-based (no reference OBJ needed)**
```bash
python3 tools/generate_bed.py Model/MyModel.obj --offset -5.0
```
Projects each vertex inward along its normal by the specified distance (mm).

**Option B: Reference OBJ-based (more anatomically accurate)**
```bash
python3 tools/generate_bed.py Model/MyModel.obj --reference-obj Model/MyDeepBed.obj
```
Uses KD-tree closest-point projection from skin vertices to the deep bed surface.

### Step 4: Generate Scene File (.smd)

```bash
python3 tools/generate_smd.py Model/MyModel.obj --anatomy generic
```

Creates a `.smd` JSON file with:
- Reference to the OBJ and texture files
- Default physics parameters (strain limits, weights)
- Material layer mapping (all 13 fields)

**Anatomy presets:**
- `generic` — balanced defaults for arbitrary models
- `facial` — matches unilatCompleteCleft parameters
- `shoulder` — matches ShoulderMinimal parameters

### Step 5: Validate and Load

```bash
# Validate scene definition
python3 scripts/quick_test.py --validate-smd Model/MyModel.smd

# Validate STL source (optional, pre-conversion check)
python3 scripts/quick_test.py --validate-stl Model/MyModel.stl
```

Load in the simulator via File → Open Scene → select your `.smd` file.

---

## 5. Command Reference

### convert_stl_to_obj.py

```
Usage: python3 tools/convert_stl_to_obj.py <input.stl> [options]

Options:
  --output PATH          Output OBJ path (default: input with .obj extension)
  --uv-method METHOD     UV generation: planar|spherical|cylindrical (default: planar)
  --material-mode MODE   Material assignment: manual|auto|interactive (default: manual)
  --decimate N           Reduce face count to N faces (quadric decimation)
  --simplify-ratio R     Keep ratio R of faces (0.1~1.0, default: 1.0 = no reduction)
  --fix-normals          Attempt to unify face normals (default: enabled)
  --no-fix-normals       Skip normal unification
  --verbose              Print detailed conversion log
```

**UV methods explained:**

| Method | Best for | Seam risk | Distortion |
|--------|----------|-----------|------------|
| `planar` (default) | Flat/dome shapes | None | High at edges |
| `spherical` | Roughly spherical models | 1 seam line | Low for spheres |
| `cylindrical` | Elongated shapes | 1 seam line | Low for cylinders |

**Note:** SkinFlaps uses textures for visual display only (not physics). Planar
projection is the safest default — seam artifacts are cosmetic, not functional.

### generate_bed.py

```
Usage: python3 tools/generate_bed.py <skin.obj> [options]

Options:
  --reference-obj PATH   Deep bed reference OBJ for closest-point projection
  --offset FLOAT         Normal-based offset distance in mm (default: -5.0)
  --output PATH          Output .bed path (default: input with .bed extension)
```

### generate_smd.py

```
Usage: python3 tools/generate_smd.py <skin.obj> [options]

Options:
  --anatomy TYPE         Parameter preset: generic|facial|shoulder (default: generic)
  --scene-name NAME      Scene name (default: derived from OBJ filename)
  --output PATH          Output .smd path (default: input with .smd extension)
```

---

## 6. Material Assignment

### Why Materials Matter

The physics solver requires three material types to function:

```
Material 1 (boundary)    → Peripheral face anchors → soft constraint (periferalWeight)
Material 2 (skin)        → Surgical interaction layer → user operates on this
Material 7 (periosteum)  → Fixed bone-surface anchors → rigid constraint (fixedWeight)
```

**Without materials 1 and 7:** `fixPeriostealPeriferalVertices()` finds no
anchor faces → solver stiffness matrix is singular → crash.

### Manual Assignment

With `--material-mode manual`, the converter assigns `usemtl 2` to all faces.
You then edit the OBJ to reassign boundary and periosteum faces.

**Guidelines for manual assignment:**
- **Boundary (mat 1):** Outermost ring of faces at the surgical field edge.
  These faces should form a band around the perimeter.
- **Skin (mat 2):** The main body of the mesh. This is the layer users interact
  with (incisions, hooks, sutures).
- **Periosteum (mat 7):** Faces at the deepest/most fixed region (closest to
  bone or immovable structure). Typically a small cluster.

**Minimum counts:** At least 6 faces each for materials 1 and 7.

### Auto Assignment (`--material-mode auto`)

The auto-assigner uses geometry heuristics:
1. Compute bounding box of the mesh
2. **Boundary (mat 1):** Faces with centroids within 5% of the bounding box
   perimeter (outermost ring)
3. **Periosteum (mat 7):** Faces with centroids in the bottom 10% along the
   primary axis (deepest region)
4. **Skin (mat 2):** All remaining faces

**When auto-assign works well:** Dome-shaped or roughly convex meshes.
**When to use manual:** Complex shapes, concave regions, or specific anatomical
knowledge about tissue layers.

---

## 7. Deep Bed Configuration

### What Is the Deep Bed?

The deep bed is the tissue surface beneath the skin layer. During incisions,
the simulator creates a skin flap with:
- Top surface = original skin (material 2)
- Bottom surface = deep bed (material 5, created at runtime from `.bed` data)

### .bed File Format

Plain text, one line per skin vertex:
```
vertex_index x y z
0 1.234567 2.345678 3.456789
1 1.345678 2.456789 3.567890
...
```

**Critical rule:** The number of `.bed` entries MUST equal the number of vertices
in the OBJ file. A mismatch causes `setDeepBed()` to fail.

### Offset vs. Reference OBJ

| Method | Accuracy | Difficulty | When to use |
|--------|----------|------------|-------------|
| `--offset -5.0` | Approximate | Easy | Prototyping, no anatomical deep bed data |
| `--reference-obj` | Anatomically accurate | Requires deep bed mesh | Production models with known tissue layers |

**Offset method:** Each skin vertex is projected inward along its averaged
vertex normal by the specified distance. Positive values project outward,
negative values project inward (toward the body interior).

---

## 8. Troubleshooting

### Conversion Errors

| Error | Cause | Fix |
|-------|-------|-----|
| "STL is not watertight" | Holes in the mesh | Run `tools/fix_stl_manifold.py` or repair in MeshLab |
| "Multiple connected components" | Loose parts in STL | Keep only the largest component, or merge in 3D software |
| "Non-manifold edges detected" | Edge shared by >2 faces | Run `tools/fix_stl_manifold.py` |
| "Too many faces (N > 20000)" | High-resolution scan | Use `--decimate 15000` to reduce |

### Validation Failures (validate_obj.py)

| Failure | Cause | Fix |
|---------|-------|-----|
| "Materials not in {1,2,7}" | Wrong material IDs | Re-run converter or fix `usemtl` lines manually |
| "Euler V-E+F != 2" | Not a closed manifold | Check for holes; re-run with manifold repair |
| "Boundary edges > 0" | Open edges | Mesh has holes; needs repair before conversion |
| "Inconsistent winding" | Mixed face orientations | Run `tools/fix_obj_winding.py Model/MyModel.obj` |
| "Multiple components" | Disconnected mesh parts | Merge or keep largest component |

### Simulator Errors

| Error | Cause | Fix |
|-------|-------|-----|
| "Solid ordering error" in BCC | Multiple shells in OBJ | Ensure single connected component (see validate_obj.py) |
| Singular matrix in physics | Missing mat 1 or mat 7 | Re-assign materials; need both boundary and periosteum |
| `setDeepBed()` crash | .bed vertex count mismatch | Regenerate .bed file after any OBJ vertex changes |
| Hook tool crash | No fixed vertices | Ensure mat 7 (periosteum) faces exist |
| Knife tool crash | No deep bed data | Generate and verify .bed file |

### STL Quality Issues

| Issue | Detection | Fix |
|-------|-----------|-----|
| Inverted normals | `trimesh.is_winding_consistent` = False | `--fix-normals` (default enabled) |
| Degenerate triangles | Zero-area faces | Automatic removal during conversion |
| Self-intersecting faces | `trimesh.is_volume` = False | Repair in MeshLab or Blender |
| Bowtie vertices | Non-manifold vertex | `fix_stl_manifold.py` splits bowtie vertices |

---

## 9. Mesh Simplification (Size Optimization)

### Why Simplify?

DICOM-extracted STL files often have excessive face counts (100K+), causing slow
BCC lattice generation and large memory usage. The `--simplify-ratio` option
reduces face count while preserving mesh topology.

### Usage

```bash
# Keep 50% of faces (recommended starting point)
python3 tools/convert_stl_to_obj.py Model/HighRes.stl --simplify-ratio 0.5

# Aggressive reduction (keep 20% — check quality afterward)
python3 tools/convert_stl_to_obj.py Model/HighRes.stl --simplify-ratio 0.2

# Combine with other options
python3 tools/convert_stl_to_obj.py Model/HighRes.stl \
    --simplify-ratio 0.3 --material-mode auto --uv-method spherical
```

### Recommended Ranges

| Face Count (original) | Recommended Ratio | Result |
|------------------------|-------------------|--------|
| < 5,000 | 1.0 (no reduction) | Already within simulator limits |
| 5,000 ~ 20,000 | 0.5 ~ 0.8 | Good balance of speed and quality |
| 20,000 ~ 100,000 | 0.2 ~ 0.5 | Significant speedup with acceptable quality |
| > 100,000 | 0.1 ~ 0.3 | Required for simulator performance |

### `--simplify-ratio` vs `--decimate`

| Option | Input | Example | When to use |
|--------|-------|---------|-------------|
| `--simplify-ratio 0.5` | Ratio (0.1~1.0) | Halves face count | When you don't know the face count |
| `--decimate 5000` | Absolute count | Exactly 5000 faces | When you need a specific face count |

If both are specified, `--simplify-ratio` takes precedence.

### Post-Simplification Validation

The converter automatically validates the mesh after simplification:
- **Watertight check**: Attempts repair if simplification creates holes
- **Euler characteristic**: Warns if topology changes (V-E+F != 2)
- **Degenerate faces**: Detects zero-area triangles from collapse
- **Excessive reduction**: Warns if >80% of faces were removed

Always validate the output OBJ after simplification:
```bash
python3 scripts/quick_test.py --validate-obj Model/HighRes.obj
```

### Troubleshooting Simplification

| Problem | Cause | Fix |
|---------|-------|-----|
| "Broke watertight property" | Decimation created holes | Use higher ratio (0.5+) or repair with `fix_stl_manifold.py` |
| "Material boundary lost" | Too aggressive reduction collapsed boundary faces | Use `--simplify-ratio >= 0.3` and `--material-mode auto` |
| "Euler characteristic changed" | Topology altered (handles/holes) | Use higher ratio; inspect in MeshLab |
| "Only N faces remaining" | Ratio too low for mesh size | Use higher ratio; ensure >=18 faces |
| Solver singular matrix | Boundary/periosteum faces lost | Re-run with higher ratio; check material distribution |

---

## 10. Limitations

### Current Limitations
- **No quad/polygon support in STL:** STL only has triangles (this is fine — SkinFlaps requires triangles)
- **Auto material assignment is heuristic:** Complex anatomies may need manual material assignment
- **No texture transfer:** STL has no texture data; UV coordinates are synthesized geometrically
- **Single dynamic OBJ per scene:** The simulator loads one dynamic OBJ file per `.smd` scene
- **Face count ceiling:** Very large meshes (>50K faces) may cause slow BCC lattice generation

### STL vs. Native OBJ Quality

| Aspect | Native OBJ | STL-converted OBJ |
|--------|------------|-------------------|
| Texture mapping | Artist-authored UVs | Synthesized (planar/spherical) |
| Material regions | Manually curated | Auto-assigned or manual post-edit |
| Mesh quality | Optimized for simulation | May need decimation |
| Deep bed | Anatomically designed | Offset-based or reference projection |

**Recommendation:** For production-quality models, use STL conversion as a
starting point, then refine material assignments and deep bed mapping manually.

---

*Document version: 2026-02-14 v1.0.0. Initial STL import pipeline guide.*
