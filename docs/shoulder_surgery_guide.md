# Shoulder Surgery Simulation -- User Guide

## 1. Overview

The SkinFlaps shoulder surgery extension adds rotator cuff repair simulation to the existing facial surgery simulator. It introduces a shoulder anatomy model with deformable soft tissues (skin, muscle, tendon) over static bone structures (humerus, glenoid, acromion), three new surgical tools (suture anchor, arthroscope, tissue grasper), and a custom fragment shader that renders shoulder-specific tissue materials with procedural texturing.

The shoulder extension reuses the same Projective Dynamics physics engine, multi-resolution BCC tetrahedral lattice, and surgical history system as the facial simulator. The scene loader auto-detects the anatomy type from the `sceneName` field in the `.smd` file and configures material layers, tissue regions, and shaders accordingly.

---

## 2. Loading the Shoulder Model

1. Launch the SkinFlaps application.
2. Select **File > Load Scene** from the menu bar.
3. Navigate to the `Model/` directory and select `ShoulderPrototype.smd`.

The loader performs the following steps automatically:

- Parses the JSON scene descriptor (`ShoulderPrototype.smd`).
- Detects `AnatomyType::SHOULDER` from the `"sceneName": "ShoulderPrototype"` field (any scene name containing "Shoulder" or "shoulder" triggers this).
- Loads the dynamic skin object (`ShoulderSkin.obj`) and its associated deep bed file (`ShoulderSkin.bed`).
- Loads static bone collision objects (humerus, glenoid, acromion).
- Loads texture maps (`diffuse2.jpg`, `normal.jpg`).
- Selects the shoulder-specific fragment shader (`shoulderFragmentShader.txt`).
- Configures material layer IDs including shoulder extensions (tendon=11, jointCapsule=12, boneSurface=13).
- Creates the BCC tetrahedral lattice and applies tissue region subsets for deltoid muscle and supraspinatus tendon.
- Runs `validateScene()` to verify all referenced OBJ and texture files exist.

---

## 3. Anatomy Overview

The shoulder model consists of 7 OBJ files organized into three categories:

### Dynamic Object (Deformable)

| File | Description |
|------|-------------|
| `ShoulderSkin.obj` | Outer skin/deltoid surface. This is the primary deformable mesh embedded in the tetrahedral physics lattice. Texture-mapped with diffuse and normal maps. |

### Static Objects (Rigid Collision Bodies)

| File | Description |
|------|-------------|
| `ShoulderBone_humerus.obj` | Humeral head -- the ball of the ball-and-socket shoulder joint. Acts as a rigid collision surface. |
| `ShoulderBone_glenoid.obj` | Glenoid fossa -- the socket portion of the shoulder joint on the scapula. |
| `ShoulderBone_acromion.obj` | Acromion process -- the bony projection over the top of the shoulder joint. |

### Tetrahedral Subsets (Soft Tissue Regions)

| File | Description |
|------|-------------|
| `ShoulderMuscle_deltoid.obj` | Closed manifold defining the spatial extent of the deltoid muscle within the tetrahedral lattice. Tetrahedra inside this volume receive deltoid-specific strain limits and stiffness. |
| `ShoulderTendon_supraspinatus.obj` | Closed manifold defining the supraspinatus tendon region. Tetrahedra within this volume are assigned high stiffness and narrow strain limits to model the relatively inextensible tendon tissue. |

### Deep Bed Surface

| File | Description |
|------|-------------|
| `ShoulderDeepBed.obj` | Deep tissue bed surface used as the undermining reference plane. The associated `.bed` file (`ShoulderSkin.bed`) stores the precomputed mapping between skin surface vertices and their deep bed projections. |

---

## 4. Material Layers

The material layer system assigns integer IDs to different tissue types. The shader and surgical tools use these IDs to determine tissue appearance and behavior. The shoulder model uses the full set of standard layers plus three shoulder-specific extensions.

### Standard Material Layers

| ID | Name | Description |
|----|------|-------------|
| 1 | `boundary` | Blank/peripheral boundary material at mesh edges. |
| 2 | `skinSurface` | Top skin surface, texture-mapped with diffuse and normal maps. Shoulder skin is rendered slightly more tan than facial skin. |
| 3 | `incisionEdge` | Incised skin edge showing procedural dermis, dermal-fat junction, and subcutaneous fat layers. |
| 4 | `subcutaneous` | Flap underside / subcutaneous fat layer with procedural lobular fat texture. |
| 5 | `deepBed` | Deep tissue bed surface. In the shoulder model this represents the fascial plane, rendered as white/silvery connective tissue with a fibrous pattern. |
| 6 | `muscle` | Deep cut muscle layer. In the shoulder model this is the deltoid, rendered as bright red skeletal muscle with visible striation texture. |
| 7 | `periosteum` | Periosteum (bone surface lining), not undermined. Rendered as cream/white. |
| 8 | `periosteumUndermined` | Periosteum after undermining. Same visual appearance as material 7. |
| 10 | `undermineMarker` | Visual marker for undermined tissue regions. Rendered in blue. |

