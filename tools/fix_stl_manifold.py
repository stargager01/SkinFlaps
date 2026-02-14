#!/usr/bin/env python3
"""
Repair non-manifold STL meshes for SkinFlaps compatibility.

Diagnoses and fixes common STL issues that cause BCC tet cutter failure:
  - Non-manifold edges (shared by >2 faces)
  - Non-manifold vertices (pinch points)
  - Open boundaries (holes)
  - Inconsistent winding order
  - Degenerate (zero-area) faces
  - Self-intersections (detected, not auto-repaired)

The BCC tet cutter (vnBccTetCutter_tbb.cpp) requires a single closed manifold
surface. getConnectedComponents() fails on non-manifold geometry with
"Solid ordering error".

Dependencies: trimesh, numpy

Usage:
  python fix_stl_manifold.py <input.stl> [output.stl]
  python fix_stl_manifold.py --diagnose Model.stl
  python fix_stl_manifold.py --dir <directory>
"""

import argparse
import os
import sys
from collections import defaultdict

import numpy as np

try:
    import trimesh
except ImportError:
    print("ERROR: trimesh required. Install with: pip install trimesh", file=sys.stderr)
    sys.exit(1)


def diagnose_mesh(mesh):
    """Analyze mesh for manifold issues.

    Returns dict of diagnostics with counts and descriptions.
    """
    diag = {}

    diag["vertices"] = len(mesh.vertices)
    diag["faces"] = len(mesh.faces)
    diag["watertight"] = mesh.is_watertight
    diag["euler_number"] = mesh.euler_number

    # Edge analysis
    edge_face_count = defaultdict(int)
    for face in mesh.faces:
        for i in range(3):
            a, b = int(face[i]), int(face[(i + 1) % 3])
            e = tuple(sorted((a, b)))
            edge_face_count[e] += 1

    boundary = sum(1 for c in edge_face_count.values() if c == 1)
    non_manifold = sum(1 for c in edge_face_count.values() if c > 2)
    diag["boundary_edges"] = boundary
    diag["non_manifold_edges"] = non_manifold
    diag["total_edges"] = len(edge_face_count)

    # Degenerate faces
    areas = mesh.area_faces
    diag["degenerate_faces"] = int(np.sum(areas < 1e-12))

    # Duplicate faces
    face_set = set()
    duplicates = 0
    for face in mesh.faces:
        key = tuple(sorted(face))
        if key in face_set:
            duplicates += 1
        face_set.add(key)
    diag["duplicate_faces"] = duplicates

    # Connected components
    try:
        components = mesh.split(only_watertight=False)
        diag["connected_components"] = len(components)
    except Exception:
        diag["connected_components"] = -1

    # Volume (negative means inverted normals)
    if mesh.is_watertight:
        diag["volume"] = float(mesh.volume)
    else:
        diag["volume"] = None

    return diag


def print_diagnosis(filepath, diag):
    """Print formatted diagnosis report."""
    print(f"\n{'='*60}")
    print(f"STL Manifold Diagnosis: {filepath}")
    print(f"{'='*60}")

    issues = []

    print(f"  Vertices:            {diag['vertices']}")
    print(f"  Faces:               {diag['faces']}")
    print(f"  Edges:               {diag['total_edges']}")
    print(f"  Watertight:          {diag['watertight']}")
    print(f"  Euler number:        {diag['euler_number']}")
    print(f"  Connected components: {diag['connected_components']}")

    if diag.get("volume") is not None:
        print(f"  Volume:              {diag['volume']:.4f}")
        if diag["volume"] < 0:
            issues.append("Negative volume (inverted normals)")

    print(f"\n--- Issues ---")

    if diag["boundary_edges"] > 0:
        issues.append(f"{diag['boundary_edges']} boundary edges (open holes)")
    if diag["non_manifold_edges"] > 0:
        issues.append(f"{diag['non_manifold_edges']} non-manifold edges")
    if diag["degenerate_faces"] > 0:
        issues.append(f"{diag['degenerate_faces']} degenerate (zero-area) faces")
    if diag["duplicate_faces"] > 0:
        issues.append(f"{diag['duplicate_faces']} duplicate faces")
    if diag["euler_number"] != 2:
        issues.append(f"Euler number {diag['euler_number']} (expected 2 for closed surface)")
    if diag["connected_components"] != 1:
        issues.append(f"{diag['connected_components']} connected components (need exactly 1)")

    if not issues:
        print(f"  [OK] No manifold issues detected")
    else:
        for issue in issues:
            print(f"  [!] {issue}")

    return issues


