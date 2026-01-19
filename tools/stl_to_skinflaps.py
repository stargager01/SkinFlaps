#!/usr/bin/env python3
"""
STL to SkinFlaps OBJ Converter
Converts STL files to SkinFlaps-compatible OBJ, BED, and SMD files.

Usage: python stl_to_skinflaps.py input.stl output_prefix [--skin-depth 0.5]

Example:
    python stl_to_skinflaps.py face.stl my_model
    Creates: my_model.obj, my_model.bed, my_model.smd
"""

import sys
import struct
import os

def read_stl_binary(filename):
    """Read binary STL file"""
    triangles = []
    with open(filename, 'rb') as f:
        header = f.read(80)
        num_triangles = struct.unpack('I', f.read(4))[0]
        
        for _ in range(num_triangles):
            normal = struct.unpack('3f', f.read(12))
            v1 = struct.unpack('3f', f.read(12))
            v2 = struct.unpack('3f', f.read(12))
            v3 = struct.unpack('3f', f.read(12))
            attr = struct.unpack('H', f.read(2))[0]
            triangles.append((v1, v2, v3, normal))
    
    return triangles

def read_stl_ascii(filename):
    """Read ASCII STL file"""
    triangles = []
    with open(filename, 'r') as f:
        lines = f.readlines()
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('facet normal'):
            parts = line.split()
            normal = (float(parts[2]), float(parts[3]), float(parts[4]))
            i += 2  # skip 'outer loop'
            
            vertices = []
            for _ in range(3):
                vline = lines[i].strip().split()
                vertices.append((float(vline[1]), float(vline[2]), float(vline[3])))
                i += 1
            
            triangles.append((vertices[0], vertices[1], vertices[2], normal))
            i += 2  # skip 'endloop', 'endfacet'
        else:
            i += 1
    
    return triangles

def read_stl(filename):
    """Read STL file (auto-detect binary/ascii)"""
    with open(filename, 'rb') as f:
        header = f.read(80)
    
    try:
        with open(filename, 'r') as f:
            first_line = f.readline().strip()
            if first_line.startswith('solid'):
                return read_stl_ascii(filename)
    except:
        pass
    
    return read_stl_binary(filename)

def merge_vertices(triangles, tolerance=1e-6):
    """Merge duplicate vertices and create face indices"""
    vertices = []
    vertex_map = {}
    faces = []
    
    for v1, v2, v3, normal in triangles:
        face = []
        for v in [v1, v2, v3]:
            key = tuple(round(x / tolerance) * tolerance for x in v)
            
            if key not in vertex_map:
                vertex_map[key] = len(vertices)
                vertices.append(v)
            
            face.append(vertex_map[key] + 1)
        
        faces.append(face)
    
    return vertices, faces

def cross_product(a, b):
    return (a[1]*b[2] - a[2]*b[1], a[2]*b[0] - a[0]*b[2], a[0]*b[1] - a[1]*b[0])

def normalize(v):
    length = (v[0]**2 + v[1]**2 + v[2]**2) ** 0.5
    if length < 1e-10:
        return (0, 0, 1)
    return (v[0]/length, v[1]/length, v[2]/length)

def subtract(a, b):
    return (a[0]-b[0], a[1]-b[1], a[2]-b[2])

def classify_faces(vertices, faces):
    """Classify faces by normal direction"""
    top_faces, bottom_faces, side_faces = [], [], []
    
    for face in faces:
        v0, v1, v2 = vertices[face[0]-1], vertices[face[1]-1], vertices[face[2]-1]
        normal = normalize(cross_product(subtract(v1, v0), subtract(v2, v0)))
        
        if normal[2] > 0.7:
            top_faces.append(face)
        elif normal[2] < -0.7:
            bottom_faces.append(face)
        else:
            side_faces.append(face)
    
    return top_faces, bottom_faces, side_faces

def check_manifold(vertices, faces):
    edges = {}
    for face in faces:
        for i in range(len(face)):
            v1, v2 = face[i], face[(i+1) % len(face)]
            edge = (min(v1, v2), max(v1, v2))
            edges[edge] = edges.get(edge, 0) + 1
    
    non_manifold = [e for e, c in edges.items() if c != 2]
    return len(non_manifold) == 0, len(non_manifold)

def write_obj(filename, vertices, top_faces, side_faces, bottom_faces):
    with open(filename, 'w') as f:
        f.write("# Converted from STL for SkinFlaps\n")
        f.write("# Materials: 2=skin(top), 1=periferal(side), 7=periosteal(bottom)\n\n")
        
        for v in vertices:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        
        f.write("\n")
        
        x_coords = [v[0] for v in vertices]
        y_coords = [v[1] for v in vertices]
        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)
        x_range = x_max - x_min if x_max > x_min else 1
        y_range = y_max - y_min if y_max > y_min else 1
        
        for v in vertices:
            u = (v[0] - x_min) / x_range
            vt = (v[1] - y_min) / y_range
            f.write(f"vt {u:.6f} {vt:.6f}\n")
        
        f.write("\n")
        
        if top_faces:
            f.write("usemtl 2\ns 1\n")
            for face in top_faces:
                f.write(f"f {face[0]}/{face[0]} {face[1]}/{face[1]} {face[2]}/{face[2]}\n")
        
        if bottom_faces:
            f.write("\nusemtl 7\ns 2\n")
            for face in bottom_faces:
                f.write(f"f {face[0]}/{face[0]} {face[1]}/{face[1]} {face[2]}/{face[2]}\n")
        
        if side_faces:
            f.write("\nusemtl 1\ns 3\n")
            for face in side_faces:
                f.write(f"f {face[0]}/{face[0]} {face[1]}/{face[1]} {face[2]}/{face[2]}\n")
    
    return len(vertices), len(top_faces), len(side_faces), len(bottom_faces)

