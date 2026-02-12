#!/usr/bin/env python3
"""Merge ShoulderSkin.obj and ShoulderDeepBed.obj into a SINGLE CLOSED MANIFOLD.

Phase 3a fix: the previous merge created two disconnected closed shells that
caused 'Solid ordering error' in getConnectedComponents(). This version:

1. Removes bottom caps from both shells (opening them at the y=0 rim)
2. Reverses deep bed face winding (inner surface normals point inward)
3. Adds a boundary strip connecting skin rim to deep bed rim (material 1)
4. Designates deep bed apex fan as periosteum (material 7)

Result: single closed manifold with materials 1, 2, 5, 7.
"""
import math
import os
import sys
import shutil

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Model")


def read_obj(path):
    """Read an OBJ file, returning vertices, texcoords, and faces."""
    vertices = []
    texcoords = []
    faces = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line.startswith('v ') and not line.startswith('vt'):
                parts = line.split()
                vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
            elif line.startswith('vt '):
                parts = line.split()
                texcoords.append((float(parts[1]), float(parts[2])))
            elif line.startswith('f '):
                parts = line.split()[1:]
                face = []
                for p in parts:
                    indices = p.split('/')
                    vi = int(indices[0])
                    ti = int(indices[1]) if len(indices) > 1 and indices[1] else vi
                    face.append((vi, ti))
                faces.append(face)
    return vertices, texcoords, faces


def reverse_face(face):
    """Reverse face winding: swap 2nd and 3rd vertices."""
    return [face[0], face[2], face[1]]


def get_rim_vertices(verts, pole_idx):
    """Find rim vertices at y=0, excluding the pole vertex. Returns sorted by angle."""
    rim = []
    for i, v in enumerate(verts):
        if i == pole_idx:
            continue
        if abs(v[1]) < 0.001 and (abs(v[0]) > 0.1 or abs(v[2]) > 0.1):
            angle = math.atan2(v[2], v[0])
            rim.append((i + 1, angle))  # 1-indexed
    rim.sort(key=lambda x: x[1])
    return rim


def stitch_rims(skin_rim, deep_rim, skin_tc_count, deep_tc_offset):
    """Create triangulated strip connecting two rims of different sizes.

    Both rims are sorted by angle. Uses a zipper algorithm that advances
    whichever rim has the closer next vertex angle-wise.

    Returns list of faces (material 1 boundary) with downward (-Y) normals.
    """
    ns = len(skin_rim)
    nd = len(deep_rim)
    faces = []

    si = 0  # skin index
    di = 0  # deep index

    def next_angle(rim, idx):
        """Get angle of next vertex in the ring (wrapping)."""
        return rim[(idx + 1) % len(rim)][1]

    def angle_diff(a, b):
        """Smallest angular difference."""
        d = (a - b) % (2 * math.pi)
        return min(d, 2 * math.pi - d)

    # Walk around creating triangles
    for _ in range(ns + nd):
        sv = skin_rim[si % ns][0]       # current skin vertex (1-indexed)
        dv = deep_rim[di % nd][0]       # current deep vertex (1-indexed, original)
        dv_off = dv + deep_tc_offset    # deep vertex with offset (for merged file)

        # Use same index for texcoord as vertex (1:1 mapping)
        sv_tc = sv
        dv_tc = dv + deep_tc_offset

        sn = skin_rim[(si + 1) % ns][0]     # next skin vertex
        sn_tc = sn
        dn = deep_rim[(di + 1) % nd][0]     # next deep vertex (original)
        dn_off = dn + deep_tc_offset
        dn_tc = dn + deep_tc_offset

        # Decide: advance skin or deep?
        s_next_angle = skin_rim[(si + 1) % ns][1]
        d_next_angle = deep_rim[(di + 1) % nd][1]
        current_angle = (skin_rim[si % ns][1] + deep_rim[di % nd][1]) / 2

        if si >= ns:
            # Skin ring exhausted, advance deep
            advance_skin = False
        elif di >= nd:
            # Deep ring exhausted, advance skin
            advance_skin = True
        else:
            advance_skin = angle_diff(s_next_angle, current_angle) <= angle_diff(d_next_angle, current_angle)

        if advance_skin:
            # Triangle: skin_curr, next_skin, deep_curr
            # Winding gives -Y normal (downward, away from tissue volume)
            faces.append([
                (sv, sv_tc),
                (sn, sn_tc),
                (dv_off, dv_tc),
            ])
            si += 1
        else:
            # Triangle: skin_curr, deep_next, deep_curr
            faces.append([
                (sv, sv_tc),
                (dn_off, dn_tc),
                (dv_off, dv_tc),
            ])
            di += 1

    return faces