### Shoulder Extension Layers

| ID | Name | Description |
|----|------|-------------|
| 11 | `tendon` | Tendon tissue (supraspinatus). Rendered with a pearlescent white appearance and longitudinal fibrous texture that runs along the tendon axis. The shader creates a glistening effect via fiber-aligned normal perturbation. |
| 12 | `jointCapsule` | Joint capsule / labrum tissue. Rendered as translucent pinkish-white with a smooth surface. Uses slight alpha transparency (0.92). |
| 13 | `boneSurface` | Exposed bone surface (e.g., humeral head footprint). Rendered as ivory/cream with subtle porous surface variation using multi-octave simplex noise. |

In the default `materialLayerConfig`, the shoulder extension fields (`tendon`, `jointCapsule`, `boneSurface`) are set to -1, indicating they are not present. The shoulder `.smd` file explicitly sets these to 11, 12, and 13 respectively via the `"materialLayers"` JSON section.

---

## 5. Tissue Regions

The shoulder model defines 5 tissue regions in the `"tissueRegions"` section of `ShoulderPrototype.smd`. Each region specifies strain limits (how much the tissue can compress or stretch) and optional stiffness weights. The physics solver enforces these limits during simulation.

| Region | minStrain | maxStrain | lowTetWeight | highTetWeight | Subset OBJ | Description |
|--------|-----------|-----------|--------------|---------------|------------|-------------|
| `skin_deltoid` | 0.6 | 1.8 | (global) | (global) | -- | Shoulder skin over the deltoid. Moderately extensible, allowing significant stretch for flap mobilization. |
| `deltoid_muscle` | 0.5 | 2.5 | 200.0 | 600.0 | `ShoulderMuscle_deltoid.obj` | Deltoid muscle belly. Highly extensible (up to 2.5x) with low stiffness, reflecting the compliance of skeletal muscle. |
| `supraspinatus_tendon` | 0.85 | 1.15 | 2000.0 | 4000.0 | `ShoulderTendon_supraspinatus.obj` | Supraspinatus tendon. Very narrow strain range and high stiffness, modeling the relatively inextensible nature of tendon tissue. This is the tissue typically torn in rotator cuff injuries. |
| `joint_capsule` | 0.9 | 1.1 | 3000.0 | 5000.0 | -- | Glenohumeral joint capsule. Narrow strain range and high stiffness. Resists deformation to maintain joint stability. |
| `bone` | 0.99 | 1.01 | 50000.0 | 100000.0 | -- | Bone tissue. Essentially rigid (less than 1% strain allowed) with extremely high stiffness weights. |

**Strain values explained:** A `minStrain` of 1.0 means no compression is allowed; values below 1.0 permit compression. A `maxStrain` of 1.0 means no stretch; values above 1.0 permit extension. For example, the supraspinatus tendon with `minStrain=0.85, maxStrain=1.15` can compress by 15% or stretch by 15%.

---

## 6. Surgical Tools

Tools are selected from the **Tools** menu or the on-screen toolbox. The shoulder extension adds three new tools (IDs 8-10) below a separator line in the menu, in addition to the 8 standard tools (IDs 0-7).

### Standard Tools

| ID | Menu Name | Description |
|----|-----------|-------------|
| 0 | **View** | Navigation mode. Physics simulation runs. Use mouse to rotate, pan, and zoom the camera. No tissue interaction. |
| 1 | **Hook** | Place tissue hooks to retract and hold tissue. Right-click on tissue to place a hook, then drag to apply force. Physics pauses when the tool is active; deformation is computed when switching to View. |
| 2 | **Knife** | Make incisions. Right-click to begin a cut on the skin surface, drag to extend the incision line. Incisions split the mesh topology. |
| 3 | **Undermine** | Separate tissue layers. Right-click on tissue to mark undermining points. Creates a plane of separation between the skin flap and the deep bed. |
| 4 | **Suture** | Place sutures to close wounds or reattach tissue. Right-click on an incision edge to set the first suture point, then right-click the opposing edge to set the second point. Auto-suture spacing is configurable (`autoSutureSpacing` in the `.smd` file, default 0.10). Use **Promote sutures** from the Tools menu to convert temporary sutures to permanent physics constraints. |
| 5 | **Excise** | Remove tissue. Right-click to mark tissue for excision within a fenced region. |
| 6 | **Deep cut** | Make incisions that extend through the full thickness of the tissue, reaching the deep bed layer. |
| 7 | **Periosteal** | Periosteal undermining. Right-click on periosteum (material 7) to mark triangles for undermining, separating tissue from the bone surface. |

