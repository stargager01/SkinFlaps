#!/usr/bin/env python3
"""
Convert STL files to SkinFlaps-compatible OBJ format.

Handles the complete STL-to-OBJ pipeline:
  1. Parse ASCII/Binary STL (via trimesh)
  2. Merge duplicate vertices (STL stores per-face vertices)
  3. Remove degenerate faces (zero-area triangles)
  4. Repair non-manifold geometry if possible
  5. Unify face normals (outward-facing)
  6. Generate UV texture coordinates (planar/spherical/cylindrical)
  7. Assign material IDs {1=boundary, 2=skin, 7=periosteum}
  8. Write SkinFlaps-compatible OBJ with smoothing groups

CRITICAL architecture rules (see MEMORY.md):
  - Output MUST be a SINGLE closed surface (one solid volume boundary)
  - Only materials {1, 2, 7} allowed in OBJ
  - Material 5 (deepBed) is NEVER in OBJ -- use .bed file instead
  - Both mat1 (boundary, >=6 faces) and mat7 (periosteum, >=6 faces) required

Dependencies: trimesh, numpy

Usage:
  python convert_stl_to_obj.py <input.stl> [output.obj]
  python convert_stl_to_obj.py Model.stl --uv-method spherical
  python convert_stl_to_obj.py Model.stl --material-mode auto --boundary-axis y
"""

import argparse
import os
import sys
import math

import numpy as np

try:
    import trimesh
except ImportError:
    print("ERROR: trimesh required. Install with: pip install trimesh", file=sys.stderr)
    sys.exit(1)


# ── UV Generation ───────────────────────────────────────────────────


def generate_uv_planar(vertices, axis="y"):
    """Planar UV projection along the specified axis.

    Projects vertices onto a plane perpendicular to `axis`, then normalizes
    to [0,1] range.
    """
    if axis == "x":
        u_coords = vertices[:, 1]
        v_coords = vertices[:, 2]
    elif axis == "z":
        u_coords = vertices[:, 0]
        v_coords = vertices[:, 1]
    else:  # default "y"
        u_coords = vertices[:, 0]
        v_coords = vertices[:, 2]

    # Normalize to [0, 1]
    u_min, u_max = u_coords.min(), u_coords.max()
    v_min, v_max = v_coords.min(), v_coords.max()

    u_range = u_max - u_min
    v_range = v_max - v_min
    if u_range < 1e-12:
        u_range = 1.0
    if v_range < 1e-12:
        v_range = 1.0

    uvs = np.column_stack([
        (u_coords - u_min) / u_range,
        (v_coords - v_min) / v_range
    ])
    return uvs


def generate_uv_spherical(vertices):
    """Spherical UV mapping from mesh centroid."""
    center = vertices.mean(axis=0)
    relative = vertices - center

    # Avoid division by zero
    r = np.linalg.norm(relative, axis=1)
    r = np.where(r < 1e-12, 1e-12, r)

    theta = np.arctan2(relative[:, 0], relative[:, 2])  # longitude
    phi = np.arccos(np.clip(relative[:, 1] / r, -1.0, 1.0))  # latitude

    u = (theta + np.pi) / (2 * np.pi)
    v = phi / np.pi

    return np.column_stack([u, v])


def generate_uv_cylindrical(vertices, axis="y"):
    """Cylindrical UV mapping around the specified axis."""
    center = vertices.mean(axis=0)
    relative = vertices - center

    if axis == "x":
        angle = np.arctan2(relative[:, 1], relative[:, 2])
        height = relative[:, 0]
    elif axis == "z":
        angle = np.arctan2(relative[:, 0], relative[:, 1])
        height = relative[:, 2]
    else:  # "y"
        angle = np.arctan2(relative[:, 0], relative[:, 2])
        height = relative[:, 1]

    u = (angle + np.pi) / (2 * np.pi)

    h_min, h_max = height.min(), height.max()
    h_range = h_max - h_min
    if h_range < 1e-12:
        h_range = 1.0
    v = (height - h_min) / h_range

    return np.column_stack([u, v])


UV_GENERATORS = {
    "planar": generate_uv_planar,
    "spherical": generate_uv_spherical,
    "cylindrical": generate_uv_cylindrical,
}


# ── Material Assignment ─────────────────────────────────────────────