def main():
    # Use single-layer backup as source (the original unmodified skin OBJ)
    skin_source = os.path.join(MODEL_DIR, "ShoulderSkin_single_layer.obj")
    skin_output = os.path.join(MODEL_DIR, "ShoulderSkin.obj")
    deep_path = os.path.join(MODEL_DIR, "ShoulderDeepBed.obj")

    if not os.path.exists(skin_source):
        # First run: backup current ShoulderSkin.obj
        if os.path.exists(skin_output):
            shutil.copy2(skin_output, skin_source)
            print(f"Backed up original to ShoulderSkin_single_layer.obj")
        else:
            print(f"ERROR: Neither {skin_source} nor {skin_output} found")
            sys.exit(1)

    if not os.path.exists(deep_path):
        print(f"ERROR: {deep_path} not found")
        sys.exit(1)

    # Read source OBJ files
    skin_verts, skin_tc, skin_faces = read_obj(skin_source)
    deep_verts, deep_tc, deep_faces = read_obj(deep_path)

    print(f"ShoulderSkin (source): {len(skin_verts)} verts, {len(skin_tc)} tc, {len(skin_faces)} faces")
    print(f"ShoulderDeepBed:      {len(deep_verts)} verts, {len(deep_tc)} tc, {len(deep_faces)} faces")

    # --- Classify skin faces ---
    skin_pole = len(skin_verts)  # vertex 386 (1-indexed), the bottom center pole
    skin_bottom_fan = []  # to be REMOVED (opens the dome)
    skin_main = []        # material 2 (skin surface)
    for face in skin_faces:
        if any(vi == skin_pole for vi, ti in face):
            skin_bottom_fan.append(face)
        else:
            skin_main.append(face)

    # --- Classify deep bed faces ---
    deep_pole_bottom = len(deep_verts)  # vertex 242 (1-indexed), bottom center pole
    deep_pole_apex = 1                  # vertex 1 (1-indexed), top apex at (0, 6, 0)
    deep_bottom_fan = []  # to be REMOVED (opens the dome)
    deep_apex_fan = []    # material 7 (periosteum) - reversed winding
    deep_main = []        # material 5 (deep bed) - reversed winding
    for face in deep_faces:
        if any(vi == deep_pole_bottom for vi, ti in face):
            deep_bottom_fan.append(face)
        elif any(vi == deep_pole_apex for vi, ti in face):
            deep_apex_fan.append(face)
        else:
            deep_main.append(face)

    print(f"\n--- Face classification ---")
    print(f"Skin bottom fan (REMOVED):   {len(skin_bottom_fan)} faces")
    print(f"Skin main (mat 2):           {len(skin_main)} faces")
    print(f"Deep bottom fan (REMOVED):   {len(deep_bottom_fan)} faces")
    print(f"Deep apex fan (mat 7):       {len(deep_apex_fan)} faces")
    print(f"Deep main (mat 5):           {len(deep_main)} faces")

    # --- Remove unused pole vertices ---
    # Skin pole (last vertex, at origin) and deep bed bottom pole (last vertex)
    # are not referenced by any face after removing bottom cap fans.
    # Removing them gives exact Euler V-E+F = 2 for a closed genus-0 manifold.
    skin_verts_out = skin_verts[:-1]   # 385 vertices (exclude skin pole)
    skin_tc_out = skin_tc[:-1]         # 385 texcoords
    deep_verts_out = deep_verts[:-1]   # 241 vertices (exclude bottom pole)
    deep_tc_out = deep_tc[:-1]         # 241 texcoords

    print(f"\n--- Pole vertex removal ---")
    print(f"Skin pole v{len(skin_verts)} at {skin_verts[-1]} REMOVED")
    print(f"Deep bed pole v{len(deep_verts)} at {deep_verts[-1]} REMOVED")
    print(f"Skin: {len(skin_verts)} -> {len(skin_verts_out)} verts")
    print(f"Deep: {len(deep_verts)} -> {len(deep_verts_out)} verts")

    # --- Offset deep bed indices ---
    vert_offset = len(skin_verts_out)  # 385
    tc_offset = len(skin_tc_out)       # 385

    def offset_faces(face_list):
        return [[(vi + vert_offset, ti + tc_offset) for vi, ti in face]
                for face in face_list]

    # Reverse winding on deep bed faces (inner surface normals point inward)
    deep_main_reversed = [reverse_face(f) for f in deep_main]
    deep_apex_reversed = [reverse_face(f) for f in deep_apex_fan]

    # Apply offset after reversing
    deep_main_offset = offset_faces(deep_main_reversed)
    deep_apex_offset = offset_faces(deep_apex_reversed)

    # --- Create boundary strip connecting skin rim to deep bed rim ---
    # Skin rim: 24 vertices at y=0 (excluding pole v386)
    skin_rim = get_rim_vertices(skin_verts, skin_pole - 1)  # 0-indexed for lookup
    # Deep bed rim: 20 vertices at y=0 (excluding pole v242)
    deep_rim = get_rim_vertices(deep_verts, deep_pole_bottom - 1)

    print(f"\n--- Rim analysis ---")
    print(f"Skin rim: {len(skin_rim)} vertices")
    print(f"Deep rim: {len(deep_rim)} vertices")

    boundary_strip = stitch_rims(skin_rim, deep_rim, len(skin_tc_out), vert_offset)
    print(f"Boundary strip: {len(boundary_strip)} faces")

    # --- Write merged OBJ ---
    total_verts = len(skin_verts_out) + len(deep_verts_out)
    total_tc = len(skin_tc_out) + len(deep_tc_out)

    with open(skin_output, 'w') as f:
        f.write("# ShoulderSkin - single closed manifold (multi-layer)\n")
        f.write("# Merged from ShoulderSkin.obj (skin) + ShoulderDeepBed.obj (deep bed)\n")
        f.write("# Materials: 1=boundary(strip), 2=skinSurface, 5=deepBed(reversed), 7=periosteum(reversed)\n")
        f.write(f"# Skin vertices: 1-{len(skin_verts_out)}, "
                f"Deep bed vertices: {len(skin_verts_out)+1}-{total_verts}\n")
        f.write("# Single connected manifold: skin rim connected to deep bed rim via boundary strip\n")

        # Vertices (excluding unused pole vertices)
        for v in skin_verts_out:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        for v in deep_verts_out:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")

        # Texture coordinates (excluding unused pole texcoords)
        for tc in skin_tc_out:
            f.write(f"vt {tc[0]:.6f} {tc[1]:.6f}\n")
        for tc in deep_tc_out:
            f.write(f"vt {tc[0]:.6f} {tc[1]:.6f}\n")

        def write_faces(face_list, material):
            f.write(f"usemtl {material}\n")
            for face in face_list:
                parts = [f"{vi}/{ti}" for vi, ti in face]
                f.write("f " + " ".join(parts) + "\n")

        write_faces(boundary_strip, 1)           # boundary strip
        write_faces(skin_main, 2)                # skin surface
        write_faces(deep_main_offset, 5)         # deep bed (reversed winding)
        write_faces(deep_apex_offset, 7)         # periosteum (reversed winding)

    n_boundary = len(boundary_strip)
    n_skin = len(skin_main)
    n_deepbed = len(deep_main_offset)
    n_perio = len(deep_apex_offset)
    total_faces = n_boundary + n_skin + n_deepbed + n_perio

    print(f"\n--- Merged ShoulderSkin.obj ---")
    print(f"  Total: {total_verts} vertices, {total_faces} faces")
    print(f"  Material 1 (boundary strip): {n_boundary} faces")
    print(f"  Material 2 (skin surface):   {n_skin} faces")
    print(f"  Material 5 (deep bed):       {n_deepbed} faces")
    print(f"  Material 7 (periosteum):     {n_perio} faces")

    # --- Update .bed file (remove entry for removed skin pole vertex) ---
    bed_path = os.path.join(MODEL_DIR, "ShoulderSkin.bed")
    if os.path.exists(bed_path):
        with open(bed_path) as bf:
            bed_lines = bf.readlines()
        # Keep only entries for vertices that still exist (0-based index < skin_verts_out count)
        n_skin_verts = len(skin_verts_out)
        new_bed_lines = []
        for line in bed_lines:
            line = line.strip()
            if not line:
                continue
            idx = int(line.split()[0])
            if idx < n_skin_verts:
                new_bed_lines.append(line)
        with open(bed_path, 'w') as bf:
            for line in new_bed_lines:
                bf.write(line + '\n')
        print(f"\n--- Updated ShoulderSkin.bed ---")
        print(f"  Entries: {len(new_bed_lines)} (was {len(bed_lines)}, "
              f"removed pole vertex entry)")

    # --- Print expected Euler characteristic ---
    expected_euler = total_verts - (3 * total_faces // 2) + total_faces
    print(f"\n--- Expected topology ---")
    print(f"  V={total_verts}, F={total_faces}, E≈{3*total_faces//2}")
    print(f"  Euler V-E+F ≈ {expected_euler} (expect 2 for closed genus-0)")


if __name__ == "__main__":
    main()
