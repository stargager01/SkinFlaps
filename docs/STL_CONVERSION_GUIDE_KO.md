# STL 파일을 SkinFlaps 모델로 변환하기

DICOM에서 추출한 STL 또는 사용자 3D 모델을 SkinFlaps에서 사용하는 방법

## 목차
1. [개요](#1-개요)
2. [필요한 소프트웨어](#2-필요한-소프트웨어)
3. [변환 워크플로우](#3-변환-워크플로우)
4. [Blender를 이용한 변환](#4-blender를-이용한-변환)
5. [MeshLab을 이용한 변환](#5-meshlab을-이용한-변환)
6. [Python 스크립트 변환](#6-python-스크립트-변환)
7. [BED 및 SMD 파일 생성](#7-bed-및-smd-파일-생성)
8. [주의사항 및 팁](#8-주의사항-및-팁)

---

## 1. 개요

### 1.1 STL vs SkinFlaps 형식 비교

| 특성 | STL | SkinFlaps (OBJ) |
|------|-----|-----------------|
| 정점 정보 | 삼각형별 중복 | 공유 정점 |
| Material | 없음 | 필수 (2, 1, 7) |
| 텍스처 좌표 | 없음 | 필요 |
| 구조 | 단일 표면 가능 | 닫힌 볼륨 필수 |

### 1.2 변환 과정 요약

```
STL 파일
    ↓
1. 메쉬 정리 (중복 정점 병합, 구멍 메우기)
    ↓
2. 닫힌 볼륨으로 변환 (상단/하단/측면 추가)
    ↓
3. Material 영역 지정
    ↓
4. OBJ 형식으로 내보내기
    ↓
5. BED 파일 생성
    ↓
6. SMD 설정 파일 생성
    ↓
SkinFlaps 모델 완성
```

---

## 2. 필요한 소프트웨어

### 2.1 권장 소프트웨어

| 소프트웨어 | 용도 | 다운로드 |
|-----------|------|----------|
| **Blender** (권장) | 메쉬 편집, 변환 | https://www.blender.org |
| **MeshLab** | 메쉬 정리, 수리 | https://www.meshlab.net |
| **3D Slicer** | DICOM → STL 변환 | https://www.slicer.org |
| **Python** | 자동화 스크립트 | https://www.python.org |

### 2.2 DICOM에서 STL 추출
3D Slicer를 사용하여 CT/MRI DICOM에서 STL 추출:
1. 3D Slicer 실행
2. DICOM 데이터 로드
3. Segment Editor로 관심 영역 분할
4. `Segmentation` → `Export to files` → STL 선택

---

## 3. 변환 워크플로우

### 3.1 SkinFlaps 모델 요구사항

✅ **필수 조건**:
- 닫힌 매니폴드 표면 (모든 edge가 정확히 2개 면 공유)
- Material 지정: 2(피부), 1(측면), 7(하단)
- 텍스처 좌표 (vt)
- 충분한 상단 표면 삼각형 (최소 6개)

⚠️ **권장 사항**:
- 방사형 구조 (중심에서 바깥으로)
- 정점 수: 15-50개
- 면 수: 30-100개
- 단순한 형태

### 3.2 DICOM 메쉬의 특성

DICOM에서 추출한 STL은 보통:
- 매우 많은 삼각형 (수만~수십만 개)
- 복잡한 형태
- 노이즈와 구멍 존재 가능

→ **단순화(Decimation)가 필수**

---

## 4. Blender를 이용한 변환

### 4.1 STL 가져오기
```
File → Import → STL (.stl)
```

### 4.2 메쉬 단순화 (Decimation)
1. 객체 선택
2. `Modifier Properties` (스패너 아이콘)
3. `Add Modifier` → `Decimate`
4. `Ratio` 조절 (0.01~0.1 권장)
5. `Apply`

### 4.3 닫힌 볼륨 만들기

#### 방법 A: 기존 메쉬에 두께 추가
1. 객체 선택 → Edit Mode (Tab)
2. 모든 면 선택 (A)
3. `Mesh` → `Extrude` → `Extrude Faces Along Normals`
4. 음수 방향으로 이동하여 두께 생성

#### 방법 B: Solidify Modifier
1. `Add Modifier` → `Solidify`
2. `Thickness` 설정 (음수 값으로 안쪽 방향)
3. `Apply`

### 4.4 Material 영역 분리

1. Edit Mode에서 상단 표면 선택
2. `P` → `Selection`으로 분리
3. 각 부분에 Material 이름 지정:
   - 상단: `2`
   - 측면: `1`
   - 하단: `7`

### 4.5 텍스처 좌표 생성
1. Edit Mode → 모든 면 선택
2. `UV` → `Smart UV Project`
3. 기본 설정으로 OK

### 4.6 OBJ 내보내기
```
File → Export → Wavefront (.obj)
```

설정:
- ✅ Selection Only (필요시)
- ✅ Include UVs
- ✅ Write Materials
- ✅ Triangulate Faces

---

## 5. MeshLab을 이용한 변환

### 5.1 STL 가져오기
```
File → Import Mesh → STL 파일 선택
```

### 5.2 메쉬 정리
```
Filters → Cleaning and Repairing → 
  → Remove Duplicate Vertices
  → Remove Duplicate Faces
  → Remove Zero Area Faces
```

### 5.3 구멍 메우기
```
Filters → Remeshing, Simplification... → Close Holes
```

### 5.4 단순화
```
Filters → Remeshing, Simplification... → 
  Simplification: Quadric Edge Collapse Decimation
  
Target number of faces: 50-200
```

### 5.5 OBJ 내보내기
```
File → Export Mesh As → OBJ
```

⚠️ **주의**: MeshLab은 Material 지정이 제한적이므로, 
내보낸 후 텍스트 에디터로 Material 수동 추가 필요

---

## 6. Python 스크립트 변환

### 6.1 STL → OBJ 기본 변환 스크립트

```python
#!/usr/bin/env python3
"""
STL to SkinFlaps OBJ Converter
Usage: python stl_to_skinflaps.py input.stl output_prefix
"""

import sys
import struct
import numpy as np

def read_stl_binary(filename):
    """Read binary STL file"""
    with open(filename, 'rb') as f:
        header = f.read(80)
        num_triangles = struct.unpack('I', f.read(4))[0]
        
        triangles = []
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
        if b'solid' in header[:6]:
            return read_stl_ascii(filename)
    except:
        pass
    
    return read_stl_binary(filename)

def merge_vertices(triangles, tolerance=1e-6):
    """Merge duplicate vertices"""
    vertices = []
    vertex_map = {}
    faces = []
    
    for v1, v2, v3, normal in triangles:
        face = []
        for v in [v1, v2, v3]:
            # Round for comparison
            key = tuple(round(x / tolerance) * tolerance for x in v)
            
            if key not in vertex_map:
                vertex_map[key] = len(vertices)
                vertices.append(v)
            
            face.append(vertex_map[key] + 1)  # OBJ is 1-indexed
        
        faces.append(face)
    
    return vertices, faces

def classify_faces(vertices, faces):
    """Classify faces by normal direction (top/bottom/side)"""
    top_faces = []
    bottom_faces = []
    side_faces = []
    
    for face in faces:
        # Calculate face normal
        v0 = np.array(vertices[face[0]-1])
        v1 = np.array(vertices[face[1]-1])
        v2 = np.array(vertices[face[2]-1])
        
        edge1 = v1 - v0
        edge2 = v2 - v0
        normal = np.cross(edge1, edge2)
        normal = normal / np.linalg.norm(normal)
        
        # Classify by Z component of normal
        if normal[2] > 0.7:
            top_faces.append(face)
        elif normal[2] < -0.7:
            bottom_faces.append(face)
        else:
            side_faces.append(face)
    
    return top_faces, bottom_faces, side_faces

def write_obj(filename, vertices, top_faces, side_faces, bottom_faces):
    """Write OBJ file with materials"""
    with open(filename, 'w') as f:
        f.write("# Converted from STL for SkinFlaps\n")
        f.write("# Materials: 2=skin(top), 1=periferal(side), 7=periosteal(bottom)\n\n")
        
        # Write vertices
        for v in vertices:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        
        f.write("\n")
        
        # Write texture coordinates (simple planar projection)
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
        
        # Write faces with materials
        if top_faces:
            f.write("usemtl 2\n")
            f.write("s 1\n")
            for face in top_faces:
                f.write(f"f {face[0]}/{face[0]} {face[1]}/{face[1]} {face[2]}/{face[2]}\n")
        
        if bottom_faces:
            f.write("\nusemtl 7\n")
            f.write("s 2\n")
            for face in bottom_faces:
                f.write(f"f {face[0]}/{face[0]} {face[1]}/{face[1]} {face[2]}/{face[2]}\n")
        
        if side_faces:
            f.write("\nusemtl 1\n")
            f.write("s 3\n")
            for face in side_faces:
                f.write(f"f {face[0]}/{face[0]} {face[1]}/{face[1]} {face[2]}/{face[2]}\n")
    
    print(f"Written: {filename}")
    print(f"  Vertices: {len(vertices)}")
    print(f"  Top faces (mat 2): {len(top_faces)}")
    print(f"  Side faces (mat 1): {len(side_faces)}")
    print(f"  Bottom faces (mat 7): {len(bottom_faces)}")

def write_bed(filename, vertices, skin_depth=0.5):
    """Write BED file"""
    with open(filename, 'w') as f:
        z_coords = [v[2] for v in vertices]
        z_max = max(z_coords)
        z_min = min(z_coords)
        z_mid = (z_max + z_min) / 2
        
        for i, v in enumerate(vertices):
            # Top vertices get deep bed below surface
            # Bottom vertices stay at their position
            if v[2] > z_mid:
                deep_z = v[2] - skin_depth
            else:
                deep_z = v[2]
            
            f.write(f"{i} {v[0]:.6f} {v[1]:.6f} {deep_z:.6f}\n")
    
    print(f"Written: {filename}")

def write_smd(filename, obj_name):
    """Write SMD configuration file"""
    smd_content = f'''{{
    "dynamicObjects" : {{
        "{obj_name}" : {{
            "textureMaps": [1, 2, 3, 4]
        }}
    }},
    "textureFiles" : {{
        "diffuse2.jpg" : 1,
        "normal.jpg" : 2,
        "deepBedTexture.jpg" : 3,
        "deepBedNormal.jpg" : 4
    }},
    "tetrahedralProperties" : {{
        "minStrain" : 0.8,
        "maxStrain" : 1.26,
        "stiffness" : 8000.0,
        "poissonsRatio" : 0.4
    }}
}}
'''
    with open(filename, 'w') as f:
        f.write(smd_content)
    
    print(f"Written: {filename}")

def main():
    if len(sys.argv) < 3:
        print("Usage: python stl_to_skinflaps.py input.stl output_prefix")
        print("Example: python stl_to_skinflaps.py model.stl my_model")
        print("         Creates: my_model.obj, my_model.bed, my_model.smd")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_prefix = sys.argv[2]
    
    print(f"Reading: {input_file}")
    triangles = read_stl(input_file)
    print(f"  Triangles: {len(triangles)}")
    
    if len(triangles) > 500:
        print(f"\n⚠️  WARNING: Too many triangles ({len(triangles)})!")
        print("   SkinFlaps works best with 30-100 faces.")
        print("   Please simplify the mesh first using Blender or MeshLab.")
        print("   Continuing anyway, but model may not work properly.\n")
    
    print("Merging vertices...")
    vertices, faces = merge_vertices(triangles)
    print(f"  Unique vertices: {len(vertices)}")
    print(f"  Faces: {len(faces)}")
    
    print("Classifying faces...")
    top, bottom, side = classify_faces(vertices, faces)
    
    if len(top) < 6:
        print(f"\n⚠️  WARNING: Only {len(top)} top faces detected!")
        print("   SkinFlaps needs at least 6 triangles on top surface.")
        print("   The model may not work properly.\n")
    
    # Write output files
    obj_file = f"{output_prefix}.obj"
    bed_file = f"{output_prefix}.bed"
    smd_file = f"{output_prefix}.smd"
    
    write_obj(obj_file, vertices, top, side, bottom)
    write_bed(bed_file, vertices)
    write_smd(smd_file, f"{output_prefix}.obj")
    
    print("\n✅ Conversion complete!")
    print(f"   Load {smd_file} in SkinFlaps to test.")

if __name__ == "__main__":
    main()
```

### 6.2 스크립트 사용법

```bash
# 스크립트 저장
python stl_to_skinflaps.py input.stl output_prefix

# 예시
python stl_to_skinflaps.py face_scan.stl my_face
# 결과: my_face.obj, my_face.bed, my_face.smd
```

---

## 7. BED 및 SMD 파일 생성

### 7.1 BED 파일 수동 생성

BED 파일 형식:
```
vertex_index x y z
```

각 정점의 deep bed 좌표를 계산:
- **상단 정점**: Z 좌표를 0.3~0.5 정도 낮춤
- **하단 정점**: 원래 좌표 유지

예시:
```
0 0.0 0.0 0.5    # 원래 (0, 0, 1.0) → deep bed (0, 0, 0.5)
1 1.0 0.0 0.5    # 상단 정점
2 0.0 0.0 -0.5   # 하단 정점 (변경 없음)
```

### 7.2 SMD 파일 템플릿

```json
{
    "dynamicObjects" : {
        "your_model.obj" : {
            "textureMaps": [1, 2, 3, 4]
        }
    },
    "textureFiles" : {
        "diffuse2.jpg" : 1,
        "normal.jpg" : 2,
        "deepBedTexture.jpg" : 3,
        "deepBedNormal.jpg" : 4
    },
    "tetrahedralProperties" : {
        "minStrain" : 0.8,
        "maxStrain" : 1.26,
        "stiffness" : 8000.0,
        "poissonsRatio" : 0.4
    }
}
```

**주의**: `your_model.obj`를 실제 파일명으로 변경

---

## 8. 주의사항 및 팁

### 8.1 DICOM 메쉬 처리 시 주의사항

1. **크기 조정 필요**
   - DICOM은 보통 mm 단위
   - SkinFlaps는 작은 단위 선호 (약 2-4 단위 크기)
   - Blender에서 `S` 키로 스케일 조정

2. **방향 확인**
   - 피부 표면이 +Z 방향을 향해야 함
   - Blender에서 `R` 키로 회전 가능

3. **원점 설정**
   - 모델 중심이 원점 근처에 있어야 함
   - Blender: `Object` → `Set Origin` → `Origin to Geometry`

### 8.2 단순화 권장 수준

| 원본 삼각형 수 | 권장 목표 | Decimate Ratio |
|---------------|----------|----------------|
| 100,000+ | 50-100 | 0.001 |
| 10,000 | 50-100 | 0.01 |
| 1,000 | 50-100 | 0.1 |

### 8.3 성공적인 변환을 위한 체크리스트

- [ ] 메쉬가 닫힌 볼륨인가?
- [ ] 정점 수가 50개 이하인가?
- [ ] 상단 표면에 6개 이상의 삼각형이 있는가?
- [ ] Material이 올바르게 지정되었는가? (2, 1, 7)
- [ ] 텍스처 좌표가 있는가?
- [ ] BED 파일의 정점 수가 OBJ와 일치하는가?
- [ ] SMD 파일의 OBJ 파일명이 정확한가?

### 8.4 문제 해결

| 문제 | 원인 | 해결책 |
|------|------|--------|
| Physics lattice 오류 | 메쉬가 너무 복잡 | 더 많이 단순화 |
| 닫힌 매니폴드 아님 | 구멍이나 비매니폴드 edge | MeshLab에서 수리 |
| surfacePath 오류 | 상단 삼각형 부족 | 상단 표면 세분화 |
| 모델이 보이지 않음 | 크기가 너무 크거나 작음 | 스케일 조정 |

### 8.5 실제 사례: 얼굴 스캔 변환

1. **3D Slicer에서 얼굴 영역 추출**
2. **MeshLab에서 정리 및 단순화** (50-100 faces)
3. **Blender에서 편집**:
   - 피부 영역만 선택
   - Solidify로 두께 추가
   - Material 지정
4. **OBJ 내보내기**
5. **Python 스크립트로 BED/SMD 생성**
6. **SkinFlaps에서 테스트**

---

## 요약

STL을 SkinFlaps로 변환하는 핵심 단계:

1. **단순화**: 삼각형 수를 50-100개로 줄임
2. **닫힌 볼륨**: Solidify 또는 수동으로 상단/하단/측면 생성
3. **Material 지정**: 2(상단), 1(측면), 7(하단)
4. **파일 생성**: OBJ + BED + SMD

복잡한 해부학적 모델보다는 **simple_circle.smd를 기반으로 수정**하는 것이 
초보자에게 더 쉬운 방법입니다.

---

*추가 질문이나 문제가 있으면 GitHub Issues에 문의하세요.*