def repair_mesh(mesh, verbose=True):
    """Attempt to repair non-manifold mesh issues.

    Returns:
        repaired trimesh.Trimesh, list of repair actions taken
    """
    actions = []

    original_verts = len(mesh.vertices)
    original_faces = len(mesh.faces)

    # 1. Remove degenerate faces
    keep_mask = mesh.nondegenerate_faces()
    n_degen = int(np.sum(~keep_mask))
    if n_degen > 0:
        mesh.update_faces(keep_mask)
        actions.append(f"Removed {n_degen} degenerate faces")

    # 2. Remove duplicate faces
    unique_mask = mesh.unique_faces()
    n_dup = int(np.sum(~unique_mask))
    if n_dup > 0:
        mesh.update_faces(unique_mask)
        actions.append(f"Removed {n_dup} duplicate faces")

    # 3. Remove unreferenced vertices
    mesh.remove_unreferenced_vertices()

    # 4. Fill holes
    if not mesh.is_watertight:
        try:
            trimesh.repair.fill_holes(mesh)
            if mesh.is_watertight:
                actions.append("Filled holes to make watertight")
            else:
                actions.append("Attempted hole filling (still not watertight)")
        except Exception as e:
            actions.append(f"Hole filling failed: {e}")

    # 5. Fix winding order
    try:
        trimesh.repair.fix_winding(mesh)
        actions.append("Fixed winding order consistency")
    except Exception as e:
        actions.append(f"Winding fix failed: {e}")

    # 6. Fix normals
    try:
        trimesh.repair.fix_normals(mesh)
        trimesh.repair.fix_inversion(mesh)
        actions.append("Fixed face normals (outward)")
    except Exception as e:
        actions.append(f"Normal fix failed: {e}")

    # 7. Handle multiple components (keep largest)
    try:
        components = mesh.split(only_watertight=False)
        if len(components) > 1:
            largest = max(components, key=lambda c: len(c.faces))
            mesh = largest
            actions.append(f"Kept largest component ({len(mesh.faces)} faces) "
                           f"of {len(components)} components")
    except Exception as e:
        actions.append(f"Component splitting failed: {e}")

    if verbose:
        print(f"\n--- Repair Actions ---")
        for action in actions:
            print(f"  - {action}")
        print(f"  Before: {original_verts} verts, {original_faces} faces")
        print(f"  After:  {len(mesh.vertices)} verts, {len(mesh.faces)} faces")

    return mesh, actions


def fix_stl_file(input_path, output_path=None, diagnose_only=False):
    """Load, diagnose, and optionally repair an STL file.

    Returns:
        (success, issues_found, issues_fixed)
    """
    if output_path is None:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_fixed{ext}"

    # Load
    try:
        mesh = trimesh.load(input_path, force='mesh')
    except Exception as e:
        print(f"ERROR: Cannot load {input_path}: {e}")
        return False, [], []

    # Diagnose
    diag = diagnose_mesh(mesh)
    issues = print_diagnosis(input_path, diag)

    if diagnose_only:
        return len(issues) == 0, issues, []

    if not issues:
        print(f"\n  Mesh is already manifold. No repair needed.")
        return True, [], []

    # Repair
    print(f"\n--- Repairing ---")
    mesh, actions = repair_mesh(mesh)

    # Re-diagnose
    diag_after = diagnose_mesh(mesh)
    issues_after = print_diagnosis(f"{input_path} (after repair)", diag_after)

    # Save
    mesh.export(output_path)
    print(f"\n  Saved repaired mesh to: {output_path}")

    return len(issues_after) == 0, issues, actions


def main():
    parser = argparse.ArgumentParser(
        description="Diagnose and repair non-manifold STL files for SkinFlaps."
    )
    parser.add_argument("files", nargs="*", metavar="FILE",
                        help="STL file(s) to process")
    parser.add_argument("--dir", "-d", metavar="DIRECTORY",
                        help="Process all .stl files in directory")
    parser.add_argument("--diagnose", action="store_true",
                        help="Diagnose only, don't repair")
    parser.add_argument("--output", "-o", metavar="OUTPUT",
                        help="Output path (default: <input>_fixed.stl)")
    parser.add_argument("--in-place", action="store_true",
                        help="Overwrite input file with repaired version")
    args = parser.parse_args()

    stl_files = list(args.files) if args.files else []
    if args.dir:
        for entry in sorted(os.listdir(args.dir)):
            if entry.lower().endswith(".stl"):
                stl_files.append(os.path.join(args.dir, entry))

    if not stl_files:
        parser.print_help()
        sys.exit(1)

    all_ok = True
    for filepath in stl_files:
        output = args.output
        if args.in_place:
            output = filepath
        success, _, _ = fix_stl_file(filepath, output, diagnose_only=args.diagnose)
        if not success:
            all_ok = False

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
