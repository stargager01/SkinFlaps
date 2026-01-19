# SkinFlaps 사용자 커스텀 모델 생성 가이드

이 문서는 SkinFlaps 수술 시뮬레이션을 위한 커스텀 3D 모델을 생성하는 방법을 설명합니다.

## 목차
1. [필요한 파일 구조](#1-필요한-파일-구조)
2. [OBJ 파일 작성법](#2-obj-파일-작성법)
3. [BED 파일 작성법](#3-bed-파일-작성법)
4. [SMD 설정 파일 작성법](#4-smd-설정-파일-작성법)
5. [중요 주의사항](#5-중요-주의사항)
6. [예제: simple_circle 모델 분석](#6-예제-simple_circle-모델-분석)
7. [문제 해결](#7-문제-해결)

---

## 1. 필요한 파일 구조

SkinFlaps에서 모델을 로드하려면 다음 3개의 파일이 필요합니다:

```
Model/
├── your_model.smd      # 설정 파일 (JSON 형식)
├── your_model.obj      # 3D 메쉬 파일
└── your_model.bed      # Deep bed 좌표 파일
```

---

## 2. OBJ 파일 작성법

### 2.1 기본 구조

```obj
# 주석
v x y z          # 정점 (vertex)
vt u v           # 텍스처 좌표
usemtl N         # Material 번호 지정
s N              # Smoothing group
f v1/t1 v2/t2 v3/t3   # 삼각형 면 (face)
```

### 2.2 필수 Material 번호

| Material | 용도 | 설명 |
|----------|------|------|
| **2** | 피부 표면 (Skin) | 수술이 수행되는 상단 표면 |
| **1** | 경계면 (Periferal) | 측면 벽 |
| **7** | 골막층 (Periosteal) | 하단 표면 (고정됨) |

### 2.3 메쉬 요구사항

#### ✅ 필수 조건

1. **닫힌 매니폴드 (Closed Manifold)**
   - 모든 edge가 정확히 2개의 면에 의해 공유되어야 함
   - 열린 표면(한 장의 시트)은 작동하지 않음
   - 상단 + 하단 + 측면으로 완전히 닫힌 볼륨이어야 함

2. **일관된 Winding Order (CCW)**
   - 상단 표면: 반시계 방향 (위에서 볼 때)
   - 하단 표면: 시계 방향 (위에서 볼 때) = 아래에서 보면 반시계
   - 노멀이 바깥쪽을 향해야 함

3. **충분한 삼각형 수**
   - 상단 표면에 최소 6개 이상의 삼각형 필요
   - Deep cut 등 수술 작업을 위해 충분한 세분화 필요

4. **방사형 구조 권장**
   - 중심점에서 바깥으로 퍼지는 구조가 가장 안정적
   - 그리드 구조보다 방사형 구조가 더 잘 작동함

### 2.4 권장 구조 (방사형)

```
          외부 링
       *----*----*
      /    / \    \
     *----*---*----*   <- 내부 링
      \    \ /    /
       *----*----*     <- 중심점
```

---

## 3. BED 파일 작성법

BED 파일은 undermine(박리) 작업을 위한 deep bed 좌표를 정의합니다.

### 형식
```
vertex_index x y z
```

- `vertex_index`: 0부터 시작하는 정점 인덱스 (OBJ는 1부터 시작)
- `x y z`: 해당 정점의 deep bed 좌표

### 예시
```
0 0.0 0.0 0.5      # OBJ의 정점 1 → 인덱스 0
1 2.0 0.0 0.5      # OBJ의 정점 2 → 인덱스 1
2 1.0 1.732 0.5    # OBJ의 정점 3 → 인덱스 2
```

### Deep Bed 좌표 계산
- 상단 표면 정점: Z 좌표를 약간 낮춤 (예: 1.0 → 0.5)
- 하단 표면 정점: 원래 좌표 유지

---

## 4. SMD 설정 파일 작성법

SMD 파일은 JSON 형식의 설정 파일입니다.

### 기본 템플릿
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

### 필수 항목
- `dynamicObjects`: OBJ 파일 이름과 텍스처 매핑
- `textureFiles`: 텍스처 파일 정의
- `tetrahedralProperties`: 물리 시뮬레이션 속성

---

## 5. 중요 주의사항

### ⚠️ 반드시 피해야 할 것들

1. **열린 메쉬 (Open Surface)**
   ```
   ❌ 단일 평면 시트
   ✅ 완전히 닫힌 볼륨 (상단 + 하단 + 측면)
   ```

2. **불일치하는 Winding Order**
   ```
   ❌ 일부 삼각형이 반대 방향
   ✅ 모든 삼각형이 일관된 CCW 순서
   ```

3. **너무 적은 삼각형**
   ```
   ❌ 상단 표면에 2-4개 삼각형
   ✅ 상단 표면에 최소 6개 이상 삼각형
   ```

4. **직각 코너가 있는 구조**
   ```
   ❌ 정사각형/직사각형 형태
   ✅ 육각형, 팔각형 등 부드러운 형태
   ```

### ✅ 권장사항

1. **작은 모델로 시작하기**
   - simple_circle.obj를 템플릿으로 사용
   - 정점 수: 15-30개
   - 면 수: 30-50개

2. **방사형 구조 사용**
   - 중심점 1개
   - 내부 링 6-8개 정점
   - 외부 링 6-8개 정점

3. **테스트 순서**
   - 먼저 모델 로드가 되는지 확인
   - 다음으로 Deep Cut 작업 테스트
   - 마지막으로 다른 수술 작업 테스트

---

## 6. 예제: simple_circle 모델 분석

### 6.1 정점 구조 (20개)

```obj
# 상단 표면 (z = 1.0)
# 중심점 (1개)
v 0.0 0.0 1.0           # 정점 1

# 내부 링 (6개, 반지름 1.0)
v 1.0 0.0 1.0           # 정점 2
v 0.5 0.866 1.0         # 정점 3
v -0.5 0.866 1.0        # 정점 4
v -1.0 0.0 1.0          # 정점 5
v -0.5 -0.866 1.0       # 정점 6
v 0.5 -0.866 1.0        # 정점 7

# 외부 링 (6개, 반지름 2.0)
v 2.0 0.0 1.0           # 정점 8
v 1.0 1.732 1.0         # 정점 9
v -1.0 1.732 1.0        # 정점 10
v -2.0 0.0 1.0          # 정점 11
v -1.0 -1.732 1.0       # 정점 12
v 1.0 -1.732 1.0        # 정점 13

# 하단 표면 (z = -0.5)
# 중심점 + 외부 링 (7개)
v 0.0 0.0 -0.5          # 정점 14
v 2.0 0.0 -0.5          # 정점 15
...
```

### 6.2 면 구조 (36개)

```obj
# 상단 표면 (Material 2) - 18개 삼각형
usemtl 2
# 내부 팬 (6개) - 중심에서 내부 링으로
f 1 2 3    # 중심 → 내부링
f 1 3 4
...

# 외부 링 (12개) - 내부 링에서 외부 링으로
f 2 8 9    # 내부 → 외부
f 2 9 3
...

# 하단 표면 (Material 7) - 6개 삼각형
usemtl 7
f 14 16 15  # CW 순서 (위에서 봤을 때)
...

# 측면 벽 (Material 1) - 12개 삼각형
usemtl 1
f 8 15 16   # 상단 외부 → 하단 외부
f 8 16 9
...
```

### 6.3 구조 다이어그램

```
     상단 표면 (z = 1.0)
         
        10---9
       / \ / \
     11---4---3---8
       \ / \ / \ /
        5---1---2
       / \ / \ / \
     12---6---7---13
       \ / \ /
        -   -
        
     측면 벽으로 하단과 연결
         
     하단 표면 (z = -0.5)
```

---

## 7. 문제 해결

### 오류: "The model file did not load successfully"
**원인**: SMD 파일 형식 오류 또는 필수 항목 누락
**해결**: 
- JSON 문법 확인
- `dynamicObjects`, `textureFiles` 항목 확인
- OBJ 파일명이 정확한지 확인

### 오류: "Model is not a closed manifold surface"
**원인**: 메쉬가 닫힌 볼륨이 아님
**해결**:
- 상단, 하단, 측면이 모두 있는지 확인
- 모든 edge가 정확히 2개 면에 공유되는지 확인

### 오류: "Couldn't create the initial physics lattice"
**원인**: 메쉬 geometry 문제
**해결**:
- 방사형 구조로 변경
- 직각 코너 제거
- 정점 위치가 균일한지 확인

### 오류: "surfacePath() call does not have a valid starting triangle"
**원인**: 상단 표면에 삼각형이 부족하거나 구조가 부적절
**해결**:
- 상단 표면 삼각형 수 증가 (최소 6개)
- 방사형 구조 사용
- Material 2가 올바르게 지정되었는지 확인

---

## 참고: 메쉬 검증 Python 스크립트

```python
def validate_obj(filename):
    with open(filename, 'r') as f:
        content = f.read()
    
    vertices = []
    faces = []
    
    for line in content.strip().split('\n'):
        line = line.strip()
        if line.startswith('v '):
            parts = line.split()
            vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
        elif line.startswith('f '):
            parts = line.split()[1:]
            face = [int(p.split('/')[0]) for p in parts]
            faces.append(face)
    
    print(f"Vertices: {len(vertices)}, Faces: {len(faces)}")
    
    # Check closed manifold
    edges = {}
    for face in faces:
        for i in range(len(face)):
            v1, v2 = face[i], face[(i+1) % len(face)]
            edge = (min(v1, v2), max(v1, v2))
            edges[edge] = edges.get(edge, 0) + 1
    
    non_manifold = [e for e, c in edges.items() if c != 2]
    if non_manifold:
        print(f"ERROR: {len(non_manifold)} non-manifold edges")
        return False
    print("Valid closed manifold!")
    return True

validate_obj('your_model.obj')
```

---

## 문의 및 지원

작동하는 예제 모델:
- `Model/simple_circle.smd` - 육각형 프리즘 (권장 템플릿)

문제가 발생하면 simple_circle 모델을 복사하여 수정하는 것을 권장합니다.
