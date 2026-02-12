#!/usr/bin/env python3
"""Assign material regions to ShoulderSkin.obj for BCC tet cutter compatibility.

Phase 3b: The BCC tet cutter (vnBccTetCutter_tbb.cpp) requires a SINGLE closed
surface to define one solid volume. The previous dual-layer approach (merging
skin + deep bed into one manifold) created thin-shell geometry that caused
'Solid ordering error' in getConnectedComponents().

The correct approach matches the facial model (unilatCompleteCleft.obj):
  - Single closed surface with materials 1, 2, 7 ONLY
  - Deep bed defined via .bed file coordinates (NOT as OBJ faces)
  - Material 5 (deepBed) is assigned dynamically during cutting, not in OBJ

This script takes the original single-shell ShoulderSkin dome and assigns:
  - Material 1 (boundary):   bottom fan faces at y=0 rim (peripheral anchors)
  - Material 2 (skinSurface): main body faces (deformable tissue)
  - Material 7 (periosteum):  top fan faces near apex (fixed bone anchors)

Result: 386 vertices, 768 faces, single closed genus-0 manifold.
"""
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


def main():
    skin_output = os.path.join(MODEL_DIR, "ShoulderSkin.obj")

    # Use existing ShoulderSkin.obj as input (assign material regions in-place)
    skin_source = skin_output
    if not os.path.exists(skin_source):
        print(f"ERROR: {skin_source} not found")
        sys.exit(1)

    # Read source OBJ (single-layer dome: 386 verts, 768 faces, all material 2)
    verts, texcoords, faces = read_obj(skin_source)
    print(f"Source: {len(verts)} verts, {len(texcoords)} tc, {len(faces)} faces")

    # Identify special vertices:
    #   v1 (1-indexed) = top apex at (0, ~6, 0)
    #   v386 (1-indexed) = bottom pole at (0, 0, 0)
    top_apex = 1           # 1-indexed
    bottom_pole = len(verts)  # 386, 1-indexed

    # Classify faces by region
    bottom_fan = []    # faces touching bottom pole -> material 1 (boundary)
    top_fan = []       # faces touching top apex -> material 7 (periosteum)
    skin_main = []     # everything else -> material 2 (skin surface)

    for face in faces:
        vis = [vi for vi, ti in face]
        if bottom_pole in vis:
            bottom_fan.append(face)
        elif top_apex in vis:
            top_fan.append(face)
        else:
            skin_main.append(face)

    print(f"\n--- Face classification ---")
    print(f"Bottom fan (mat 1 boundary):   {len(bottom_fan)} faces")
    print(f"Skin main  (mat 2 skin):       {len(skin_main)} faces")
    print(f"Top fan    (mat 7 periosteum): {len(top_fan)} faces")
    total_classified = len(bottom_fan) + len(skin_main) + len(top_fan)
    print(f"Total classified: {total_classified} (source: {len(faces)})")
    assert total_classified == len(faces), "Face classification mismatch!"

    # Write output OBJ with material regions
    with open(skin_output, 'w') as f:
        f.write("# ShoulderSkin - single closed surface with material regions\n")
        f.write("# Matches facial model architecture (single solid boundary)\n")
        f.write("# Materials: 1=boundary(bottom rim), 2=skinSurface(main), 7=periosteum(top)\n")
        f.write(f"# Vertices: {len(verts)}, Faces: {len(faces)}\n")
        f.write("# Deep bed defined via ShoulderSkin.bed (NOT as OBJ faces)\n")

        # Write all vertices
        for v in verts:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")

        # Write all texture coordinates
        for tc in texcoords:
            f.write(f"vt {tc[0]:.6f} {tc[1]:.6f}\n")

        def write_faces(face_list, material):
            f.write(f"usemtl {material}\n")
            for face in face_list:
                parts = [f"{vi}/{ti}" for vi, ti in face]
                f.write("f " + " ".join(parts) + "\n")

        # Material 1: boundary (bottom fan - peripheral anchors at y=0)
        write_faces(bottom_fan, 1)
        # Material 2: skin surface (main deformable body)
        write_faces(skin_main, 2)
        # Material 7: periosteum (top fan - fixed bone anchors)
        write_faces(top_fan, 7)

    print(f"\n--- Output ShoulderSkin.obj ---")
    print(f"  Vertices: {len(verts)}")
    print(f"  Faces:    {len(faces)}")
    print(f"  Material 1 (boundary):   {len(bottom_fan)} faces")
    print(f"  Material 2 (skin):       {len(skin_main)} faces")
    print(f"  Material 7 (periosteum): {len(top_fan)} faces")

    # Restore .bed file to original 386 entries if it was trimmed
    bed_path = os.path.join(MODEL_DIR, "ShoulderSkin.bed")
    if os.path.exists(bed_path):
        with open(bed_path) as bf:
            bed_lines = [l.strip() for l in bf if l.strip()]
        n_bed = len(bed_lines)
        if n_bed != len(verts):
            print(f"\n--- WARNING: .bed has {n_bed} entries but OBJ has {len(verts)} verts ---")
            print(f"  The .bed file should have one entry per skin vertex ({len(verts)} entries)")
        else:
            print(f"\n--- .bed file: {n_bed} entries (matches vertex count) ---")


if __name__ == "__main__":
    main()
