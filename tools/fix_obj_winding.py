#!/usr/bin/env python3
"""
Fix OBJ winding order for SkinFlaps compatibility.

The SkinFlaps loader (materialTriangles::findAdjacentTriangles) requires
that shared edges between adjacent triangles are traversed in OPPOSITE
directions. This script detects and fixes faces with inconsistent winding
by flipping vertex order of problematic triangles.

Algorithm:
  1. Parse all faces from the OBJ file
  2. Build an edge adjacency map
  3. BFS from face 0, marking each face's expected orientation
  4. Flip faces that need reversal
  5. Write corrected OBJ back

Usage:
  python fix_obj_winding.py <file.obj> [file2.obj ...]
  python fix_obj_winding.py --dir <directory>
"""

import argparse
import os
import sys
from collections import defaultdict, deque


def parse_obj_faces(lines):
    """Parse OBJ lines and extract face data.

    Returns:
        faces: list of (line_index, vertex_tokens) where vertex_tokens is
               the list of face vertex strings (e.g., ['1/1', '2/2', '3/3'])
        face_pos_indices: list of lists of 0-based position indices per face
    """
    faces = []
    face_pos_indices = []

    for line_idx, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue
        tokens = line.split()
        if tokens[0] != 'f':
            continue
        vtx_tokens = tokens[1:]
        if len(vtx_tokens) < 3:
            continue

        pos_indices = []
        for tok in vtx_tokens:
            parts = tok.split('/')
            pos_indices.append(int(parts[0]) - 1)  # 0-based

        if len(vtx_tokens) == 3:
            faces.append((line_idx, vtx_tokens))
            face_pos_indices.append(pos_indices)
        elif len(vtx_tokens) == 4:
            # Quad: split into two triangles same as C++ loader
            # Tri 1: 0,1,2  Tri 2: 2,3,0
            faces.append((line_idx, vtx_tokens[:3]))
            face_pos_indices.append(pos_indices[:3])
            faces.append((line_idx, [vtx_tokens[2], vtx_tokens[3], vtx_tokens[0]]))
            face_pos_indices.append([pos_indices[2], pos_indices[3], pos_indices[0]])

    return faces, face_pos_indices


def build_edge_adjacency(face_pos_indices):
    """Build edge-to-face adjacency map.

    Returns:
        edge_faces: dict mapping canonical_edge -> list of (face_idx, is_reversed)
            where canonical_edge = (min_vertex, max_vertex)
            and is_reversed indicates if the face traverses the edge in reverse
    """
    edge_faces = defaultdict(list)

    for face_idx, pos_indices in enumerate(face_pos_indices):
        n = len(pos_indices)
        for j in range(n):
            a = pos_indices[j]
            b = pos_indices[(j + 1) % n]
            if a < b:
                canonical = (a, b)
                is_reversed = False
            else:
                canonical = (b, a)
                is_reversed = True
            edge_faces[canonical].append((face_idx, is_reversed))

    return edge_faces


def compute_flips(face_pos_indices):
    """Determine which faces need flipping using BFS orientation propagation.

    Returns:
        flip_set: set of face indices that need their vertex order reversed
        n_components: number of connected components
        n_conflicts: number of edge orientation conflicts found
    """
    n_faces = len(face_pos_indices)
    if n_faces == 0:
        return set(), 0, 0

    edge_faces = build_edge_adjacency(face_pos_indices)

    # Build face-to-face adjacency with orientation info
    # For each face, list of (neighbor_face_idx, same_direction)
    # same_direction=True means the shared edge is traversed the same way (BAD)
    face_neighbors = defaultdict(list)
    for canonical, entries in edge_faces.items():
        if len(entries) == 2:
            f1, rev1 = entries[0]
            f2, rev2 = entries[1]
            # If both traverse the edge in the same direction, they conflict
            same_dir = (rev1 == rev2)
            face_neighbors[f1].append((f2, same_dir))
            face_neighbors[f2].append((f1, same_dir))

    # BFS to assign orientations
    orientation = [None] * n_faces  # True = keep, False = flip
    flip_set = set()
    n_components = 0
    n_conflicts = 0

    for start_face in range(n_faces):
        if orientation[start_face] is not None:
            continue
        n_components += 1
        orientation[start_face] = True  # keep first face as reference
        queue = deque([start_face])

        while queue:
            fi = queue.popleft()
            for neighbor, same_dir in face_neighbors[fi]:
                if orientation[neighbor] is not None:
                    # Check for consistency
                    expected = (not orientation[fi]) if same_dir else orientation[fi]
                    if orientation[neighbor] != expected:
                        n_conflicts += 1
                    continue
                # If edges go same direction, neighbor should be opposite orientation
                if same_dir:
                    orientation[neighbor] = not orientation[fi]
                else:
                    orientation[neighbor] = orientation[fi]
                if not orientation[neighbor]:
                    flip_set.add(neighbor)
                queue.append(neighbor)

    return flip_set, n_components, n_conflicts


