#!/usr/bin/env python3
"""
Generate .smd (scene definition) files for SkinFlaps OBJ meshes.

Creates a JSON scene file with:
  - Dynamic object reference (the OBJ file)
  - Tetrahedral physics parameters (14 properties)
  - Material layer mapping (9 base + optional shoulder extensions)
  - Optional tissue region overrides
  - Optional texture file references

Anatomy presets:
  - generic:  balanced defaults for general models
  - facial:   parameters tuned for facial tissue simulation
  - shoulder: includes tendon/capsule/bone material layers

Usage:
  python generate_smd.py Model.obj
  python generate_smd.py Model.obj --anatomy shoulder --scene-name MyScene
  python generate_smd.py Model.obj --output Model.smd
"""

import argparse
import json
import os
import sys


# ── Physics Parameter Presets ────────────────────────────────────────

PRESETS = {
    "generic": {
        "minStrain": 0.7,
        "maxStrain": 1.4,
        "lowTetWeight": 300.0,
        "highTetWeight": 800.0,
        "TJunctionWeight": 50.0,
        "collisionWeight": 40000.0,
        "selfCollisionWeight": 80000.0,
        "fixedWeight": 10000.0,
        "periferalWeight": 1000.0,
        "hookWeight": 800.0,
        "sutureWeight": 3000.0,
        "autoSutureSpacing": 0.10,
        "nTetSizeLevels": 2,
        "maxDimMegatetSubdivs": 16,
    },
    "facial": {
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
        "maxDimMegatetSubdivs": 34,
    },
    "shoulder": {
        "minStrain": 0.7,
        "maxStrain": 1.4,
        "lowTetWeight": 300.0,
        "highTetWeight": 800.0,
        "TJunctionWeight": 50.0,
        "collisionWeight": 40000.0,
        "selfCollisionWeight": 80000.0,
        "fixedWeight": 10000.0,
        "periferalWeight": 1000.0,
        "hookWeight": 800.0,
        "sutureWeight": 3000.0,
        "autoSutureSpacing": 0.10,
        "nTetSizeLevels": 2,
        "maxDimMegatetSubdivs": 16,
    },
}

# ── Material Layer Definitions ───────────────────────────────────────

MATERIAL_LAYERS_BASE = {
    "boundary": 1,
    "skinSurface": 2,
    "incisionEdge": 3,
    "subcutaneous": 4,
    "deepBed": 5,
    "muscle": 6,
    "periosteum": 7,
    "periosteumUndermined": 8,
    "undermineMarker": 10,
}

MATERIAL_LAYERS_SHOULDER = {
    **MATERIAL_LAYERS_BASE,
    "tendon": 11,
    "jointCapsule": 12,
    "boneSurface": 13,
}

# ── Tissue Region Defaults ───────────────────────────────────────────

TISSUE_REGIONS = {
    "generic": {
        "default": {"minStrain": 0.5, "maxStrain": 2.0}
    },
    "facial": {
        "cheek": {"minStrain": 0.5, "maxStrain": 2.0},
        "eyelid": {"minStrain": 0.5, "maxStrain": 2.0},
        "forehead": {"minStrain": 0.75, "maxStrain": 1.2},
        "scalp": {"minStrain": 0.85, "maxStrain": 1.0},
        "nose": {"minStrain": 0.85, "maxStrain": 1.0},
        "lip": {"minStrain": 0.6, "maxStrain": 1.5},
        "periorbital": {"minStrain": 0.6, "maxStrain": 1.6},
    },
    "shoulder": {
        "skin_deltoid": {"minStrain": 0.6, "maxStrain": 1.8}
    },
}


def generate_smd(obj_filename, scene_name=None, anatomy="generic",
                 fragment_shader=None, texture_files=None):
    """Generate an .smd scene definition dict.

    Args:
        obj_filename: name of the OBJ file (basename only)
        scene_name: scene name (default: derived from OBJ filename)
        anatomy: preset name ("generic", "facial", "shoulder")
        fragment_shader: optional fragment shader filename
        texture_files: optional dict of texture_filename -> slot_number

    Returns:
        dict representing the .smd JSON structure
    """
    if scene_name is None:
        scene_name = os.path.splitext(obj_filename)[0]

    if anatomy not in PRESETS:
        raise ValueError(f"Unknown anatomy preset: {anatomy}. "
                         f"Choose from: {list(PRESETS.keys())}")

    smd = {}
    smd["sceneName"] = scene_name

    # Fragment shader (shoulder anatomy uses custom shader)
    if fragment_shader:
        smd["fragmentShader"] = fragment_shader
    elif anatomy == "shoulder":
        smd["fragmentShader"] = "shoulderFragmentShader.txt"

    # Texture files
    if texture_files:
        smd["textureFiles"] = texture_files
    else:
        smd["textureFiles"] = {
            "diffuse2.jpg": 1,
            "normal.jpg": 2,
        }

    # Dynamic objects
    smd["dynamicObjects"] = {
        obj_filename: {
            "textureMaps": [1, 2, 1, 2]
        }
    }

    # Tetrahedral properties
    smd["tetrahedralProperties"] = dict(PRESETS[anatomy])

    # Tissue regions
    smd["tissueRegions"] = dict(TISSUE_REGIONS.get(anatomy, TISSUE_REGIONS["generic"]))

    # Material layers
    if anatomy == "shoulder":
        smd["materialLayers"] = dict(MATERIAL_LAYERS_SHOULDER)
    else:
        smd["materialLayers"] = dict(MATERIAL_LAYERS_BASE)

    # Fixed collision sets (empty by default)
    smd["fixedCollisionSets"] = {}

    return smd


