# SkinFlaps Hardening Plan: Phase 0-4 Verification Fixes

Based on the comprehensive parallel audit of the codebase, this plan addresses **Top 10 Critical issues** plus **High-priority gaps** across 5 verification phases. Changes are grouped into 4 implementation batches ordered by severity and dependency.

---

## Batch 1: Input Validation Hardening (Phase 0 fixes)

### 1.1 OBJ Parser Bounds Checking
**File:** `gl3wGraphics/materialTriangles.cpp` (lines 85-141)
**What:** Add vertex/texture index bounds checking during `readObjFile()` parsing.
- After line 107 (`vIn[i-1][j] = atoi(str.c_str()) - 1`), validate:
  - Position index < `_xyz.size()`
  - Texture index < `_uv.size()`
  - All 3 vertex indices are distinct (reject degenerate `f 10/5 10/5 10/5`)
- Return new error code 7 for out-of-bounds indices
- Add degenerate triangle detection (zero-area) after face assembly (~line 120)

**Impact:** Prevents silent OOB access crashes downstream.

### 1.2 `.bed` File Robust Parsing
**File:** `SkinFlaps/src/skinCutUndermineTets.cpp` (lines 1018-1046)
**What:** Harden `setDeepBed()` with proper validation:
- Check `sscanf()` return value == 4; log and skip malformed lines
- Validate `topVert >= 0 && topVert < mt->numberOfVertices()`
- Validate coordinate components are finite (`std::isfinite()`)
- Replace `while (!istr.eof())` with `while (istr.getline(s, 399))`
- Add entry count warning if `_deepBed.size()` != expected vertex count
- Return `false` (fail scene load) if zero valid entries parsed

**Impact:** Eliminates silent parse failures and uninitialized data.

### 1.3 Scene Load Fail-on-Missing-Bed
**File:** `SkinFlaps/src/bccTetScene.cpp` (lines 474-477)
**What:** Change `.bed` file missing from warning-only to `return false`:
```cpp
if (!_surgAct->getDeepCutPtr()->setDeepBed(...)) {
    _surgAct->sendUserMessage("...", "Error Message");
    return false;  // ADD THIS
}
```
Also at lines 330-334: upgrade invalid strain range from warning to `return false`.

**Impact:** Prevents partially-initialized scenes from reaching physics solver.

### 1.4 Invoke `validateScene()` Automatically
**File:** `SkinFlaps/src/bccTetScene.cpp` (end of `loadScene()`, ~line 495)
**What:** Call `validateScene()` before `return true` in `loadScene()`. Currently it's only called if the user explicitly invokes it.

**Impact:** Catches duplicate material IDs, missing region files at load time.

---

## Batch 2: Grid/Numeric Safety (Phase 1 + Phase 4 fixes)

### 2.1 Short Integer Overflow Protection
**Files:**
- `vnBccTetrahedra.cpp:78-80` (centroidToNodeLoci)
- `vnBccTetCutter_tbb.cpp:540` (multi-res scaling)

**What:** Add overflow checks before `short × mult` operations:
```cpp
int mult = 1 << (nLevels - 1);
for (auto& nl : _nodeGridLoci) {
    for (int j = 0; j < 3; ++j) {
        int scaled = (int)nl[j] * mult;
        if (scaled > SHRT_MAX || scaled < SHRT_MIN)
            throw std::runtime_error("Grid coordinate overflow at multi-res level " + std::to_string(nLevels));
        nl[j] = (short)scaled;
    }
}
```
Same pattern in `centroidToNodeLoci()` for intermediate multiplication.

**Impact:** Converts silent data corruption to caught exception.

### 2.2 Parametric Tet Lookup: Use Actual Subdivision Levels
**File:** `vnBccTetrahedra.cpp:864`
**What:** Replace hardcoded `level > 16` with `level > _tetSubdivisionLevels + 2`:
```cpp
if (level > _tetSubdivisionLevels + 2)
    throw(std::logic_error("Surface point not embedded in existing tetrahedron."));
```

**Impact:** Correct limit for actual model, fails faster on impossible lookups.

### 2.3 Scale-Adaptive Tolerance Constants
**File:** `vnBccTetCutter_tbb.cpp:1753` and `vnBccTetrahedra.cpp:245`
**What:** Extract magic tolerances to named constants computed from grid scale:
- `sameHit`: Already `maxGridDim * 6e-4` (OK but add upper-bound clamp to 1.0)
- `barycentric eps`: Change from `1e-4f` to `_unitSpacing * 1e-4f` (scale-adaptive)
- Add static constexpr names: `kSameHitFraction = 6e-4`, `kBarycentricRelEps = 1e-4`

### 2.4 Document & Name Critical Magic Numbers
**Files:** Multiple (deepCut.cpp:1393, skinCutUndermineTets.cpp:538, tetCollisions.cpp:268)
**What:** For each scale-dependent magic number identified in Phase 4:
- `skinCutUndermineTets.cpp:538` — Extract `0.5f` "fudge factor" to `kPathLengthScale` with comment documenting facial-model origin
- `deepCut.cpp:1393` — Extract `1e-16` to `kDoubleHitTolerance`, computed from grid scale
- `tetCollisions.cpp:268,330` — Extract `1e-4f` to `kMinCollisionDepth`, `1e-6f` to `kMinBarycentricCoord`
- `tetCollisions.cpp:473` — Extract `0.02f` to `kDefaultRayDepthFraction`
- `tetCollisions.cpp:102` — Extract `0.75f` to `kRayDepthScale`

