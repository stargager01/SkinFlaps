#!/usr/bin/env python3
"""
OBJ file validator for SkinFlaps surgical simulator.

Validates OBJ files against the requirements of the SkinFlaps OBJ loader
(gl3wGraphics/materialTriangles.cpp), including:
  - Texture coordinates (vt) must be present before any faces
  - Faces must be triangles in v/vt format
  - Material assignment (usemtl <integer>) before face groups
  - Smoothing group (s <integer>) before faces
  - Consistent winding order (manifold edge check from findAdjacentTriangles)

Exit codes:
  0 - All files pass validation
  1 - One or more files failed validation

Usage:
  python validate_obj.py <file1.obj> [file2.obj ...]
  python validate_obj.py --dir <directory>
  python validate_obj.py --strict <file.obj>
"""

import argparse
import os
import sys
from collections import defaultdict


class ObjValidationResult:
    """Holds validation results for a single OBJ file."""

    def __init__(self, filepath):
        self.filepath = filepath
        self.errors = []    # (line_number, error_code, message)
        self.warnings = []  # (line_number, message)
        self.vertex_count = 0
        self.texcoord_count = 0
        self.face_count = 0

    @property
    def passed(self):
        return len(self.errors) == 0

    def add_error(self, line_num, code, message):
        self.errors.append((line_num, code, message))

    def add_warning(self, line_num, message):
        self.warnings.append((line_num, message))

    def summary(self):
        lines = []
        status = "PASS" if self.passed else "FAIL"
        lines.append(f"[{status}] {self.filepath}")
        lines.append(f"  Vertices: {self.vertex_count}, "
                     f"TexCoords: {self.texcoord_count}, "
                     f"Faces: {self.face_count}")
        for line_num, code, msg in self.errors:
            lines.append(f"  ERROR (code {code}) line {line_num}: {msg}")
        for line_num, msg in self.warnings:
            lines.append(f"  WARNING line {line_num}: {msg}")
        return "\n".join(lines)


def parse_face_vertex(token):
    """Parse a face vertex token like 'v/vt' or 'v/vt/vn'.

    Returns (position_index, texture_index) as 0-based integers,
    or raises ValueError if the format is invalid.
    """
    parts = token.split("/")
    if len(parts) < 2 or parts[1] == "":
        raise ValueError(f"Face vertex '{token}' missing texture coordinate index")
    pos_idx = int(parts[0]) - 1  # OBJ indices are 1-based
    tex_idx = int(parts[1]) - 1
    return pos_idx, tex_idx


def check_winding_order(faces, result):
    """Check manifold winding order using the findAdjacentTriangles algorithm.

    For each edge shared by two triangles, the edge must be traversed in
    opposite directions. An edge from vertex A to B in one triangle must
    appear as B to A in the adjacent triangle.

    This mirrors the C++ logic in materialTriangles::findAdjacentTriangles()
    (gl3wGraphics/materialTriangles.cpp lines 314-378).
    """
    # edge_map: canonical_edge -> (reversed_flag, face_index, edge_index, face_line_number)
    edge_map = {}

    for face_idx, (verts, face_line_num) in enumerate(faces):
        v0, v1, v2 = verts[0], verts[1], verts[2]
        tri = [v0, v1, v2]

        for j in range(3):
            a = tri[j]
            b = tri[(j + 1) % 3]

            if b < a:
                vtx_min = b
                vtx_max = a
                reversed_flag = 1
            else:
                vtx_min = a
                vtx_max = b
                reversed_flag = 0

            canonical = (vtx_min, vtx_max)

            if canonical in edge_map:
                prev_reversed, prev_face, prev_edge, prev_line = edge_map[canonical]
                if prev_reversed == reversed_flag and vtx_min != vtx_max:
                    result.add_error(
                        face_line_num, 7,
                        f"Triangle ordering error: edge ({vtx_min+1},{vtx_max+1}) "
                        f"in face {face_idx+1} (line {face_line_num}) has same winding "
                        f"as face {prev_face+1} (line {prev_line})")
                # Edge matched, remove from map (as the C++ code does with M.erase)
                del edge_map[canonical]
            else:
                edge_map[canonical] = (reversed_flag, face_idx, j, face_line_num)