### Shoulder Extension Tools

#### Anchor (Tool ID 8 -- `TOOL_SUTURE_ANCHOR`)

**Purpose:** Place bone-fixed suture anchors for rotator cuff reattachment. In real surgery, suture anchors are screws or press-fit devices inserted into bone with attached suture threads. In the simulator, an anchor establishes a fixed point on bone-adjacent tissue from which sutures can originate.

**How to use:**
1. Select **Anchor** from the Tools menu.
2. Right-click on a periosteum surface (material 7), undermined periosteum (material 8), or deep bed surface (material 5). These are the bone-adjacent tissue surfaces where anchors are valid.
3. A gold-colored sphere appears at the placement point, confirming anchor placement.
4. A dialog confirms: "Suture anchor placed. Switch to Suture tool to attach threads."
5. Switch to the **Suture** tool to connect suture threads from the anchor to the torn tendon edge.

**What it does internally:**
- Validates that the clicked surface is bone-adjacent tissue (materials 5, 7, or 8). Clicking other materials produces an error.
- Computes the surface normal at the placement point.
- Creates a `sutureAnchor` struct storing the bone position, surface normal, and collision object index.
- Adds a visual sphere marker (gold, radius = 2.5% of scene radius).
- Records the placement in the surgical history for replay.

**Constraints:** Anchors cannot be placed on skin, muscle, fat, or tendon surfaces -- only on periosteum or deep bed. This reflects the surgical reality that anchors must be fixed into bone.

#### Scope (Tool ID 9 -- `TOOL_ARTHROSCOPE`)

**Purpose:** Simulate an arthroscopic camera view. In real shoulder surgery, an arthroscope is a small camera inserted through a portal (small incision) to visualize the interior of the joint. The simulator approximates this by narrowing the field of view and positioning the camera near the tissue surface.

**How to use:**
1. Select **Scope** from the Tools menu.
2. Right-click on any tissue surface to place the arthroscope portal.
3. The camera field of view narrows to approximately 30 degrees (from the default ~70 degree FOV), simulating the restricted arthroscopic view.
4. A dialog confirms: "Arthroscope placed. Press ESC or switch tool to exit scope view."
5. To exit arthroscope mode, switch to any other tool (e.g., **View**). The FOV automatically resets to normal.

**What it does internally:**
- Stores the portal triangle index in `_arthroscopePortalIdx`.
- Reduces the camera view height parameter from 0.7 to 0.35, creating a narrow FOV.
- When leaving arthroscope mode (switching to another tool), `setToolState()` automatically detects the transition and restores the original FOV and screen aspect ratio.

#### Grasp (Tool ID 10 -- `TOOL_GRASPER`)

**Purpose:** Grasp and manipulate tissue with a two-point tissue grasper. This is a strong-grip variant of the hook tool, representing the forceful tissue manipulation done with arthroscopic graspers during rotator cuff mobilization.

**How to use:**
1. Select **Grasp** from the Tools menu.
2. Right-click on deformable tissue to place the grasper.
3. Drag to manipulate the grasped tissue. The grasper uses "strong hooks" (power hooks) regardless of the global Power Hooks setting.
4. The grasped point behaves like a hook but with increased grip strength, preventing tissue slippage during manipulation.

**What it does internally:**
- Temporarily enables `_strongHooks = true` for the placement, then restores the previous setting. This means the grasper always uses maximum grip force.
- Creates a hook at the clicked position via the existing hook system.
- Initializes the physics solver if needed, then launches the physics computation on a TBB task thread.
- Records the grasper placement in the surgical history as a hook action.

---

## 7. Typical Workflow -- Rotator Cuff Repair

The following is a representative step-by-step workflow for simulating a rotator cuff repair:

1. **Load the scene.** File > Load Scene > `ShoulderPrototype.smd`. Wait for the tetrahedral lattice to initialize.

2. **Inspect the anatomy.** Use the **View** tool to rotate and examine the shoulder model. Identify the skin surface, the deltoid muscle region, and the bone structures.

3. **Make the skin incision.** Select the **Knife** tool. Right-click and drag along the planned incision line on the skin surface (material 2) to create an incision over the lateral shoulder.

4. **Undermine the skin flap.** Select the **Undermine** tool. Right-click on the tissue to mark undermining points, separating the skin from the underlying deltoid fascia along the deep bed plane.

5. **Retract the skin.** Select the **Hook** tool. Place hooks on the skin flap edges and drag to retract the flap, exposing the deltoid and deeper structures. Switch to **View** to let the physics settle.

6. **Expose the rotator cuff.** If needed, use the **Deep cut** tool to incise through the deltoid to expose the supraspinatus tendon and its insertion on the humeral head.

