# SkinFlaps File Format Reference

This document describes the two custom JSON-based file formats used by the
SkinFlaps surgical simulation:

| Extension | Purpose | Parser |
|-----------|---------|--------|
| `.hst` | Surgical history (action replay) | `surgicalActions::nextHistoryAction()` in `SkinFlaps/src/surgicalActions.cpp` |
| `.smd` | Scene / model definition | `bccTetScene::loadScene()` in `SkinFlaps/src/bccTetScene.cpp` |

Both formats are standard JSON. The simulator pretty-prints them on save for
human readability, but any conforming JSON serialiser will produce valid files.

---

## History File Format (.hst)

### Overview

A `.hst` file records a complete surgical procedure as an ordered sequence of
discrete actions. During replay, `surgicalActions::nextHistoryAction()` walks
through these actions one at a time to reproduce the surgery step by step.

History files live in the `History/` directory. There are currently 13 example
files covering procedures such as cleft lip repairs, eyelid reconstruction,
scalp rotation flaps, and ear reconstruction.

### Top-Level Structure

The file is a **JSON array** of action objects:

```json
[
  { "<actionType>": <actionValue> },
  { "<actionType>": <actionValue> },
  ...
]
```

Each element is a JSON object with exactly **one key** that identifies the
action type. The value format varies by action type (see below).

### Conventions

**Attachment points.** Most actions reference locations on the mesh surface.
These are encoded with three fields that together uniquely identify a point:

| Field | Type | Description |
|-------|------|-------------|
| `material` | Integer | Material ID of the triangle (typically 2 for skin surface; 4 for deep bed; 8 for periosteal). |
| `historyTexture` | Array of 2 floats | Texture-space UV coordinates `[u, v]` in the range [0, 1]. |
| `displacement` | Array of 3 floats | Spatial displacement vector `[x, y, z]` from the rest-pose position. Usually `[0, 0, 0]` when recorded before physics deformation. |

During replay, the simulator calls `getHistoryAttachPoint()` which maps
`(material, historyTexture, displacement)` back to a specific triangle and
barycentric coordinates on the current mesh.

### Rules

1. The **first action** in every history file MUST be `loadSceneFile`.
2. Actions are replayed strictly in order.
3. The `pointNumber` field in array-based actions (incision, deep cut) must
   match the actual number of point objects that follow the header.
4. Suture numbers (`sutureNum`) are sequential user-visible indices starting
   from 0.
5. Hook numbers (`hookNum`) are assigned by the simulator; on replay the
   simulator may reassign them.

---

### Action Types

#### `loadSceneFile`

Loads the scene definition file that provides the model, textures, and physics
parameters. Must be the first action in every history file.

**Value:** String -- the `.smd` filename (relative to the Model directory).