def validate_smd(smd):
    """Validate generated .smd structure.

    Returns list of (severity, message) tuples.
    """
    issues = []

    # Required sections
    for key in ("dynamicObjects", "tetrahedralProperties"):
        if key not in smd:
            issues.append(("ERROR", f"Missing required section: {key}"))

    # Physics parameter ranges
    tp = smd.get("tetrahedralProperties", {})

    ranges = {
        "minStrain": (0.5, 1.0),
        "maxStrain": (1.0, 2.0),
        "lowTetWeight": (100, 5000),
        "highTetWeight": (100, 10000),
        "TJunctionWeight": (10, 4000),
        "collisionWeight": (1000, 100000),
        "selfCollisionWeight": (1000, 100000),
        "fixedWeight": (1000, 50000),
        "periferalWeight": (0.1, 10000),
        "hookWeight": (10, 5000),
        "sutureWeight": (100, 10000),
        "autoSutureSpacing": (0.01, 0.5),
        "nTetSizeLevels": (1, 4),
        "maxDimMegatetSubdivs": (10, 34),
    }

    for param, (lo, hi) in ranges.items():
        if param in tp:
            val = tp[param]
            if val < lo or val > hi:
                issues.append(("WARNING",
                               f"{param}={val} outside typical range [{lo}, {hi}]"))

    if "minStrain" in tp and "maxStrain" in tp:
        if tp["minStrain"] >= tp["maxStrain"]:
            issues.append(("ERROR", "minStrain must be < maxStrain"))

    # Material layer uniqueness
    ml = smd.get("materialLayers", {})
    positive_vals = [v for v in ml.values() if isinstance(v, int) and v > 0]
    if len(positive_vals) != len(set(positive_vals)):
        issues.append(("ERROR", "Duplicate material layer IDs"))

    return issues


def main():
    parser = argparse.ArgumentParser(
        description="Generate .smd scene files for SkinFlaps OBJ meshes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_smd.py Model/MyModel.obj
  python generate_smd.py Model/MyModel.obj --anatomy shoulder
  python generate_smd.py Model/MyModel.obj --scene-name MySurgery --output Model/MySurgery.smd
"""
    )
    parser.add_argument("input", metavar="INPUT_OBJ",
                        help="Input OBJ file path")
    parser.add_argument("--output", "-o", metavar="OUTPUT_SMD",
                        help="Output .smd file path (default: same name as input)")
    parser.add_argument("--anatomy", choices=["generic", "facial", "shoulder"],
                        default="generic",
                        help="Anatomy preset for physics parameters (default: generic)")
    parser.add_argument("--scene-name", metavar="NAME",
                        help="Scene name (default: derived from OBJ filename)")
    parser.add_argument("--fragment-shader", metavar="FILE",
                        help="Fragment shader filename")
    parser.add_argument("--validate-only", action="store_true",
                        help="Validate an existing .smd file instead of generating")

    args = parser.parse_args()

    # Validate existing .smd
    if args.validate_only:
        smd_path = args.input
        if not os.path.isfile(smd_path):
            print(f"ERROR: File not found: {smd_path}", file=sys.stderr)
            sys.exit(1)
        with open(smd_path, 'r') as f:
            smd = json.load(f)
        issues = validate_smd(smd)
        if not issues:
            print(f"[OK] {smd_path}: valid .smd")
            sys.exit(0)
        for severity, msg in issues:
            print(f"[{severity}] {msg}")
        has_errors = any(s == "ERROR" for s, _ in issues)
        sys.exit(1 if has_errors else 0)

    # Generate new .smd
    if not os.path.isfile(args.input):
        print(f"ERROR: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    obj_basename = os.path.basename(args.input)
    if args.output is None:
        args.output = os.path.splitext(args.input)[0] + ".smd"

    print(f"\n=== Generate .smd File ===")
    print(f"  OBJ:     {obj_basename}")
    print(f"  Anatomy: {args.anatomy}")
    print(f"  Output:  {args.output}")

    smd = generate_smd(
        obj_filename=obj_basename,
        scene_name=args.scene_name,
        anatomy=args.anatomy,
        fragment_shader=args.fragment_shader,
    )

    # Validate before writing
    issues = validate_smd(smd)
    if issues:
        print(f"\n--- Validation ---")
        for severity, msg in issues:
            print(f"  [{severity}] {msg}")
        if any(s == "ERROR" for s, _ in issues):
            print(f"\nERROR: Generated .smd has validation errors. Not writing.")
            sys.exit(1)

    # Write
    with open(args.output, 'w') as f:
        json.dump(smd, f, indent=4)
        f.write('\n')

    print(f"\n  Written to: {args.output}")
    print(f"\n--- Physics Parameters ({args.anatomy}) ---")
    tp = smd["tetrahedralProperties"]
    for key, val in tp.items():
        print(f"  {key}: {val}")

    print(f"\n--- Material Layers ---")
    for name, mid in smd["materialLayers"].items():
        print(f"  {name}: {mid}")

    sys.exit(0)


if __name__ == "__main__":
    main()
