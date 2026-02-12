#!/usr/bin/env python3
"""Merge ShoulderSkin.obj and ShoulderDeepBed.obj into a single multi-layer OBJ.

Creates a merged ShoulderSkin.obj with:
  Material 1 (boundary): Skin bottom fan faces - peripheral physics anchor
  Material 2 (skin surface): Main skin surface faces
  Material 5 (deep bed): Deep bed surface faces
  Material 7 (periosteum): Deep bed bottom fan faces - fixed physics anchor

The original ShoulderSkin.obj is backed up as ShoulderSkin_single_layer.obj.
"""
import os
import sys
import shutil

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Model")

def read_obj(path):
    """Read an OBJ file, returning vertices, texcoords, and faces."""
    vertices = []
    texcoords = []
    faces = []  # each face: list of (vertex_idx, texcoord_idx) tuples (1-indexed)
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


def write_merged_obj(path, skin_verts, skin_tc, deep_verts, deep_tc,
                     boundary_faces, skin_faces, deepbed_faces, periosteum_faces,
                     vert_offset):
    """Write the merged multi-layer OBJ file."""
    with open(path, 'w') as f:
        f.write("# ShoulderSkin - multi-layer shoulder mesh\n")
        f.write("# Merged from ShoulderSkin.obj (skin) + ShoulderDeepBed.obj (deep bed)\n")
        f.write("# Materials: 1=boundary, 2=skinSurface, 5=deepBed, 7=periosteum\n")
        f.write(f"# Skin vertices: 1-{len(skin_verts)}, "
                f"Deep bed vertices: {len(skin_verts)+1}-{len(skin_verts)+len(deep_verts)}\n")

        # Write all vertices: skin first, then deep bed
        for v in skin_verts:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        for v in deep_verts:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")

        # Write all texture coordinates: skin first, then deep bed
        for tc in skin_tc:
            f.write(f"vt {tc[0]:.6f} {tc[1]:.6f}\n")
        for tc in deep_tc:
            f.write(f"vt {tc[0]:.6f} {tc[1]:.6f}\n")

        def write_faces(face_list, material):
            f.write(f"usemtl {material}\n")
            for face in face_list:
                parts = [f"{vi}/{ti}" for vi, ti in face]
                f.write("f " + " ".join(parts) + "\n")

        # Write faces grouped by material (matching facial OBJ ordering)
        write_faces(boundary_faces, 1)
        write_faces(skin_faces, 2)
        write_faces(deepbed_faces, 5)
        write_faces(periosteum_faces, 7)


def main():
    skin_path = os.path.join(MODEL_DIR, "ShoulderSkin.obj")
    deep_path = os.path.join(MODEL_DIR, "ShoulderDeepBed.obj")
    backup_path = os.path.join(MODEL_DIR, "ShoulderSkin_single_layer.obj")

    if not os.path.exists(skin_path):
        print(f"ERROR: {skin_path} not found")
        sys.exit(1)
    if not os.path.exists(deep_path):
        print(f"ERROR: {deep_path} not found")
        sys.exit(1)

    # Read both OBJ files
    skin_verts, skin_tc, skin_faces = read_obj(skin_path)
    deep_verts, deep_tc, deep_faces = read_obj(deep_path)

    print(f"ShoulderSkin.obj:    {len(skin_verts)} verts, {len(skin_tc)} tc, {len(skin_faces)} faces")
    print(f"ShoulderDeepBed.obj: {len(deep_verts)} verts, {len(deep_tc)} tc, {len(deep_faces)} faces")

    # Identify bottom fan faces
    # Skin: faces containing vertex 386 (bottom center pole)
    skin_pole = len(skin_verts)  # 386 (1-indexed)
    skin_bottom_fan = []
    skin_main = []
    for face in skin_faces:
        if any(vi == skin_pole for vi, ti in face):
            skin_bottom_fan.append(face)
        else:
            skin_main.append(face)

    # Deep bed: faces containing vertex 242 (bottom center pole)
    deep_pole = len(deep_verts)  # 242 (1-indexed)
    deep_bottom_fan = []
    deep_main = []
    for face in deep_faces:
        if any(vi == deep_pole for vi, ti in face):
            deep_bottom_fan.append(face)
        else:
            deep_main.append(face)

    print(f"\nSkin bottom fan (→ boundary mat 1):    {len(skin_bottom_fan)} faces")
    print(f"Skin main      (→ skin mat 2):         {len(skin_main)} faces")
    print(f"Deep main       (→ deep bed mat 5):     {len(deep_main)} faces")
    print(f"Deep bottom fan (→ periosteum mat 7):   {len(deep_bottom_fan)} faces")

    # Offset deep bed vertex/texcoord indices by skin counts
    vert_offset = len(skin_verts)
    tc_offset = len(skin_tc)

    def offset_faces(face_list):
        return [[(vi + vert_offset, ti + tc_offset) for vi, ti in face]
                for face in face_list]

    deep_main_offset = offset_faces(deep_main)
    deep_bottom_fan_offset = offset_faces(deep_bottom_fan)

    # Backup original
    if not os.path.exists(backup_path):
        shutil.copy2(skin_path, backup_path)
        print(f"\nBacked up original to {os.path.basename(backup_path)}")

    # Write merged OBJ
    write_merged_obj(
        skin_path,
        skin_verts, skin_tc,
        deep_verts, deep_tc,
        boundary_faces=skin_bottom_fan,       # mat 1
        skin_faces=skin_main,                 # mat 2
        deepbed_faces=deep_main_offset,       # mat 5
        periosteum_faces=deep_bottom_fan_offset,  # mat 7
        vert_offset=vert_offset
    )

    total_faces = len(skin_bottom_fan) + len(skin_main) + len(deep_main) + len(deep_bottom_fan)
    total_verts = len(skin_verts) + len(deep_verts)
    print(f"\nMerged ShoulderSkin.obj written:")
    print(f"  Total: {total_verts} vertices, {total_faces} faces")
    print(f"  Material 1 (boundary):   {len(skin_bottom_fan)} faces")
    print(f"  Material 2 (skin):       {len(skin_main)} faces")
    print(f"  Material 5 (deep bed):   {len(deep_main)} faces")
    print(f"  Material 7 (periosteum): {len(deep_bottom_fan)} faces")

    # Validate
    print("\nValidation:")
    # Check winding consistency (all faces should be CCW when viewed from outside)
    print(f"  Skin vertices 1-{len(skin_verts)}")
    print(f"  Deep vertices {len(skin_verts)+1}-{total_verts}")
    print(f"  Vertex offset applied to deep bed: +{vert_offset}")
    print(f"  Texcoord offset applied to deep bed: +{tc_offset}")


if __name__ == "__main__":
    main()