```json
{
  "loadSceneFile": "FacialFlaps.smd"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| *(value)* | String | Yes | Filename of the `.smd` scene file. |

---

#### `addHook`

Places a skin hook at a surface point to apply traction forces.

**Value:** Object with the following fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `hookNum` | Integer | Yes | Hook index (0-based, assigned on creation). |
| `material` | Integer | Yes | Material ID of the attachment triangle. |
| `historyTexture` | Array[2] of Float | Yes | Texture UV of the attachment point. |
| `displacement` | Array[3] of Float | Yes | Spatial displacement from rest pose. |
| `strongHook` | Boolean | No | If `true`, hook uses stronger spring constant. Defaults to `false` if absent. |

```json
{
  "addHook": {
    "hookNum": 0,
    "material": 2,
    "historyTexture": [0.557334, 0.344458],
    "displacement": [-0.256638, -0.572136, 0.273468]
  }
}
```

**With strong hook:**

```json
{
  "addHook": {
    "hookNum": 3,
    "material": 4,
    "strongHook": true,
    "historyTexture": [0.575156, 0.607315],
    "displacement": [0.0, 0.0, 0.0]
  }
}
```

---

#### `moveHook`

Repositions an existing hook to a new 3D world-space coordinate.

**Value:** Array of 4 numbers: `[hookNum, x, y, z]`.

| Index | Type | Description |
|-------|------|-------------|
| 0 | Integer | Hook number to move. |
| 1 | Float | New X position (world space). |
| 2 | Float | New Y position (world space). |
| 3 | Float | New Z position (world space). |

```json
{
  "moveHook": [0, 4.548689, -3.703511, 6.901753]
}
```

---

#### `deleteHook`

Removes a previously placed hook.

**Value:** Integer -- the hook number to delete.

```json
{
  "deleteHook": 0
}
```

---

#### `makeIncision`

Performs a surface incision (skin cut) along a polyline of points on the skin
surface. This cuts only the skin layer, not the underlying deep bed.

**Value:** Array where the first element is a header object and subsequent
elements are incision point objects.

**Header object (index 0):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `incisedObject` | Integer | Yes | Object index (currently always 0). |
| `Tin` | Boolean | Yes | Whether the incision start connects to an existing edge ("T-in"). |
| `Tout` | Boolean | Yes | Whether the incision end connects to an existing edge ("T-out"). |
| `pointNumber` | Integer | Yes | Number of incision points that follow. |

**Incision point objects (indices 1..N):**

Each is an object with a single key `"incisionPoint"` whose value is an
attachment-point object:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `material` | Integer | Yes | Material ID (typically 2). |
| `historyTexture` | Array[2] of Float | Yes | Texture UV. |
| `displacement` | Array[3] of Float | Yes | Spatial displacement from rest pose. |

```json
{
  "makeIncision": [
    {
      "Tin": false,
      "Tout": false,
      "incisedObject": 0,
      "pointNumber": 3
    },
    {
      "incisionPoint": {
        "material": 2,
        "historyTexture": [0.642312, 0.759176],
        "displacement": [0.0, 0.0, 0.0]
      }
    },
    {
      "incisionPoint": {
        "material": 2,
        "historyTexture": [0.649553, 0.724417],
        "displacement": [0.0, 0.0, 0.0]
      }
    },
    {
      "incisionPoint": {
        "material": 2,
        "historyTexture": [0.568569, 0.726894],
        "displacement": [0.0, 0.0, 0.0]
      }
    }
  ]
}
```

---

#### `undermine`

Separates the skin flap from the underlying deep bed across a set of
triangles. Each element identifies one triangle in the undermined region.

**Value:** Array of undermine-point wrapper objects.

Each element is an object with a single key `"underminePoint"` whose value
contains:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `material` | Integer | Yes | Material ID (2 at time of recording, even though internally marked as 10 during the operation). |
| `historyTexture` | Array[2] of Float | Yes | Texture UV of the triangle center. |
| `displacement` | Array[3] of Float | Yes | Spatial displacement. |
| `incisionConnect` | Boolean | No | Whether this triangle connects to an existing incision edge. Defaults to `true` for backward compatibility if absent. |

```json
{
  "undermine": [
    {
      "underminePoint": {
        "material": 2,
        "historyTexture": [0.620794, 0.615570],
        "displacement": [-0.363785, 0.321045, 0.327774],
        "incisionConnect": true
      }
    },
    {
      "underminePoint": {
        "material": 2,
        "historyTexture": [0.613441, 0.607032],
        "displacement": [0.0, 0.0, 0.0],
        "incisionConnect": false
      }
    }
  ]
}
```

---

#### `excise`

Removes (excises) a region of tissue that has been fully outlined by
incisions. The point identifies any triangle inside the closed incision
boundary.

**Value:** Object -- a single attachment-point:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `material` | Integer | Yes | Material ID of the excised triangle. |
| `historyTexture` | Array[2] of Float | Yes | Texture UV of a point inside the excision region. |
| `displacement` | Array[3] of Float | Yes | Spatial displacement. |

```json
{
  "excise": {
    "material": 2,
    "historyTexture": [0.541420, 0.449944],
    "displacement": [0.0, 0.0, 0.0]
  }
}
```

---

#### `addSuture`

Places a suture connecting two points on opposite sides of an incision. Each
suture has two endpoints (0 and 1), each specified by its own attachment
fields.

**Value:** Object with the following fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `sutureNum` | Integer | Yes | User-visible suture index (0-based, sequential). |
| `linked` | Boolean | Yes | If `true`, the suture is part of a linked line that generates automatic intermediate sutures. |
| `material0` | Integer | Yes | Material ID for endpoint 0. |
| `historyTexture0` | Array[2] of Float | Yes | Texture UV for endpoint 0. |
| `displacement0` | Array[3] of Float | Yes | Spatial displacement for endpoint 0. |
| `material1` | Integer | Yes | Material ID for endpoint 1. |
| `historyTexture1` | Array[2] of Float | Yes | Texture UV for endpoint 1. |
| `displacement1` | Array[3] of Float | Yes | Spatial displacement for endpoint 1. |

```json
{
  "addSuture": {
    "sutureNum": 0,
    "linked": false,
    "material0": 2,
    "historyTexture0": [0.501693, 0.399796],
    "displacement0": [1.333618, 2.445465, -0.020859],
    "material1": 2,
    "historyTexture1": [0.501560, 0.399941],
    "displacement1": [-0.798347, 1.796623, 1.037186]
  }
}
```

**Linked suture** (generates automatic sutures between linked pairs):

```json
{
  "addSuture": {
    "sutureNum": 1,
    "linked": true,
    "material0": 2,
    "historyTexture0": [0.508966, 0.398562],
    "displacement0": [1.220528, -0.081123, -0.605408],
    "material1": 2,
    "historyTexture1": [0.546395, 0.397575],
    "displacement1": [-0.427994, -0.038300, 0.562134]
  }
}
```

---

#### `deleteSuture`

Removes a suture. Has two forms depending on whether a user-placed suture or
an automatically generated suture row is being deleted.

**Form 1 -- Delete a user suture by number:**

**Value:** Integer -- the user suture number.

```json
{
  "deleteSuture": 12
}
```

**Form 2 -- Delete automatic sutures generated by a linked suture:**

**Value:** Object with a single key `"autoSuturesFor"`:

| Field | Type | Description |
|-------|------|-------------|
| `autoSuturesFor` | Integer | User suture number whose automatic sutures should be deleted. |

```json
{
  "deleteSuture": {
    "autoSuturesFor": 3
  }
}
```

---

#### `makeDeepCut`

Performs a full-thickness cut through both skin and deep bed along a polyline.
Unlike `makeIncision` (skin only), this separates tissue through all layers.

**Value:** Array where the first element is a header object and subsequent
elements are deep-cut point objects.

**Header object (index 0):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `deepCutObject` | Integer | Yes | Object index (currently always 0). |
| `openIn` | Boolean | Yes | Whether the cut start is an open (free) end. |
| `openOut` | Boolean | Yes | Whether the cut end is an open (free) end. |
| `pointNumber` | Integer | Yes | Number of deep-cut points that follow. |

**Deep-cut point objects (indices 1..N):**

Each is an object with a single key `"deepCutPoint"` whose value contains:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `material` | Integer | Yes | Material ID (typically 2). |
| `historyTexture` | Array[2] of Float | Yes | Texture UV. |
| `displacement` | Array[3] of Float | Yes | Spatial displacement. |
| `postNormal` | Array[3] of Float | Yes | Post normal vector `[x, y, z]` used to determine the deep cutting direction. |

```json
{
  "makeDeepCut": [
    {
      "deepCutObject": 0,
      "openIn": true,
      "openOut": true,
      "pointNumber": 3
    },
    {
      "deepCutPoint": {
        "material": 2,
        "historyTexture": [0.514769, 0.440112],
        "displacement": [0.0, 0.0, 0.0],
        "postNormal": [0.001581, -0.010274, 0.999946]
      }
    },
    {
      "deepCutPoint": {
        "material": 2,
        "historyTexture": [0.527765, 0.469496],
        "displacement": [0.0, 0.0, 0.0],
        "postNormal": [0.006090, 0.037597, 0.999274]
      }
    },
    {
      "deepCutPoint": {
        "material": 2,
        "historyTexture": [0.551337, 0.477113],
        "displacement": [0.0, 0.0, 0.0],
        "postNormal": [0.142526, 0.239985, 0.960257]
      }
    }
  ]
}
```

---

#### `periostealUndermine`

Separates the periosteum (bone-lining tissue) from the underlying bone across
a set of triangles. Similar to `undermine` but operates on the periosteal
layer (material 8) rather than the skin layer.

**Value:** Array of periosteal-triangle wrapper objects.

Each element is an object with a single key `"periostealTriangle"` whose
value contains:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `material` | Integer | Yes | Material ID (typically 8 for periosteum). |
| `historyTexture` | Array[2] of Float | Yes | Texture UV of the triangle center. |
| `displacement` | Array[3] of Float | Yes | Spatial displacement. |
| `incisionConnect` | Boolean | No | Whether this triangle connects to an incision edge. Defaults to `true` if absent. |

```json
{
  "periostealUndermine": [
    {
      "periostealTriangle": {
        "material": 8,
        "historyTexture": [0.185462, 0.125795],
        "displacement": [0.0, 0.0, 0.0],
        "incisionConnect": true
      }
    },
    {
      "periostealTriangle": {
        "material": 8,
        "historyTexture": [0.214413, 0.121237],
        "displacement": [0.0, 0.0, 0.0],
        "incisionConnect": false
      }
    }
  ]
}
```

---

#### `promoteSutureApproximations`

Converts preliminary ("fake") suture approximations into finalized sutures.
This is typically called after all sutures for a section are placed, to
commit the suture-driven deformation.

**Value:** Integer (the value is ignored by the parser; conventionally 0).

```json
{
  "promoteSutureApproximations": 0
}
```

---

#### `pausePhysics`

Pauses the physics simulation. Used to freeze the model state before
performing the next series of actions.

**Value:** Integer (the value is ignored by the parser; conventionally 0).

```json
{
  "pausePhysics": 0
}
```

---

### Complete Example

A minimal history file showing a typical surgical workflow:

```json
[
  {
    "loadSceneFile": "FacialFlaps.smd"
  },
  {
    "makeIncision": [
      {
        "Tin": false,
        "Tout": false,
        "incisedObject": 0,
        "pointNumber": 2
      },
      {
        "incisionPoint": {
          "material": 2,
          "historyTexture": [0.50, 0.40],
          "displacement": [0.0, 0.0, 0.0]
        }
      },
      {
        "incisionPoint": {
          "material": 2,
          "historyTexture": [0.55, 0.45],
          "displacement": [0.0, 0.0, 0.0]
        }
      }
    ]
  },
  {
    "excise": {
      "material": 2,
      "historyTexture": [0.52, 0.42],
      "displacement": [0.0, 0.0, 0.0]
    }
  },
  {
    "undermine": [
      {
        "underminePoint": {
          "material": 2,
          "historyTexture": [0.53, 0.43],
          "displacement": [0.0, 0.0, 0.0],
          "incisionConnect": true
        }
      }
    ]
  },
  {
    "addHook": {
      "hookNum": 0,
      "material": 2,
      "historyTexture": [0.54, 0.44],
      "displacement": [0.0, 0.0, 0.0]
    }
  },
  {
    "moveHook": [0, 3.0, -2.0, 7.0]
  },
  {
    "addSuture": {
      "sutureNum": 0,
      "linked": false,
      "material0": 2,
      "historyTexture0": [0.50, 0.40],
      "displacement0": [0.1, 0.2, 0.0],
      "material1": 2,
      "historyTexture1": [0.55, 0.40],
      "displacement1": [-0.1, 0.2, 0.0]
    }
  },
  {
    "deleteHook": 0
  }
]
```

---

## Scene File Format (.smd)

### Overview

A `.smd` file defines a complete simulation scene: the 3D model geometry,
texture assignments, physics parameters, collision bodies, and (optionally)
region-specific material properties. Scene files live in the `Model/`
directory and are referenced by history files via the `loadSceneFile` action.

### Top-Level Structure

The file is a **JSON object** with the following sections (keys):

```json
{
  "dynamicObjects":        { ... },
  "staticObjects":         { ... },
  "textureFiles":          { ... },
  "tetrahedralProperties": { ... },
  "tetrahedralSubsets":    { ... },
  "tissueRegions":         { ... },
  "materialLayers":        { ... },
  "fixedCollisionSets":    { ... }
}
```

All sections except `dynamicObjects`, `textureFiles`, and
`tetrahedralProperties` are optional.

---

### `textureFiles`

Maps texture image filenames to integer texture IDs. These IDs are referenced
by the object sections.

**Structure:** Object where each key is a filename (String) and each value is
a unique integer ID.

| Field | Type | Description |
|-------|------|-------------|
| `<filename>` | Integer | Unique texture ID assigned to this file. |

Textures are loaded from the same directory as the `.smd` file (the Model
directory). Supported formats include `.jpg` and `.bmp`.

Convention: IDs 1-2 are the dynamic object's diffuse and normal maps; IDs 3-4
are the deep bed diffuse and normal; higher IDs are used for static objects.

```json
"textureFiles": {
    "diffuse2.jpg": 1,
    "normal.jpg": 2,
    "deepBedTexture.jpg": 3,
    "deepBedNormal.jpg": 4,
    "eye_diffuse.jpg": 5,
    "eye_diffuseNormal.jpg": 6,
    "teeth_diffuse.jpg": 7,
    "teeth_diffuseNormal.jpg": 8
}
```

---

### `dynamicObjects`

Defines the deformable (surgically operable) mesh. Currently the simulator
supports exactly **one** dynamic object.

**Structure:** Object where each key is an `.obj` filename and each value is
an object with a `textureMaps` array.

| Field | Type | Description |
|-------|------|-------------|
| `textureMaps` | Array of Integer | Ordered list of texture IDs: `[diffuse, normal, deepBedDiffuse, deepBedNormal]`. |

The dynamic object's `.obj` file is loaded as a `materialTriangles` mesh. A
corresponding `.bed` file (same base name, `.bed` extension) provides the
undermine deep-bed geometry if present.

```json
"dynamicObjects": {
    "wholeFace_NasalCartilage.obj": {
        "textureMaps": [1, 2, 3, 4]
    }
}
```

---

### `staticObjects`

Defines non-deformable scenery objects (eyes, teeth, etc.) that are rendered
but not affected by physics.

**Structure:** Object where each key is an `.obj` filename and each value
assigns texture and normal maps.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `textureMap` | Integer | Yes | Texture ID for the diffuse map. |
| `normalMap` | Integer | Yes | Texture ID for the normal map. |

```json
"staticObjects": {
    "eye_right_CBC.obj": {
        "textureMap": 5,
        "normalMap": 6
    },
    "eye_left_CBC.obj": {
        "textureMap": 5,
        "normalMap": 6
    },
    "teeth.obj": {
        "textureMap": 7,
        "normalMap": 8
    }
}
```

---

### `tetrahedralProperties`

Global physics parameters for the BCC tetrahedral lattice that drives the
soft-tissue simulation.

**Structure:** Object with the following fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `minStrain` | Float | Yes | Minimum allowable strain ratio (compression limit). Values < 1.0 allow compression. |
| `maxStrain` | Float | Yes | Maximum allowable strain ratio (stretch limit). Values > 1.0 allow stretch. |
| `lowTetWeight` | Float | Yes | Spring constant for low-resolution tetrahedra. |
| `highTetWeight` | Float | Yes | Spring constant for high-resolution tetrahedra. |
| `TJunctionWeight` | Float | Yes | Constraint weight for T-junction nodes between resolution levels. |
| `collisionWeight` | Float | Yes | Penalty weight for collisions with fixed objects. |
| `selfCollisionWeight` | Float | Yes | Penalty weight for self-collisions within the dynamic mesh. |
| `fixedWeight` | Float | Yes | Constraint weight for fixed (boundary) vertices. |
| `periferalWeight` | Float | Yes | Constraint weight for peripheral vertices at the lattice boundary. |
| `hookWeight` | Float | Yes | Spring constant applied to hook constraints. |
| `sutureWeight` | Float | Yes | Spring constant applied to suture constraints. |
| `autoSutureSpacing` | Float | Yes | Spacing distance for automatically generated intermediate sutures. |
| `nTetSizeLevels` | Integer | Yes | Number of multiresolution tetrahedral size levels (typically 4). |
| `maxDimMegatetSubdivs` | Integer | Yes | Maximum subdivisions along the longest dimension of the bounding mega-tetrahedron (controls initial tet count). |

```json
"tetrahedralProperties": {
    "minStrain": 0.8,
    "maxStrain": 1.26,
    "lowTetWeight": 500.0,
    "highTetWeight": 1000.0,
    "TJunctionWeight": 50.0,
    "collisionWeight": 40000.0,
    "selfCollisionWeight": 80000.0,
    "fixedWeight": 10000.0,
    "periferalWeight": 1000.0,
    "hookWeight": 1000.0,
    "sutureWeight": 2000.0,
    "autoSutureSpacing": 0.14,
    "nTetSizeLevels": 4,
    "maxDimMegatetSubdivs": 34
}
```

---

### `tetrahedralSubsets`

Defines regions of the tetrahedral lattice with overridden physics properties.
Each subset is defined by an `.obj` file whose enclosed volume selects which
tetrahedra belong to the subset.

**Structure:** Object where each key is an `.obj` filename and each value
overrides a subset of `tetrahedralProperties`:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `minStrain` | Float | Yes | Override minimum strain for this region. |
| `maxStrain` | Float | Yes | Override maximum strain for this region. |
| `lowTetWeight` | Float | Yes | Override low-tet spring constant. |
| `highTetWeight` | Float | Yes | Override high-tet spring constant. |

```json
"tetrahedralSubsets": {
    "nasalCartilage.obj": {
        "minStrain": 0.95,
        "maxStrain": 1.05,
        "lowTetWeight": 4000.0,
        "highTetWeight": 5000.0
    },
    "membranousSeptum.obj": {
        "minStrain": 0.4,
        "maxStrain": 4.0,
        "lowTetWeight": 150.0,
        "highTetWeight": 400.0
    }
}
```

---

### `tissueRegions`

Defines named anatomical regions of the face with region-specific stretch
limits. This section was added to allow different areas of the face (cheek,
eyelid, scalp, etc.) to have distinct biomechanical behavior based on
clinical tissue-mobility data.

If this section is absent, the simulator loads a built-in set of default
region properties via `getDefaultRegionProperties()`.

**Structure:** Object where each key is a region name (String) and each value
specifies the regional properties:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `minStrain` | Float | Yes | Minimum strain for this region. |
| `maxStrain` | Float | Yes | Maximum strain for this region. |
| `lowTetWeight` | Float | No | Override low-tet weight (0.0 if absent = use global). |
| `highTetWeight` | Float | No | Override high-tet weight (0.0 if absent = use global). |
| `subsetObj` | String | No | `.obj` filename of a closed manifold defining the spatial extent. If absent, region is identified by name only. |

```json
"tissueRegions": {
    "cheek": {
        "minStrain": 0.5,
        "maxStrain": 2.0
    },
    "eyelid": {
        "minStrain": 0.5,
        "maxStrain": 2.0
    },
    "forehead": {
        "minStrain": 0.75,
        "maxStrain": 1.2
    },
    "scalp": {
        "minStrain": 0.85,
        "maxStrain": 1.0
    },
    "nose": {
        "minStrain": 0.85,
        "maxStrain": 1.0
    },
    "lip": {
        "minStrain": 0.6,
        "maxStrain": 1.5
    },
    "periorbital": {
        "minStrain": 0.6,
        "maxStrain": 1.6
    }
}
```

**With a spatial-extent OBJ:**

```json
"tissueRegions": {
    "cheek": {
        "minStrain": 0.6,
        "maxStrain": 2.0,
        "subsetObj": "cheekRegion.obj"
    },
    "scalp": {
        "minStrain": 0.85,
        "maxStrain": 1.0,
        "lowTetWeight": 800,
        "highTetWeight": 1800
    }
}
```

---

### `materialLayers`

Maps semantic tissue layer names to integer material IDs used internally by the
simulator. This section allows different anatomies (face, shoulder, etc.) to
define their own tissue layer semantics without modifying C++ source code.

If this section is absent, the simulator uses hardcoded defaults that match the
facial tissue model (see Material ID Reference below).

**Structure:** Object with the following fields:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `boundary` | Integer | No | 1 | Blank/peripheral boundary. |
| `skinSurface` | Integer | No | 2 | Top skin surface (textured). |
| `incisionEdge` | Integer | No | 3 | Incised skin edge (procedural dermis/fat). |
| `subcutaneous` | Integer | No | 4 | Flap bottom / subcutaneous layer. |
| `deepBed` | Integer | No | 5 | Deep tissue bed surface. |
| `muscle` | Integer | No | 6 | Deep cut muscle layer. |
| `periosteum` | Integer | No | 7 | Periosteum / bone surface, not undermined. |
| `periosteumUndermined` | Integer | No | 8 | Periosteum, undermined. |
| `undermineMarker` | Integer | No | 10 | Visual marker for undermined tissue. |
| `tendon` | Integer | No | -1 | Tendon layer (non-facial extension). |
| `jointCapsule` | Integer | No | -1 | Joint capsule / labrum (non-facial extension). |
| `boneSurface` | Integer | No | -1 | Bone surface (non-facial extension). |
| `arthroscopicPortal` | Integer | No | -1 | Arthroscopic entry portal (non-facial extension). |

Fields with a default of -1 are extension slots for non-facial anatomies and
are not used in the facial model. Only include the fields that differ from the
defaults.

**Facial model (explicit defaults):**

```json
"materialLayers": {
    "boundary": 1,
    "skinSurface": 2,
    "incisionEdge": 3,
    "subcutaneous": 4,
    "deepBed": 5,
    "muscle": 6,
    "periosteum": 7,
    "periosteumUndermined": 8,
    "undermineMarker": 10
}
```

**Hypothetical shoulder model (with extensions):**

```json
"materialLayers": {
    "boundary": 1,
    "skinSurface": 2,
    "incisionEdge": 3,
    "subcutaneous": 4,
    "deepBed": 5,
    "muscle": 6,
    "tendon": 7,
    "jointCapsule": 8,
    "boneSurface": 9,
    "arthroscopicPortal": 10
}
```

---

### `fixedCollisionSets`

Defines rigid collision bodies by associating an `.obj` collision proxy mesh
with a set of dynamic-mesh vertex indices. These vertices are constrained to
avoid penetrating the collision body during physics simulation.

**Structure:** Object where each key is an `.obj` filename (collision proxy)
and each value is an array of integer vertex indices from the dynamic mesh.

| Field | Type | Description |
|-------|------|-------------|
| `<proxyFilename>` | Array of Integer | Dynamic-mesh vertex indices that form the collision set. |

```json
"fixedCollisionSets": {
    "eye_right_CBC.obj": [1247, 1246, 1248, 2457, 3691, ...],
    "eye_left_CBC.obj": [3934, 3935, 3933, 3929, ...],
    "teethCollisionProxy.obj": [2830, 806, 807, ...]
}
```

Note: An older `fixedGeometry` key is no longer supported and will cause a
runtime error if encountered.

---

### Complete Example

A minimal `.smd` scene file:

```json
{
    "dynamicObjects": {
        "face.obj": {
            "textureMaps": [1, 2, 3, 4]
        }
    },
    "textureFiles": {
        "skin_diffuse.jpg": 1,
        "skin_normal.jpg": 2,
        "deepbed_diffuse.jpg": 3,
        "deepbed_normal.jpg": 4
    },
    "tetrahedralProperties": {
        "minStrain": 0.8,
        "maxStrain": 1.26,
        "lowTetWeight": 500.0,
        "highTetWeight": 1000.0,
        "TJunctionWeight": 50.0,
        "collisionWeight": 40000.0,
        "selfCollisionWeight": 80000.0,
        "fixedWeight": 10000.0,
        "periferalWeight": 1000.0,
        "hookWeight": 1000.0,
        "sutureWeight": 2000.0,
        "autoSutureSpacing": 0.14,
        "nTetSizeLevels": 4,
        "maxDimMegatetSubdivs": 34
    }
}
```

---

## Existing Scene and History Files

### Scene Files (Model/)

| File | Dynamic Object | Static Objects | Notes |
|------|----------------|----------------|-------|
| `FacialFlaps.smd` | `wholeFace_NasalCartilage.obj` | eyes, teeth | Full face with facial regions. |
| `FacialFlaps_noTeethEyes.smd` | `wholeFace_NasalCartilage.obj` | *(none)* | Simplified (no static objects or facial regions). |
| `unilatCleftLip_complete.smd` | `unilatCompleteCleft.obj` | `LmaxillaFace.obj` | Complete unilateral cleft lip model. |
| `unilatCleftLip_Incomplete.smd` | *(incomplete cleft variant)* | *(varies)* | Incomplete cleft lip model. |

### History Files (History/)

| File | Scene | Procedure |
|------|-------|-----------|
| `AbbeEstlanderLip.hst` | `FacialFlaps.smd` | Abbe-Estlander lip flap |
| `AntiaBuch_ear.hst` | `FacialFlaps.smd` | Antia-Buch ear reconstruction |
| `cervicoFacialFlap.hst` | `FacialFlaps.smd` | Cervicofacial rotation flap |
| `cheekSplasty.hst` | `FacialFlaps.smd` | Cheek S-plasty |
| `cleft_CuttingRepair.hst` | `unilatCleftLip_complete.smd` | Cleft lip cutting repair |
| `cleft_FisherRepair.hst` | `unilatCleftLip_complete.smd` | Fisher cleft lip repair |
| `cleft_RoseThompson.hst` | *(cleft model)* | Rose-Thompson repair |
| `cleft_TennisonRandall.hst` | *(cleft model)* | Tennison-Randall repair |
| `foreheadFlapToNose.hst` | `FacialFlaps.smd` | Forehead flap to nose |
| `FurlowPalateRepair.hst` | *(cleft model)* | Furlow palate repair |
| `postAuricularEar.hst` | `FacialFlaps.smd` | Post-auricular ear flap |
| `scalpDoubleRotation.hst` | `FacialFlaps.smd` | Scalp double rotation flap |
| `TenzelEyelid.hst` | `FacialFlaps.smd` | Tenzel eyelid reconstruction |

---

## Material ID Reference

Material IDs used across both formats:

| ID | Meaning |
|----|---------|
| 2 | Skin surface (primary operable tissue) |
| 3-6 | Internal material layers |
| 4 | Deep bed surface |
| 7 | Periosteum (pre-undermine) |
| 8 | Periosteum (post-undermine) |
| 10 | Temporary marking during undermine operations |

---

## Notes for Tooling

When writing tools that programmatically create or edit these files:

1. **JSON compliance.** Both formats are standard JSON. Use any conforming
   JSON library. The simulator uses `json::Deserialize()` / `json::Serialize()`
   from a lightweight C++ JSON library.

2. **Pretty printing.** The simulator saves `.hst` files through a custom
   `prettyPrintJSON` formatter. This is cosmetic; the parser accepts any valid
   JSON whitespace.

3. **Coordinate system.** All 3D coordinates (displacement, moveHook position,
   postNormal) are in the same world-space coordinate system as the `.obj`
   model files.

4. **Texture UV range.** History texture coordinates should be in `[0, 1]`.
   The validation script in `tests/validate_history.py` warns on values
   outside this range.

5. **Action ordering matters.** During replay, each action modifies the mesh
   topology or physics state. Later actions depend on the state left by
   earlier ones. Do not reorder actions.

6. **Scene file paths.** All `.obj`, `.jpg`, and `.bed` filenames in `.smd`
   files are relative to the Model directory (the same directory containing
   the `.smd` file).

7. **History file references.** The `loadSceneFile` value is a bare filename,
   not a path. The simulator prepends the configured scene directory.
