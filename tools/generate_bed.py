#!/usr/bin/env python3
"""
Generate .bed (deep bed) files for SkinFlaps OBJ meshes.

The .bed file maps each skin vertex to its corresponding deep-bed position.
The BCC tet cutter uses these positions to identify the deep tissue boundary
at runtime (material 5). Material 5 must NOT appear in the OBJ file itself.

Generation methods:
  1. Offset: Project each vertex inward along its normal by a fixed distance
  2. Reference: KD-tree closest-point projection to a separate deep-bed OBJ

Format: Plain text, one line per vertex
  vertex_index x y z

CRITICAL: Line count MUST match OBJ vertex count exactly.
  Mismatch -> setDeepBed() runtime failure.

Dependencies: numpy (required), trimesh (optional, for reference method)

Usage:
  python generate_bed.py Model.obj
  python generate_bed.py Model.obj --offset -5.0
  python generate_bed.py Model.obj --reference DeepBed.obj
  python generate_bed.py Model.obj --output Model.bed
"""

import argparse
import os
import sys

import numpy as np


def parse_obj_vertices_and_normals(obj_path):
    """Parse vertices from an OBJ file and estimate per-vertex normals.

    Returns:
        vertices: numpy array (N, 3)
        normals: numpy array (N, 3) - per-vertex normals (averaged from faces)
    """
    vertices = []
    faces = []

    with open(obj_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('v ') and not line.startswith('vt') and not line.startswith('vn'):
                parts = line.split()
                vertices.append([float(parts[1]), float(parts[2]), float(parts[3])])
            elif line.startswith('f '):
                parts = line.split()[1:]
                face_verts = [int(p.split('/')[0]) - 1 for p in parts]
                faces.append(face_verts)

    vertices = np.array(vertices, dtype=float)

    # Compute per-vertex normals from face normals
    normals = np.zeros_like(vertices)
    for face in faces:
        if len(face) < 3:
            continue
        v0 = vertices[face[0]]
        v1 = vertices[face[1]]
        v2 = vertices[face[2]]
        edge1 = v1 - v0
        edge2 = v2 - v0
        face_normal = np.cross(edge1, edge2)
        norm = np.linalg.norm(face_normal)
        if norm > 1e-12:
            face_normal /= norm
        for vi in face:
            normals[vi] += face_normal

    # Normalize per-vertex normals
    norms = np.linalg.norm(normals, axis=1, keepdims=True)
    norms = np.where(norms < 1e-12, 1.0, norms)
    normals /= norms

    return vertices, normals


def generate_bed_offset(vertices, normals, offset):
    """Generate deep bed positions by offsetting vertices along normals.

    Args:
        vertices: (N, 3) array of vertex positions
        normals: (N, 3) array of vertex normals
        offset: scalar offset distance (negative = inward)

    Returns:
        bed_positions: (N, 3) array
    """
    # Ensure normals point outward by checking they generally face away from centroid
    centroid = vertices.mean(axis=0)
    outward_check = np.sum((vertices - centroid) * normals, axis=1)
    # If most normals point inward, flip them
    if np.sum(outward_check < 0) > np.sum(outward_check > 0):
        normals = -normals

    # Offset should be negative (inward) for deep bed
    bed_positions = vertices + offset * normals
    return bed_positions


def generate_bed_reference(vertices, reference_obj_path):
    """Generate deep bed by closest-point projection to a reference mesh.

    Uses KD-tree for efficient nearest-neighbor lookup.

    Args:
        vertices: (N, 3) array of skin vertex positions
        reference_obj_path: path to deep-bed reference OBJ

    Returns:
        bed_positions: (N, 3) array
    """
    try:
        from scipy.spatial import KDTree
    except ImportError:
        print("ERROR: scipy required for reference method. "
              "Install with: pip install scipy", file=sys.stderr)
        sys.exit(1)

    # Parse reference OBJ vertices
    ref_vertices = []
    with open(reference_obj_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('v ') and not line.startswith('vt') and not line.startswith('vn'):
                parts = line.split()
                ref_vertices.append([float(parts[1]), float(parts[2]), float(parts[3])])

    ref_vertices = np.array(ref_vertices, dtype=float)

    if len(ref_vertices) == 0:
        print(f"ERROR: Reference OBJ has no vertices: {reference_obj_path}")
        sys.exit(1)

    # Build KD-tree and find closest points
    tree = KDTree(ref_vertices)
    distances, indices = tree.query(vertices)

    bed_positions = ref_vertices[indices]

    print(f"  Reference OBJ: {len(ref_vertices)} vertices")
    print(f"  Min distance: {distances.min():.6f}")
    print(f"  Max distance: {distances.max():.6f}")
    print(f"  Mean distance: {distances.mean():.6f}")

    return bed_positions


def write_bed_file(bed_path, bed_positions):
    """Write .bed file in SkinFlaps format.

    Format: vertex_index x y z (one line per vertex, 0-indexed)
    """
    with open(bed_path, 'w') as f:
        for i, pos in enumerate(bed_positions):
            f.write(f"{i} {pos[0]:.6f} {pos[1]:.6f} {pos[2]:.6f}\n")

    return len(bed_positions)


def main():
    parser = argparse.ArgumentParser(
        description="Generate .bed (deep bed) files for SkinFlaps OBJ meshes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_bed.py Model/MyModel.obj                    # default offset=-5.0
  python generate_bed.py Model/MyModel.obj --offset -3.0      # custom offset
  python generate_bed.py Model/Skin.obj --reference Model/DeepBed.obj
"""
    )
    parser.add_argument("input", metavar="INPUT_OBJ",
                        help="Input OBJ file (skin surface)")
    parser.add_argument("--output", "-o", metavar="OUTPUT_BED",
                        help="Output .bed file path (default: same name as input)")
    parser.add_argument("--offset", type=float, default=-5.0,
                        help="Offset distance along normals (default: -5.0, negative=inward)")
    parser.add_argument("--reference", "-r", metavar="DEEP_BED_OBJ",
                        help="Reference deep-bed OBJ for closest-point projection")

    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"ERROR: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    if args.output is None:
        args.output = os.path.splitext(args.input)[0] + ".bed"

    print(f"\n=== Generate .bed File ===")
    print(f"  Input OBJ: {args.input}")
    print(f"  Output:    {args.output}")

    # Parse OBJ
    vertices, normals = parse_obj_vertices_and_normals(args.input)
    print(f"  Vertices:  {len(vertices)}")

    if len(vertices) == 0:
        print("ERROR: OBJ has no vertices")
        sys.exit(1)

    # Generate bed positions
    if args.reference:
        if not os.path.isfile(args.reference):
            print(f"ERROR: Reference file not found: {args.reference}", file=sys.stderr)
            sys.exit(1)
        print(f"\n--- Reference Method ---")
        bed_positions = generate_bed_reference(vertices, args.reference)
    else:
        print(f"\n--- Offset Method (offset={args.offset}) ---")
        bed_positions = generate_bed_offset(vertices, normals, args.offset)

    # Write
    n_written = write_bed_file(args.output, bed_positions)
    print(f"\n  Written {n_written} bed entries to {args.output}")

    # Verify count matches
    if n_written != len(vertices):
        print(f"  WARNING: .bed entries ({n_written}) != OBJ vertices ({len(vertices)})")
        print(f"  This will cause setDeepBed() runtime failure!")
        sys.exit(1)
    else:
        print(f"  [OK] Entry count matches vertex count ({n_written})")

    sys.exit(0)


if __name__ == "__main__":
    main()
