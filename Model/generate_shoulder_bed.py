#!/usr/bin/env python3
"""
Generate ShoulderSkin.bed from ShoulderSkin.obj and ShoulderDeepBed.obj.

The .bed file maps each skin surface vertex (material 2) to the nearest
spatial point on the deep bed surface (ShoulderDeepBed.obj).

Format: one line per skin vertex
    vertex_id x y z
where vertex_id is the 0-based vertex index (OBJ 1-based minus 1),
and (x, y, z) are the world-space coordinates of the closest point
on the deep bed surface.
"""

import math
import os
import sys


def parse_obj_vertices(filepath):
    """Parse all 'v' lines from an OBJ file, returning a list of (x, y, z) tuples."""
    vertices = []
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("v "):
                parts = line.split()
                if len(parts) >= 4:
                    vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
    return vertices


def parse_obj_faces(filepath):
    """Parse all 'f' lines from an OBJ file, returning a list of triangle index tuples (0-based)."""
    faces = []
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("f "):
                parts = line.split()[1:]
                # OBJ face indices are 1-based; may include texture/normal refs like v/vt or v/vt/vn
                indices = []
                for p in parts:
                    vid = int(p.split("/")[0]) - 1  # convert to 0-based
                    indices.append(vid)
                if len(indices) == 3:
                    faces.append(tuple(indices))
                elif len(indices) == 4:
                    # Tessellate quad into two triangles
                    faces.append((indices[0], indices[1], indices[2]))
                    faces.append((indices[0], indices[2], indices[3]))
    return faces


def vec_sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def vec_add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def vec_scale(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def vec_dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def vec_cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def vec_length_sq(a):
    return a[0] * a[0] + a[1] * a[1] + a[2] * a[2]


def closest_point_on_triangle(p, v0, v1, v2):
    """
    Find the closest point on triangle (v0, v1, v2) to point p.
    Returns (closest_point, squared_distance).
    Uses the robust algorithm from Ericson, "Real-Time Collision Detection".
    """
    ab = vec_sub(v1, v0)
    ac = vec_sub(v2, v0)
    ap = vec_sub(p, v0)

    d1 = vec_dot(ab, ap)
    d2 = vec_dot(ac, ap)
    if d1 <= 0.0 and d2 <= 0.0:
        return v0, vec_length_sq(vec_sub(p, v0))

    bp = vec_sub(p, v1)
    d3 = vec_dot(ab, bp)
    d4 = vec_dot(ac, bp)
    if d3 >= 0.0 and d4 <= d3:
        return v1, vec_length_sq(vec_sub(p, v1))

    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        v = d1 / (d1 - d3)
        pt = vec_add(v0, vec_scale(ab, v))
        return pt, vec_length_sq(vec_sub(p, pt))

    cp = vec_sub(p, v2)
    d5 = vec_dot(ab, cp)
    d6 = vec_dot(ac, cp)
    if d6 >= 0.0 and d5 <= d6:
        return v2, vec_length_sq(vec_sub(p, v2))

    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        w = d2 / (d2 - d6)
        pt = vec_add(v0, vec_scale(ac, w))
        return pt, vec_length_sq(vec_sub(p, pt))

    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        w = (d4 - d3) / ((d4 - d3) + (d5 - d6))
        pt = vec_add(v1, vec_scale(vec_sub(v2, v1), w))
        return pt, vec_length_sq(vec_sub(p, pt))

    denom = 1.0 / (va + vb + vc)
    v = vb * denom
    w = vc * denom
    pt = vec_add(v0, vec_add(vec_scale(ab, v), vec_scale(ac, w)))
    return pt, vec_length_sq(vec_sub(p, pt))


def find_nearest_surface_point(point, bed_vertices, bed_faces):
    """
    Find the nearest point on the deep bed surface to the given point.
    Returns the (x, y, z) of the closest surface point.
    """
    best_pt = None
    best_dist_sq = float("inf")

    for face in bed_faces:
        v0 = bed_vertices[face[0]]
        v1 = bed_vertices[face[1]]
        v2 = bed_vertices[face[2]]
        pt, dist_sq = closest_point_on_triangle(point, v0, v1, v2)
        if dist_sq < best_dist_sq:
            best_dist_sq = dist_sq
            best_pt = pt

    return best_pt, math.sqrt(best_dist_sq)


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))

    skin_obj_path = os.path.join(script_dir, "ShoulderSkin.obj")
    deepbed_obj_path = os.path.join(script_dir, "ShoulderDeepBed.obj")
    output_bed_path = os.path.join(script_dir, "ShoulderSkin.bed")

    if not os.path.isfile(skin_obj_path):
        print(f"Error: {skin_obj_path} not found.", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(deepbed_obj_path):
        print(f"Error: {deepbed_obj_path} not found.", file=sys.stderr)
        sys.exit(1)

    print(f"Reading skin vertices from {skin_obj_path} ...")
    skin_vertices = parse_obj_vertices(skin_obj_path)
    print(f"  Found {len(skin_vertices)} skin vertices.")

    print(f"Reading deep bed mesh from {deepbed_obj_path} ...")
    bed_vertices = parse_obj_vertices(deepbed_obj_path)
    bed_faces = parse_obj_faces(deepbed_obj_path)
    print(f"  Found {len(bed_vertices)} vertices, {len(bed_faces)} triangles.")

    print(f"Computing nearest deep bed surface points for {len(skin_vertices)} skin vertices ...")
    results = []
    max_dist = 0.0
    min_dist = float("inf")
    total_dist = 0.0

    for i, sv in enumerate(skin_vertices):
        nearest_pt, dist = find_nearest_surface_point(sv, bed_vertices, bed_faces)
        # vertex_id is 0-based (OBJ 1-based index minus 1)
        results.append((i, nearest_pt[0], nearest_pt[1], nearest_pt[2]))
        max_dist = max(max_dist, dist)
        min_dist = min(min_dist, dist)
        total_dist += dist
        if (i + 1) % 50 == 0 or (i + 1) == len(skin_vertices):
            print(f"  Processed {i + 1}/{len(skin_vertices)} vertices ...")

    avg_dist = total_dist / len(skin_vertices) if skin_vertices else 0.0
    print(f"  Distance stats: min={min_dist:.6f}, max={max_dist:.6f}, avg={avg_dist:.6f}")

    print(f"Writing {output_bed_path} ...")
    with open(output_bed_path, "w") as f:
        for vid, x, y, z in results:
            f.write(f"{vid} {x:.6f} {y:.6f} {z:.6f}\n")

    print(f"Done. Generated {len(results)} entries in {output_bed_path}")


if __name__ == "__main__":
    main()