def write_bed(filename, vertices, skin_depth=0.5):
    z_coords = [v[2] for v in vertices]
    z_mid = (max(z_coords) + min(z_coords)) / 2
    
    with open(filename, 'w') as f:
        for i, v in enumerate(vertices):
            deep_z = v[2] - skin_depth if v[2] > z_mid else v[2]
            f.write(f"{i} {v[0]:.6f} {v[1]:.6f} {deep_z:.6f}\n")

def write_smd(filename, obj_name):
    smd = f'''{{"dynamicObjects":{{"{{obj_name}}":{{"textureMaps":[1,2,3,4]}}}},"textureFiles":{{"diffuse2.jpg":1,"normal.jpg":2,"deepBedTexture.jpg":3,"deepBedNormal.jpg":4}},"tetrahedralProperties":{{"minStrain":0.8,"maxStrain":1.26,"stiffness":8000.0,"poissonsRatio":0.4}}}}'''
    
    with open(filename, 'w') as f:
        f.write('{\n')
        f.write('    "dynamicObjects" : {\n')
        f.write(f'        "{obj_name}" : {{\n')
        f.write('            "textureMaps": [1, 2, 3, 4]\n')
        f.write('        }\n')
        f.write('    },\n')
        f.write('    "textureFiles" : {\n')
        f.write('        "diffuse2.jpg" : 1,\n')
        f.write('        "normal.jpg" : 2,\n')
        f.write('        "deepBedTexture.jpg" : 3,\n')
        f.write('        "deepBedNormal.jpg" : 4\n')
        f.write('    },\n')
        f.write('    "tetrahedralProperties" : {\n')
        f.write('        "minStrain" : 0.8,\n')
        f.write('        "maxStrain" : 1.26,\n')
        f.write('        "stiffness" : 8000.0,\n')
        f.write('        "poissonsRatio" : 0.4\n')
        f.write('    }\n')
        f.write('}\n')

def main():
    if len(sys.argv) < 3:
        print("STL to SkinFlaps Converter")
        print("=" * 40)
        print("\nUsage: python stl_to_skinflaps.py input.stl output_prefix")
        print("\nExample:")
        print("  python stl_to_skinflaps.py model.stl my_model")
        print("  Creates: my_model.obj, my_model.bed, my_model.smd")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_prefix = sys.argv[2]
    skin_depth = 0.5
    
    for i, arg in enumerate(sys.argv):
        if arg == '--skin-depth' and i + 1 < len(sys.argv):
            skin_depth = float(sys.argv[i + 1])
    
    if not os.path.exists(input_file):
        print(f"Error: File not found: {input_file}")
        sys.exit(1)
    
    print("=" * 50)
    print("STL to SkinFlaps Converter")
    print("=" * 50)
    
    print(f"\n[1/5] Reading: {input_file}")
    triangles = read_stl(input_file)
    print(f"      Triangles: {len(triangles)}")
    
    if len(triangles) > 500:
        print(f"\n⚠️  WARNING: Mesh has {len(triangles)} triangles!")
        print("   SkinFlaps works best with 30-100 faces.")
        print("   Please simplify using Blender or MeshLab.")
    
    print(f"\n[2/5] Processing mesh...")
    vertices, faces = merge_vertices(triangles)
    print(f"      Unique vertices: {len(vertices)}")
    print(f"      Faces: {len(faces)}")
    
    is_manifold, bad_edges = check_manifold(vertices, faces)
    if not is_manifold:
        print(f"\n⚠️  WARNING: Not a closed manifold! ({bad_edges} bad edges)")
    
    print(f"\n[3/5] Classifying faces...")
    top, bottom, side = classify_faces(vertices, faces)
    print(f"      Top (skin): {len(top)}, Side: {len(side)}, Bottom: {len(bottom)}")
    
    if len(top) < 6:
        print(f"\n⚠️  WARNING: Only {len(top)} top faces (need >= 6)")
    
    obj_file = f"{output_prefix}.obj"
    bed_file = f"{output_prefix}.bed"
    smd_file = f"{output_prefix}.smd"
    
    print(f"\n[4/5] Writing files...")
    write_obj(obj_file, vertices, top, side, bottom)
    print(f"      {obj_file}")
    write_bed(bed_file, vertices, skin_depth)
    print(f"      {bed_file}")
    write_smd(smd_file, os.path.basename(obj_file))
    print(f"      {smd_file}")
    
    print(f"\n[5/5] Done! Load {smd_file} in SkinFlaps to test.")

if __name__ == "__main__":
    main()