def validate_obj(filepath):
    """Validate a single OBJ file against SkinFlaps loader requirements.

    Returns an ObjValidationResult.
    """
    result = ObjValidationResult(filepath)

    if not os.path.isfile(filepath):
        result.add_error(0, 1, f"File not found: {filepath}")
        return result

    try:
        with open(filepath, "r") as f:
            lines = f.readlines()
    except (IOError, OSError) as e:
        result.add_error(0, 1, f"Cannot open file: {e}")
        return result

    has_texcoords = False
    has_usemtl = False
    has_smoothing_group = False
    first_face_line = None

    # Collect faces for winding order check: list of (position_indices, line_number)
    faces = []

    for line_num_0based, raw_line in enumerate(lines):
        line_num = line_num_0based + 1
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        tokens = line.split()
        keyword = tokens[0]

        if keyword == "v":
            if len(tokens) != 4:
                result.add_error(line_num, 3,
                                 f"Vertex line must have exactly 3 coordinates, "
                                 f"got {len(tokens) - 1}")
                continue
            # Validate that coordinates are valid floats
            for i in range(1, 4):
                try:
                    float(tokens[i])
                except ValueError:
                    result.add_error(line_num, 3,
                                     f"Invalid vertex coordinate: '{tokens[i]}'")
            result.vertex_count += 1

        elif keyword == "vt":
            if len(tokens) != 3:
                result.add_error(line_num, 4,
                                 f"Texture coordinate line must have exactly 2 values, "
                                 f"got {len(tokens) - 1}")
                continue
            for i in range(1, 3):
                try:
                    float(tokens[i])
                except ValueError:
                    result.add_error(line_num, 4,
                                     f"Invalid texture coordinate: '{tokens[i]}'")
            has_texcoords = True
            result.texcoord_count += 1

        elif keyword == "usemtl":
            if len(tokens) != 2:
                result.add_error(line_num, 3,
                                 f"usemtl line must have exactly 1 argument, "
                                 f"got {len(tokens) - 1}")
                continue
            try:
                int(tokens[1])
            except ValueError:
                result.add_error(line_num, 5,
                                 f"usemtl argument must be an integer, "
                                 f"got '{tokens[1]}'")
            has_usemtl = True

        elif keyword == "s":
            if len(tokens) != 2:
                result.add_warning(line_num,
                                   "Smoothing group line should have exactly 1 argument")
                continue
            try:
                sg = int(tokens[1])
                if sg < 0:
                    result.add_warning(line_num,
                                       f"Smoothing group should be non-negative, got {sg}")
            except ValueError:
                if tokens[1].lower() != "off":
                    result.add_warning(line_num,
                                       f"Smoothing group should be an integer or 'off', "
                                       f"got '{tokens[1]}'")
            has_smoothing_group = True

        elif keyword == "f":
            if first_face_line is None:
                first_face_line = line_num

            # Check that texture coordinates exist before faces
            if not has_texcoords:
                result.add_error(line_num, 4,
                                 "No texture coordinates (vt) found before face definitions")
                # Only report this once, then set flag to avoid repeats
                has_texcoords = True  # suppress further identical errors

            num_verts = len(tokens) - 1

            # SkinFlaps loader allows triangles and quads (quads are tessellated),
            # but rejects polygons with >4 vertices (error code 2)
            if num_verts > 4:
                result.add_error(line_num, 2,
                                 f"Polygon with {num_verts} vertices not supported "
                                 f"(max 4, triangles preferred)")
                continue

            if num_verts < 3:
                result.add_error(line_num, 2,
                                 f"Face must have at least 3 vertices, got {num_verts}")
                continue

            # Parse each face vertex token
            pos_indices = []
            valid_face = True
            for i in range(1, len(tokens)):
                try:
                    pos_idx, tex_idx = parse_face_vertex(tokens[i])
                    pos_indices.append(pos_idx)
                except ValueError as e:
                    result.add_error(line_num, 5, str(e))
                    valid_face = False
                    break

            if not valid_face:
                continue

            # Validate index ranges
            for i, pidx in enumerate(pos_indices):
                if pidx < 0 or pidx >= result.vertex_count:
                    result.add_error(line_num, 5,
                                     f"Vertex position index {pidx+1} out of range "
                                     f"(1..{result.vertex_count})")
                    valid_face = False
            for i in range(1, len(tokens)):
                try:
                    _, tidx = parse_face_vertex(tokens[i])
                    if tidx < 0 or tidx >= result.texcoord_count:
                        result.add_error(line_num, 5,
                                         f"Texture coordinate index {tidx+1} out of range "
                                         f"(1..{result.texcoord_count})")
                        valid_face = False
                except ValueError:
                    pass  # already reported above

            if valid_face:
                if num_verts == 3:
                    faces.append((pos_indices, line_num))
                    result.face_count += 1
                elif num_verts == 4:
                    # Tessellate quad into two triangles, same as the C++ loader
                    # Triangle 1: verts 0,1,2
                    faces.append((pos_indices[:3], line_num))
                    # Triangle 2: verts 2,3,0
                    faces.append(([pos_indices[2], pos_indices[3], pos_indices[0]],
                                  line_num))
                    result.face_count += 2

        # Ignore other OBJ keywords (vn, mtllib, o, g, etc.)

    # Post-parse checks
    if result.vertex_count == 0:
        result.add_error(0, 3, "File contains no vertices")

    if result.texcoord_count == 0:
        result.add_error(0, 4, "File contains no texture coordinates")

    if result.face_count == 0:
        result.add_error(0, 2, "File contains no faces")

    if not has_usemtl and result.face_count > 0:
        result.add_warning(0, "No 'usemtl' directive found before faces "
                           "(material assignment missing)")

    if not has_smoothing_group and result.face_count > 0:
        result.add_warning(0, "No 's' (smoothing group) directive found before faces")

    if result.vertex_count > 0x3FFFFFFF:
        result.add_error(0, 6,
                         f"Vertex count {result.vertex_count} exceeds limit "
                         f"of {0x3FFFFFFF}")

    # Check winding order (only if we have faces and no critical parse errors)
    if faces and not any(code in (2, 3, 4, 5) for _, code, _ in result.errors):
        check_winding_order(faces, result)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Validate OBJ files for SkinFlaps surgical simulator compatibility.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("files", nargs="*", metavar="FILE",
                        help="OBJ file(s) to validate")
    parser.add_argument("--dir", "-d", metavar="DIRECTORY",
                        help="Validate all .obj files in the given directory")
    parser.add_argument("--strict", action="store_true",
                        help="Treat warnings as errors (fail on warnings)")
    args = parser.parse_args()

    obj_files = list(args.files) if args.files else []

    if args.dir:
        if not os.path.isdir(args.dir):
            print(f"Error: '{args.dir}' is not a directory", file=sys.stderr)
            sys.exit(1)
        for entry in sorted(os.listdir(args.dir)):
            if entry.lower().endswith(".obj"):
                obj_files.append(os.path.join(args.dir, entry))

    if not obj_files:
        parser.print_help()
        print("\nError: No OBJ files specified.", file=sys.stderr)
        sys.exit(1)

    all_passed = True
    results = []

    for filepath in obj_files:
        result = validate_obj(filepath)
        results.append(result)

        if not result.passed:
            all_passed = False
        elif args.strict and result.warnings:
            all_passed = False

    # Print results
    print("=" * 60)
    print("SkinFlaps OBJ Validation Report")
    print("=" * 60)

    for result in results:
        print()
        print(result.summary())
        if args.strict and result.warnings and result.passed:
            print("  ** STRICT MODE: warnings treated as errors **")

    print()
    print("-" * 60)
    total = len(results)
    passed = sum(1 for r in results if r.passed and
                 (not args.strict or not r.warnings))
    failed = total - passed
    print(f"Total: {total} file(s), {passed} passed, {failed} failed")

    if args.strict:
        print("(strict mode: warnings treated as errors)")

    if all_passed:
        print("Result: ALL PASSED")
        sys.exit(0)
    else:
        print("Result: FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