def assign_materials_auto(mesh, axis="y", boundary_pct=8.0, periosteum_pct=8.0):
    """Automatically assign materials based on face centroid position along axis.

    Faces near the bottom of the mesh -> material 1 (boundary)
    Faces near the top of the mesh -> material 7 (periosteum)
    Everything else -> material 2 (skin)

    Args:
        mesh: trimesh.Trimesh object
        axis: axis along which to classify ("x", "y", or "z")
        boundary_pct: percentage of axis range for boundary region
        periosteum_pct: percentage of axis range for periosteum region
    """
    axis_idx = {"x": 0, "y": 1, "z": 2}[axis]
    centroids = mesh.triangles_center[:, axis_idx]

    c_min, c_max = centroids.min(), centroids.max()
    c_range = c_max - c_min
    if c_range < 1e-12:
        # Flat mesh: assign all as skin, with first/last 6 faces as boundary/periosteum
        n_faces = len(mesh.faces)
        materials = np.full(n_faces, 2, dtype=int)
        n_edge = min(max(6, n_faces // 10), n_faces // 3)
        materials[:n_edge] = 1
        materials[-n_edge:] = 7
        return materials

    boundary_thresh = c_min + c_range * (boundary_pct / 100.0)
    periosteum_thresh = c_max - c_range * (periosteum_pct / 100.0)

    materials = np.full(len(mesh.faces), 2, dtype=int)
    materials[centroids <= boundary_thresh] = 1
    materials[centroids >= periosteum_thresh] = 7

    # Ensure minimum face counts (>=6 each)
    n_boundary = np.sum(materials == 1)
    n_periosteum = np.sum(materials == 7)

    if n_boundary < 6:
        # Sort by centroid position, assign lowest 6 as boundary
        sorted_idx = np.argsort(centroids)
        for i in range(min(6, len(sorted_idx))):
            materials[sorted_idx[i]] = 1

    if n_periosteum < 6:
        sorted_idx = np.argsort(centroids)[::-1]
        for i in range(min(6, len(sorted_idx))):
            if materials[sorted_idx[i]] != 1:  # don't overwrite boundary
                materials[sorted_idx[i]] = 7

    return materials


def assign_materials_manual(mesh, boundary_faces=None, periosteum_faces=None):
    """Manual material assignment. All faces default to material 2 (skin).

    Optional face index lists for boundary (mat 1) and periosteum (mat 7).
    """
    materials = np.full(len(mesh.faces), 2, dtype=int)
    if boundary_faces:
        for idx in boundary_faces:
            if 0 <= idx < len(mesh.faces):
                materials[idx] = 1
    if periosteum_faces:
        for idx in periosteum_faces:
            if 0 <= idx < len(mesh.faces):
                materials[idx] = 7
    return materials


# ── STL Processing ──────────────────────────────────────────────────


def load_and_repair_stl(stl_path, fix_normals=True, decimate_target=None):
    """Load STL and perform mesh repair.

    Returns:
        trimesh.Trimesh with merged vertices, removed degenerates, unified normals
    """
    mesh = trimesh.load(stl_path, force='mesh')

    if not isinstance(mesh, trimesh.Trimesh):
        raise ValueError(f"Failed to load as single mesh: {stl_path}")

    original_faces = len(mesh.faces)
    original_verts = len(mesh.vertices)

    # trimesh automatically merges duplicate vertices on load
    # Remove degenerate (zero-area) and duplicate faces
    keep_mask = mesh.nondegenerate_faces()
    if not keep_mask.all():
        mesh.update_faces(keep_mask)
    unique_mask = mesh.unique_faces()
    if not unique_mask.all():
        mesh.update_faces(unique_mask)
    mesh.remove_unreferenced_vertices()

    # Fill holes if any
    if not mesh.is_watertight:
        trimesh.repair.fill_holes(mesh)
        trimesh.repair.fix_winding(mesh)

    # Fix normals to point outward
    if fix_normals:
        try:
            trimesh.repair.fix_normals(mesh)
            trimesh.repair.fix_inversion(mesh)
        except (ImportError, Exception) as e:
            print(f"  Warning: normal repair skipped ({e})")

    # Optional decimation
    if decimate_target and decimate_target < len(mesh.faces):
        mesh = mesh.simplify_quadric_decimation(decimate_target)

    print(f"  Loaded:   {original_verts} vertices, {original_faces} faces")
    print(f"  Repaired: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces")
    print(f"  Watertight: {mesh.is_watertight}")
    print(f"  Euler number: {mesh.euler_number}")

    return mesh


# ── OBJ Writer ──────────────────────────────────────────────────────


def write_skinflaps_obj(filepath, mesh, uvs, materials):
    """Write a SkinFlaps-compatible OBJ file.

    Format:
      v x y z          (vertices)
      vt u v           (texture coordinates, same count as vertices)
      s 1              (smoothing group)
      usemtl <int>     (material groups: 1, 2, 7)
      f v1/vt1 v2/vt2 v3/vt3  (faces with vertex/texcoord indices)
    """
    vertices = mesh.vertices
    faces = mesh.faces

    # Group faces by material
    mat_groups = {}
    for face_idx, mat_id in enumerate(materials):
        mat_groups.setdefault(int(mat_id), []).append(face_idx)

    # Validate material requirements
    for required_mat in (1, 7):
        count = len(mat_groups.get(required_mat, []))
        if count < 6:
            print(f"  WARNING: Material {required_mat} has only {count} faces "
                  f"(need >=6). Solver may produce singular matrix.")

    disallowed = set(mat_groups.keys()) - {1, 2, 7}
    if disallowed:
        print(f"  ERROR: Disallowed material IDs detected: {disallowed}")
        print(f"  Only materials {{1, 2, 7}} allowed in OBJ files.")
        return False

    with open(filepath, 'w') as f:
        basename = os.path.basename(filepath)
        f.write(f"# {basename} - Converted from STL for SkinFlaps simulator\n")
        f.write(f"# Single closed surface with material regions\n")
        f.write(f"# Materials: 1=boundary, 2=skinSurface, 7=periosteum\n")
        f.write(f"# Deep bed defined via .bed file (NOT as OBJ faces)\n")
        f.write(f"# Vertices: {len(vertices)}, Faces: {len(faces)}\n")

        # Write vertices
        for v in vertices:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")

        # Write texture coordinates (one per vertex)
        for uv in uvs:
            f.write(f"vt {uv[0]:.6f} {uv[1]:.6f}\n")

        # Smoothing group
        f.write("s 1\n")

        # Write face groups by material (sorted: 1, 2, 7)
        for mat_id in sorted(mat_groups.keys()):
            face_indices = mat_groups[mat_id]
            f.write(f"usemtl {mat_id}\n")
            for fi in face_indices:
                v0, v1, v2 = faces[fi]
                # OBJ is 1-indexed; vertex and texcoord share the same index
                f.write(f"f {v0+1}/{v0+1} {v1+1}/{v1+1} {v2+1}/{v2+1}\n")

    return True


# ── Diagnostics ─────────────────────────────────────────────────────


def print_diagnostics(mesh, materials):
    """Print mesh quality diagnostics."""
    mat_counts = {}
    for m in materials:
        mat_counts[int(m)] = mat_counts.get(int(m), 0) + 1

    print(f"\n--- Conversion Diagnostics ---")
    print(f"  Vertices:     {len(mesh.vertices)}")
    print(f"  Faces:        {len(mesh.faces)}")
    print(f"  Watertight:   {mesh.is_watertight}")
    print(f"  Euler number: {mesh.euler_number}")

    # Edge analysis
    edges = set()
    boundary_edges = 0
    for face in mesh.faces:
        for i in range(3):
            a, b = int(face[i]), int(face[(i + 1) % 3])
            e = (min(a, b), max(a, b))
            if e in edges:
                edges.discard(e)  # shared by 2 faces = manifold
            else:
                edges.add(e)
    boundary_edges = len(edges)
    print(f"  Boundary edges: {boundary_edges}" +
          (" (not manifold!)" if boundary_edges > 0 else " (manifold)"))

    print(f"\n--- Material Distribution ---")
    for mat_id in sorted(mat_counts.keys()):
        label = {1: "boundary", 2: "skinSurface", 7: "periosteum"}.get(mat_id, "unknown")
        print(f"  Material {mat_id} ({label}): {mat_counts[mat_id]} faces")

    # Triangle quality (aspect ratio)
    areas = mesh.area_faces
    if len(areas) > 0:
        print(f"\n--- Triangle Quality ---")
        print(f"  Min area:  {areas.min():.6e}")
        print(f"  Max area:  {areas.max():.6e}")
        print(f"  Mean area: {areas.mean():.6e}")
        degenerate = np.sum(areas < 1e-12)
        if degenerate > 0:
            print(f"  WARNING: {degenerate} degenerate (zero-area) triangles")


# ── Main ────────────────────────────────────────────────────────────


def convert_stl_to_obj(stl_path, obj_path=None, uv_method="planar",
                       material_mode="manual", boundary_axis="y",
                       boundary_pct=8.0, periosteum_pct=8.0,
                       fix_normals=True, decimate_target=None):
    """Main conversion pipeline.

    Returns:
        (obj_path, n_vertices, n_faces) on success, None on failure
    """
    if obj_path is None:
        obj_path = os.path.splitext(stl_path)[0] + ".obj"

    print(f"\n=== STL to OBJ Conversion ===")
    print(f"  Input:  {stl_path}")
    print(f"  Output: {obj_path}")
    print(f"  UV method: {uv_method}")
    print(f"  Material mode: {material_mode}")

    # Step 1: Load and repair
    print(f"\n--- Step 1: Load & Repair ---")
    mesh = load_and_repair_stl(stl_path, fix_normals=fix_normals,
                               decimate_target=decimate_target)

    if len(mesh.faces) < 12:
        print(f"ERROR: Mesh has only {len(mesh.faces)} faces. "
              f"Need at least 12 for boundary+periosteum+skin.")
        return None

    # Step 2: Generate UVs
    print(f"\n--- Step 2: UV Generation ({uv_method}) ---")
    if uv_method == "planar":
        uvs = generate_uv_planar(mesh.vertices, axis=boundary_axis)
    elif uv_method == "spherical":
        uvs = generate_uv_spherical(mesh.vertices)
    elif uv_method == "cylindrical":
        uvs = generate_uv_cylindrical(mesh.vertices, axis=boundary_axis)
    else:
        print(f"ERROR: Unknown UV method: {uv_method}")
        return None
    print(f"  Generated {len(uvs)} UV coordinates")

    # Step 3: Assign materials
    print(f"\n--- Step 3: Material Assignment ({material_mode}) ---")
    if material_mode == "auto":
        materials = assign_materials_auto(mesh, axis=boundary_axis,
                                          boundary_pct=boundary_pct,
                                          periosteum_pct=periosteum_pct)
    elif material_mode == "manual":
        # Default manual: bottom 8% boundary, top 8% periosteum, rest skin
        # This gives a reasonable starting point that users can refine
        materials = assign_materials_auto(mesh, axis=boundary_axis,
                                          boundary_pct=boundary_pct,
                                          periosteum_pct=periosteum_pct)
        print(f"  (Manual mode: using auto-assignment as initial layout)")
        print(f"  Edit the OBJ to adjust material regions as needed.")
    else:
        print(f"ERROR: Unknown material mode: {material_mode}")
        return None

    n_mat1 = int(np.sum(materials == 1))
    n_mat2 = int(np.sum(materials == 2))
    n_mat7 = int(np.sum(materials == 7))
    print(f"  Material 1 (boundary):   {n_mat1} faces")
    print(f"  Material 2 (skin):       {n_mat2} faces")
    print(f"  Material 7 (periosteum): {n_mat7} faces")

    # Step 4: Write OBJ
    print(f"\n--- Step 4: Write OBJ ---")
    success = write_skinflaps_obj(obj_path, mesh, uvs, materials)
    if not success:
        return None

    # Step 5: Diagnostics
    print_diagnostics(mesh, materials)

    print(f"\n=== Conversion Complete ===")
    print(f"  Output: {obj_path}")
    print(f"  Next steps:")
    print(f"    1. Validate: python3 tests/validate_obj.py {obj_path}")
    print(f"    2. Fix winding: python3 tools/fix_obj_winding.py {obj_path}")
    print(f"    3. Generate .bed: python3 tools/generate_bed.py {obj_path}")
    print(f"    4. Generate .smd: python3 tools/generate_smd.py {obj_path}")

    return obj_path, len(mesh.vertices), len(mesh.faces)


def main():
    parser = argparse.ArgumentParser(
        description="Convert STL files to SkinFlaps-compatible OBJ format.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python convert_stl_to_obj.py Model/MyModel.stl
  python convert_stl_to_obj.py Model/MyModel.stl --uv-method spherical
  python convert_stl_to_obj.py Model/MyModel.stl --material-mode auto --boundary-axis y
  python convert_stl_to_obj.py Model/MyModel.stl --output Model/Output.obj --decimate 5000
"""
    )
    parser.add_argument("input", metavar="INPUT_STL",
                        help="Input STL file path")
    parser.add_argument("--output", "-o", metavar="OUTPUT_OBJ",
                        help="Output OBJ file path (default: same name as input)")
    parser.add_argument("--uv-method", choices=["planar", "spherical", "cylindrical"],
                        default="planar",
                        help="UV coordinate generation method (default: planar)")
    parser.add_argument("--material-mode", choices=["manual", "auto"],
                        default="manual",
                        help="Material assignment mode (default: manual)")
    parser.add_argument("--boundary-axis", choices=["x", "y", "z"], default="y",
                        help="Axis for boundary/periosteum classification (default: y)")
    parser.add_argument("--boundary-pct", type=float, default=8.0,
                        help="Percentage of axis range for boundary region (default: 8.0)")
    parser.add_argument("--periosteum-pct", type=float, default=8.0,
                        help="Percentage of axis range for periosteum region (default: 8.0)")
    parser.add_argument("--no-fix-normals", action="store_true",
                        help="Skip normal repair (not recommended)")
    parser.add_argument("--decimate", type=int, metavar="TARGET_FACES",
                        help="Decimate mesh to target face count")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"ERROR: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    result = convert_stl_to_obj(
        stl_path=args.input,
        obj_path=args.output,
        uv_method=args.uv_method,
        material_mode=args.material_mode,
        boundary_axis=args.boundary_axis,
        boundary_pct=args.boundary_pct,
        periosteum_pct=args.periosteum_pct,
        fix_normals=not args.no_fix_normals,
        decimate_target=args.decimate,
    )

    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