7. **Inspect with the arthroscope (optional).** Select the **Scope** tool. Click near the joint to get an arthroscopic view of the supraspinatus tendon and its attachment. Switch back to another tool to exit scope view.

8. **Mobilize the tendon.** Select the **Grasp** tool. Grasp the torn edge of the supraspinatus tendon and drag it toward the bone footprint. The narrow strain limits of the tendon (0.85-1.15) will resist excessive stretching, reflecting the real difficulty of tendon mobilization.

9. **Place suture anchors.** Select the **Anchor** tool. Right-click on the periosteum or deep bed surface (materials 5, 7, or 8) at the humeral head footprint to place one or more bone-fixed suture anchors. Gold spheres mark the anchor positions.

10. **Attach sutures.** Select the **Suture** tool. Place sutures connecting the tendon edge to the anchor locations. This simulates threading the suture through the tendon and tying it to the anchor.

11. **Promote sutures.** Select **Tools > Promote sutures** to convert the temporary suture constraints into permanent physics constraints. Switch to **View** to observe the repaired tendon under tension.

12. **Evaluate the repair.** Use the **View** tool to observe the tissue deformation. Check that the tendon is adequately approximated to the bone footprint without excessive tension (strain values should stay within the configured limits).

13. **Save the history.** Use **File > Save History** to save the surgical history as a JSON file for later replay or review.

---

## 8. Troubleshooting

### "json mValueType==ObjectVal required" error

**Cause:** The scene file (`.smd`) contains a JSON parsing error. This typically occurs when a JSON value is accessed as an `Object` but is actually a different type (string, array, number, etc.), or when the JSON is malformed (missing commas, unmatched braces, trailing commas).

**Solution:**
- Validate the `.smd` file with a JSON linter (e.g., `python -m json.tool ShoulderPrototype.smd`).
- Ensure all expected object fields are present and correctly typed. In particular, `"dynamicObjects"`, `"staticObjects"`, `"tetrahedralProperties"`, and `"materialLayers"` must be JSON objects (not arrays or strings).
- Check for trailing commas after the last element in any object or array, which are invalid in strict JSON.

### OBJ winding order issues

**Cause:** The OBJ files referenced by the scene may have inconsistent triangle face winding (clockwise vs. counter-clockwise). This can cause incorrect surface normals, inverted collision detection, or visual artifacts (faces appearing inside-out).

**Solution:**
- Ensure all OBJ files use consistent counter-clockwise (CCW) face winding, which is the OpenGL convention.
- If a surface appears invisible or lit from the wrong side, the winding is likely reversed. Use a mesh editing tool (e.g., Blender, MeshLab) to recalculate or flip normals.
- For static bone objects, incorrect winding can cause collision detection failures where soft tissue passes through bone instead of colliding with it.

### Missing .bed file

**Cause:** The deep bed mapping file (`ShoulderSkin.bed`) is not found in the Model directory. The `.bed` file is derived from the dynamic object name -- for `ShoulderSkin.obj`, the loader expects `ShoulderSkin.bed` in the same directory.

**Symptoms:** The error message "Undermine layer .bed file could not be found" appears on scene load. Undermining operations will not function correctly without this file.

**Solution:**
- Verify that `ShoulderSkin.bed` exists in the same directory as `ShoulderSkin.obj` (the `Model/` directory).
- The `.bed` file contains precomputed vertex-to-deep-bed projection data. It must be generated from `ShoulderSkin.obj` and `ShoulderDeepBed.obj` using the bed file generation tool. If the file is missing, it may need to be regenerated or restored from version control.
- The naming convention is strict: the `.bed` file must have exactly the same base name as the dynamic object OBJ file (e.g., `ShoulderSkin.obj` requires `ShoulderSkin.bed`).

### Physics fails to initialize after tool placement

**Cause:** Placing a grasper or hook on certain mesh locations can fail to initialize the physics solver, producing an error like "Couldn't initialize physics after grasper placement."

**Solution:**
- Try placing the tool at a slightly different location on the tissue surface.
- Ensure the tetrahedral lattice was fully constructed on scene load (check the console for lattice creation messages).
- If physics repeatedly fails, reload the scene and try a different approach to tissue manipulation.

### Anchor placement rejected

**Cause:** The Anchor tool requires clicking on bone-adjacent tissue surfaces (materials 5, 7, or 8). Clicking on skin (2), fat (4), muscle (6), tendon (11), or other materials will produce the error: "Suture anchors can only be placed on periosteum or deep bed surface (bone-adjacent tissue)."

**Solution:**
- Ensure you are clicking on the periosteum, undermined periosteum, or deep bed surface. These surfaces may need to be exposed first by incising and retracting overlying tissue.
- Use the **View** tool to rotate the model and identify the correct surface before switching to the **Anchor** tool.
