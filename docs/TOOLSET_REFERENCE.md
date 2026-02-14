# SkinFlaps Surgical Simulation Toolset Reference

## 1. Base States and Tools (0--7)

| ID | Name | Description |
|----|------|-------------|
| 0 | Viewer / Physics | Default runtime state. Activates physics simulation via `setPhysicsPause(false)`. Not a tool per se, but the simulator's baseline mode. |
| 1 | Hook | Tissue retraction and fixation. |
| 2 | Knife | Initiates incisions on the skin surface. |
| 3 | Undermine | Subcutaneous layer dissection. |
| 4 | Suture | Wound closure via suturing. |
| 5 | Excise | Lesion excision (removal of tissue). |
| 6 | Deep Cut | Deep-plane incision through multiple tissue layers. |
| 7 | Periosteal | Periosteal elevation (stripping periosteum from bone). |

## 2. Shoulder Extension Tools (8--10)

| ID | Name | Description |
|----|------|-------------|
| 8 | Anchor | Places suture anchors on bone for fixation. Targets periosteum layer; actions are recorded in simulation history. |
| 9 | Scope | Arthroscope view simulation. Normal FOV: **0.7f**; arthroscope FOV: **0.35f** (approximately half). |
| 10 | Grasp | Strong tissue grasper for manipulating tissue during arthroscopic procedures. |

## 3. Usage Precautions

- **Viewer / Physics mode** is the default runtime state, not a selectable tool.
- **Scope**: The narrow FOV (0.35f) limits visibility; minimize unnecessary camera movement while active.
- **Anchor**: Avoid excessive placement to prevent bone-surface damage in the simulation.
- **Grasp**: Control applied pressure to reduce the risk of tissue damage.
- **Knife / Deep Cut**: Strictly limit incision depth and direction to prevent unintended geometry artifacts.

## 4. Creating Custom Models

### Step 1 -- Create a single closed-surface OBJ

The dynamic OBJ **must** be a single closed manifold surface (one solid volume boundary).

Permitted material IDs in the OBJ file:

| Material ID | Layer |
|-------------|-------|
| 1 | Boundary |
| 2 | Skin surface |
| 7 | Periosteum |

Other layers (`deepBed`, `muscle`, etc.) are **not** embedded in the OBJ. Material 5 (`deepBed`) is assigned at runtime by the BCC tet cutter.

### Step 2 -- Create a `.bed` file

Map each skin vertex to its corresponding deep-bed position (closest-point projection). One line per vertex.

### Step 3 -- Write a `.smd` scene descriptor

- Define `materialLayerConfig` (13 fields).
- Specify tissue properties in the `tetrahedralProperties` section.
- `AnatomyType` (`FACIAL`, `SHOULDER`, `GENERIC`) is auto-detected by the scene loader.

### Step 4 -- Validate the OBJ

```bash
python tests/validate_obj.py path/to/model.obj
```

### Step 5 -- Load and test in the simulator

Launch the simulator, load the new scene, and verify each tool interaction works correctly.

### Step 6 -- Verify history recording / playback

Use `.hst` history files to record a simulation session and replay it to confirm deterministic behavior.

## 5. Validation and Testing

| Resource | Purpose |
|----------|---------|
| `tests/validate_obj.py` | OBJ integrity checks (manifold, winding, materials). |
| `tools/fix_obj_winding.py` | Batch-fix inverted face normals via BFS. |
| 196 automated tests | Unit and regression test suite. |
| `AnatomyType` auto-detection | Scene loader identifies anatomy from `.smd` metadata. |