def fix_obj_winding(filepath):
    """Fix winding order in an OBJ file.

    Returns:
        (n_flipped, n_total, n_conflicts) tuple
    """
    with open(filepath, 'r') as f:
        lines = f.readlines()

    faces, face_pos_indices = parse_obj_faces(lines)
    if not faces:
        return 0, 0, 0

    flip_set, n_components, n_conflicts = compute_flips(face_pos_indices)

    if not flip_set:
        return 0, len(faces), n_conflicts

    # Apply flips to the original lines
    # Group faces by their original line index (quads produce 2 faces from 1 line)
    line_face_map = defaultdict(list)
    for face_idx, (line_idx, vtx_tokens) in enumerate(faces):
        line_face_map[line_idx].append((face_idx, vtx_tokens))

    # Track which original lines need modification
    modified_lines = {}
    for line_idx, face_entries in line_face_map.items():
        if len(face_entries) == 1:
            # Single triangle face line
            face_idx, vtx_tokens = face_entries[0]
            if face_idx in flip_set:
                # Reverse vertex order: swap v1 and v2 (keep v0, swap the other two)
                # Actually, just reverse the entire vertex list
                flipped = list(reversed(vtx_tokens))
                modified_lines[line_idx] = "f " + " ".join(flipped) + "\n"
        elif len(face_entries) == 2:
            # This was a quad that got split into 2 triangles
            # We need to handle the original quad line
            # Parse original line to get the 4 vertices
            orig_line = lines[line_idx].strip()
            orig_tokens = orig_line.split()
            if orig_tokens[0] == 'f' and len(orig_tokens) == 5:
                # Quad: check if either split triangle needs flipping
                f1_idx = face_entries[0][0]
                f2_idx = face_entries[1][0]
                # If both triangles of a quad need flipping, flip the whole quad
                if f1_idx in flip_set and f2_idx in flip_set:
                    flipped = list(reversed(orig_tokens[1:]))
                    modified_lines[line_idx] = "f " + " ".join(flipped) + "\n"
                elif f1_idx in flip_set or f2_idx in flip_set:
                    # Only one triangle of quad needs flip - this is unusual
                    # Just flip the whole quad as both come from same source
                    flipped = list(reversed(orig_tokens[1:]))
                    modified_lines[line_idx] = "f " + " ".join(flipped) + "\n"

    # Write modified file
    for line_idx, new_content in modified_lines.items():
        lines[line_idx] = new_content

    with open(filepath, 'w') as f:
        f.writelines(lines)

    return len(flip_set), len(faces), n_conflicts


def main():
    parser = argparse.ArgumentParser(
        description="Fix OBJ winding order for SkinFlaps compatibility."
    )
    parser.add_argument("files", nargs="*", metavar="FILE",
                        help="OBJ file(s) to fix")
    parser.add_argument("--dir", "-d", metavar="DIRECTORY",
                        help="Fix all .obj files in the given directory")
    parser.add_argument("--dry-run", action="store_true",
                        help="Only report issues, don't modify files")
    args = parser.parse_args()

    obj_files = list(args.files) if args.files else []
    if args.dir:
        for entry in sorted(os.listdir(args.dir)):
            if entry.lower().endswith(".obj"):
                obj_files.append(os.path.join(args.dir, entry))

    if not obj_files:
        parser.print_help()
        sys.exit(1)

    total_flipped = 0
    for filepath in obj_files:
        if args.dry_run:
            # Parse and analyze only
            with open(filepath, 'r') as f:
                lines = f.readlines()
            faces, face_pos_indices = parse_obj_faces(lines)
            flip_set, n_comp, n_conflicts = compute_flips(face_pos_indices)
            n_flipped = len(flip_set)
            n_total = len(faces)
        else:
            n_flipped, n_total, n_conflicts = fix_obj_winding(filepath)

        if n_flipped > 0:
            action = "would flip" if args.dry_run else "flipped"
            print(f"[FIXED] {filepath}: {action} {n_flipped}/{n_total} faces"
                  f" ({n_conflicts} residual conflicts)")
            total_flipped += n_flipped
        else:
            print(f"[OK] {filepath}: all {n_total} faces consistent")

    if total_flipped > 0 and not args.dry_run:
        print(f"\nTotal: {total_flipped} faces flipped across {len(obj_files)} files")
    elif total_flipped > 0:
        print(f"\nDry run: {total_flipped} faces would be flipped")


if __name__ == "__main__":
    main()