**Impact:** Self-documenting code; easier future shoulder-scale tuning.

---

## Batch 3: Shoulder Anatomy Adaptation (Phase 2 fixes)

### 3.1 Shoulder-Specific Default Tissue Properties
**File:** `SkinFlaps/src/bccTetScene.cpp` (~line 815-876 region defaults)
**What:** Add shoulder anatomy region defaults alongside facial ones:
- `shoulderTendon`: strainMin=0.85, strainMax=1.15 (tendons stretch ~10-15%)
- `shoulderCapsule`: strainMin=0.8, strainMax=1.25 (capsule moderate extensibility)
- `shoulderDeltoid`: strainMin=0.7, strainMax=1.3 (muscle)
- Guard: only apply when `_anatomyType == AnatomyType::SHOULDER`

### 3.2 Semi-Fixed Periosteum for Shoulder
**File:** `SkinFlaps/src/bccTetScene.cpp:704-708` (fixPeriostealPeriferalVertices)
**What:** For SHOULDER anatomy, use `periferalWeight` (soft constraint) instead of `fixedWeight` (Dirichlet) for periosteal vertices:
```cpp
if (_anatomyType == AnatomyType::SHOULDER)
    enterFixPoint(vIdx, true);   // peripheral = semi-fixed
else
    enterFixPoint(vIdx, false);  // facial = fully fixed
```

**Impact:** Allows humeral head to articulate instead of being rigidly locked.

### 3.3 Collision Depth Threshold Tuning
**File:** `tetCollisions.cpp:268,330`
**What:** Make the collision depth threshold (`1e-4f`) configurable via `tetrahedralProperties` in `.smd`:
- Add `"minCollisionDepth"` to JSON schema (default: `1e-4f`)
- Pass through `pdTetPhysicsProperties` to `tetCollisions`
- ShoulderMinimal.smd can override to `1e-3f` (1mm) for thicker joint capsule

---

## Batch 4: Performance & Thread Safety (Phase 3 fixes)

### 4.1 Collision Density Multiplier Synchronization
**File:** `SkinFlaps/src/tetCollisions.cpp:118-121`
**What:** Add `std::atomic<float>` or mutex protection for `_collisionDensityMultiplier`:
```cpp
std::atomic<float> _collisionDensityMultiplier{1.0f};
```
This is read by the physics thread and written by the GUI thread.

**Impact:** Eliminates data race between GUI and physics threads.

### 4.2 Reserve Before Post-Shrink Insertions
**File:** `vnBccTetCutter_tbb.cpp:156-157, 472-473, 808-809`
**What:** After each `shrink_to_fit()` sequence, add `reserve()` before subsequent `insert()`/`push_back()` calls with estimated size:
```cpp
_tetNodes.shrink_to_fit();
// ... later insertion code ...
_tetNodes.reserve(_tetNodes.size() + estimatedNewTets);
```

**Impact:** Prevents memory fragmentation from repeated reallocation.

### 4.3 O(n^2) Collision Detection — Document as Known Limitation
**File:** `tetCollisions.cpp:260-280, 312-342`
**What:** The O(n^2) ray-triangle pattern is a known hot path. Full BVH/spatial-hashing optimization is out of scope for this hardening pass. Instead:
- Add `// PERF: O(bedRays * flapTris) - spatial hashing would improve for large models` comments
- Add timing instrumentation (`std::chrono`) around the parallel_for blocks gated by `#ifdef PERF_TRACE`
- This creates a measured baseline for future optimization

---

## Testing Strategy

Each batch includes:
1. **Unit tests** in `tests/` for each new validation path (error codes, overflow detection, parse failures)
2. **Regression tests** ensuring existing facial model loads unchanged
3. **Shoulder model validation** with ShoulderMinimal.smd

Estimated new tests per batch:
- Batch 1: ~12 tests (OBJ malformed, .bed malformed, .smd missing sections)
- Batch 2: ~8 tests (overflow boundary, tolerance scaling, named constants)
- Batch 3: ~6 tests (shoulder region defaults, semi-fixed periosteum, collision depth)
- Batch 4: ~4 tests (atomic race check, reserve sizing, perf instrumentation)

**Total: ~30 new tests**

---

## Files Modified (Summary)

| File | Batches | Change Type |
|------|---------|-------------|
| `gl3wGraphics/materialTriangles.cpp` | 1 | Validation |
| `SkinFlaps/src/skinCutUndermineTets.cpp` | 1, 2 | Validation + constants |
| `SkinFlaps/src/bccTetScene.cpp` | 1, 3 | Fail-fast + shoulder defaults |
| `SkinFlaps/src/vnBccTetrahedra.cpp` | 2 | Overflow + tolerance |
| `SkinFlaps/src/vnBccTetCutter_tbb.cpp` | 2, 4 | Overflow + reserve |
| `SkinFlaps/src/tetCollisions.cpp` | 2, 3, 4 | Constants + config + atomic |
| `SkinFlaps/src/deepCut.cpp` | 2 | Named constants |
| `tests/` | 1-4 | ~30 new tests |

## Execution Order

Batch 1 -> Batch 2 -> Batch 3 -> Batch 4 (sequential, each depends on prior validation being in place)
