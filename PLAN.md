# Plan: CT/MRI 기반 모델 교체 파이프라인

## 배경

`agent.md` Section 10 "Future Work"에 명시된 대로:
> "Replace prototype models with CT/MRI-segmented anatomical meshes"

현재 ShoulderMinimal 모델(386 vertices, 768 faces)은 수동으로 제작된 프로토타입이다.
실제 CT/MRI DICOM 데이터에서 추출한 해부학적으로 정확한 메시로 교체하는
파이프라인을 구축한다.

---

## 핵심 제약 조건 (반드시 준수)

SkinFlaps의 BCC Tet Cutter 아키텍처에서 요구하는 불변 조건들:

1. **단일 닫힌 표면(Single Closed Manifold)**: 동적 OBJ는 반드시 하나의 연결된 닫힌 셸이어야 함
2. **OBJ 재료 ID**: 파일 내에는 `{1(boundary), 2(skinSurface), 7(periosteum)}`만 허용
3. **재료 5(deepBed)는 런타임 전용**: OBJ에 포함하면 "Solid ordering error" 발생
4. **Deep Bed는 .bed 파일**: 각 스킨 정점 → 깊은 층 좌표 매핑
5. **일관된 와인딩(Consistent Winding)**: 바깥 방향 법선 (오른손 법칙)
6. **삼각형만 허용**: 쿼드 또는 고차 폴리곤 불가
7. **오일러 특성**: V - E + F = 2 (닫힌 표면, genus 0)

---

## 구현 단계

### Phase 1: Python 변환 도구 (외부 파이프라인, C++ 수정 없음)

#### Step 1.1: DICOM → 세그멘테이션 도구
**파일**: `tools/segment_dicom.py`

- `pydicom` + `SimpleITK`로 DICOM 시리즈 로드
- 조직 유형별 반자동 세그멘테이션:
  - **피부(skin)**: HU 임계값 기반 외곽 추출
  - **뼈(bone)**: HU > 300 (피질골 > 700)
  - **근육/건(muscle/tendon)**: HU 40-80 범위 + 수동 시드
  - **관절낭(capsule)**: 수동 마킹 또는 아틀라스 기반
- 출력: 다중 라벨 NIfTI 볼륨 (`.nii.gz`)
- 선택적으로 3D Slicer / ITK-SNAP 세그멘테이션 파일도 입력 가능

```
의존성: pydicom, SimpleITK, numpy, scipy
```

#### Step 1.2: 세그멘테이션 → SkinFlaps 변환 도구
**파일**: `tools/ct_to_skinflaps.py`

핵심 파이프라인:
```
NIfTI 다중 라벨 볼륨
    ↓
[라벨별 표면 추출] ← Marching Cubes (scikit-image/VTK)
    ↓
[메시 정리] ← 중복 정점 제거, 퇴화 삼각형 제거
    ↓
[메시 단순화] ← Quadric Edge Collapse (목표: 500-2000 faces)
    ↓
[단일 매니폴드 병합] ← 아래 상세 설명
    ↓
[재료 ID 할당] ← boundary=1, skin=2, periosteum=7
    ↓
[.bed 파일 생성] ← 스킨→깊은 층 최근접점 투영
    ↓
[위상 검증] ← 오일러, 연결성, 와인딩
    ↓
`.obj` + `.bed` + `.smd` 출력
```

**단일 매니폴드 병합 전략** (가장 핵심적인 기술적 과제):

```
방법 A: 외피 셸 방식 (권장)
━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. 피부 표면만 Marching Cubes로 추출 → 이것이 동적 OBJ가 됨
2. 피부 셸의 가장자리(하단/측면) 정점을 material 1 (boundary)로 지정
3. 뼈에 인접한 영역의 정점을 material 7 (periosteum)로 지정
4. 나머지 피부 표면을 material 2 (skinSurface)로 지정
5. 내부 조직(근육, 건)은 tetSubset OBJ로 별도 추출
6. deep bed는 .bed 파일로 생성

방법 B: 오프셋 표면 방식
━━━━━━━━━━━━━━━━━━━━━━━
1. 뼈 표면에서 외측으로 일정 거리 오프셋 → 단일 돔 형태
2. 돔의 바닥 = material 7 (periosteum)
3. 돔의 테두리 = material 1 (boundary)
4. 돔의 나머지 = material 2 (skinSurface)
5. 실제 뼈 표면 좌표로 .bed 파일 생성
```

#### Step 1.3: .bed 파일 자동 생성
**`ct_to_skinflaps.py` 내 함수**

```python
def generate_bed_file(skin_mesh, deep_surface_mesh):
    """
    각 스킨 정점에 대해 깊은 층 표면의 최근접점을 찾아 매핑.
    KD-Tree 기반 O(N log M) 최근접점 검색.
    """
    tree = KDTree(deep_surface_mesh.vertices)
    bed_entries = []
    for i, v in enumerate(skin_mesh.vertices):
        _, idx = tree.query(v)
        # 최근접 삼각형 위의 정확한 투영점 계산
        proj = project_to_triangle(v, deep_surface_mesh, idx)
        bed_entries.append((i, proj))
    return bed_entries
```

#### Step 1.4: .smd 장면 파일 자동 생성
**`ct_to_skinflaps.py` 내 함수**

기존 `ShoulderMinimal.smd`를 템플릿으로 사용하여:
- `sceneName`: 환자 ID 또는 해부 부위명
- `dynamicObjects`: 생성된 OBJ 파일 참조
- `tetrahedralProperties`: 기본값 사용 (사용자 조정 가능)
- `tissueRegions`: 세그멘테이션 라벨에서 자동 매핑
- `materialLayers`: 표준 매핑 ({1,2,7} + 런타임 ID)
- `tetrahedralSubsets`: 근육/건 tetSubset OBJ 참조

#### Step 1.5: 검증 도구
**파일**: `tools/validate_ct_mesh.py`

```python
def validate_for_skinflaps(obj_path, bed_path):
    checks = [
        check_single_connected_component(),   # 단일 연결 요소
        check_euler_characteristic(),          # V-E+F=2
        check_consistent_winding(),            # 일관된 와인딩
        check_material_ids({1, 2, 7}),         # 허용된 재료만
        check_no_degenerate_triangles(),       # 퇴화 삼각형 없음
        check_no_boundary_edges(),             # 닫힌 표면
        check_bed_vertex_coverage(bed_path),   # 모든 정점 매핑됨
        check_bed_coordinates_reasonable(),    # 좌표 범위 합리적
        check_vertex_count_reasonable(200, 50000),  # 합리적 정점 수
    ]
    return all(checks)
```

---

### Phase 2: 테스트 및 참조 데이터셋

#### Step 2.1: 합성 테스트 데이터
**파일**: `tests/test_ct_pipeline.py`

- 합성 볼륨(구, 원기둥)으로 파이프라인 단위 테스트
- Marching Cubes 출력 검증
- 단순화 후 위상 보존 검증
- .bed 생성 정확도 검증

#### Step 2.2: 공개 CT 데이터셋으로 검증

이용 가능한 공개 데이터:
- **Visible Human Project** (NIH): 전신 단면 CT
- **CT-ORG** (Cancer Imaging Archive): 장기 세그멘테이션
- **AAPM Thorax Phantom**: 표준 참조 팬텀
- **Shoulder-specific**: 어깨 관절 CT (TCIA 등)

1개 이상의 공개 어깨 CT로 end-to-end 파이프라인 테스트

#### Step 2.3: 결과 비교
- 프로토타입 ShoulderMinimal vs CT 유래 모델 시각적 비교
- 메시 품질 메트릭: 삼각형 종횡비, 최소 각도, 요소 크기 균일성

---

### Phase 3: C++ 측 개선 (선택적, 대규모 메시 지원)

#### Step 3.1: 대규모 메시 성능 최적화
CT 유래 메시는 5,000-50,000 faces일 수 있어 현재 프로토타입(768 faces) 대비 크다.

**확인 필요 항목**:
- `vnBccTetCutter_tbb`: 대규모 입력 메시 처리 시간
- `getConnectedComponents()`: 높은 face 수에서 성능
- 메모리 사용량: multi-resolution 승격 시

**대응 (필요 시)**:
- 입력 메시 단순화 임계값을 Python 도구에서 조정
- bccTetScene에 메시 크기 경고 추가

#### Step 3.2: DICOM 직접 임포트 (장기 목표)
**매우 선택적** - Phase 1 도구가 충분히 작동하면 불필요

- C++에서 DCMTK 또는 GDCM 라이브러리 사용
- File → Import CT/MRI 메뉴 항목 추가
- SurgicalSimGui에 세그멘테이션 미리보기 대화상자
- 이는 대규모 작업이며 현 단계에서는 권장하지 않음

---

### Phase 4: 문서화

#### Step 4.1: 사용자 가이드
**파일**: `docs/ct_mri_import_guide.md`

- 지원되는 CT/MRI 형식 (DICOM, NIfTI)
- 세그멘테이션 소프트웨어 권장 (3D Slicer, ITK-SNAP)
- 단계별 변환 워크플로우
- 문제 해결 (일반적 오류 및 해결 방법)

#### Step 4.2: 개발자 문서
- 파이프라인 아키텍처 다이어그램
- 확장 포인트 설명 (새 해부 부위 추가 방법)
- 메시 품질 요구사항 및 검증 기준

---

## 의존성 요약

### Python 패키지 (tools/ 디렉토리)
```
pydicom>=2.3        # DICOM 파일 읽기
SimpleITK>=2.2      # 의료 영상 처리
numpy>=1.21         # 수치 연산
scipy>=1.7          # KD-Tree, 공간 알고리즘
scikit-image>=0.19  # Marching Cubes
trimesh>=3.15       # 메시 처리, 단순화
pyvista>=0.36       # 3D 시각화 (선택)
```

### C++ (Phase 3만 해당, 선택적)
```
DCMTK 또는 GDCM     # DICOM 파싱
```

---

## 구현 우선순위 및 복잡도

| 단계 | 복잡도 | C++ 변경 | 필수/선택 |
|------|--------|---------|----------|
| Phase 1: Python 변환 도구 | 중간 | 없음 | **필수** |
| Phase 2: 테스트/검증 | 낮음 | 없음 | **필수** |
| Phase 3: C++ 대규모 메시 | 높음 | 있음 | 선택 |
| Phase 4: 문서화 | 낮음 | 없음 | 권장 |

---

## 핵심 기술적 결정 사항

### 1. 표면 추출 방법
- **Marching Cubes** (scikit-image): 표준적, 빠름, 계단 아티팩트 있음
- **Marching Cubes + Laplacian Smoothing**: 더 부드러운 표면
- **VTK Flying Edges**: 병렬화, 대용량에 적합

**권장**: Marching Cubes + Laplacian Smoothing (2-3회 반복)

### 2. 메시 단순화 알고리즘
- **Quadric Edge Collapse** (trimesh/Open3D): 형태 보존 우수
- 목표 face 수: 1000-5000 (현재 facial=17,378, shoulder=768)
- 경계 정점(material 1, 7) 보존 필수

**권장**: Quadric Edge Collapse, material 경계 정점 고정

### 3. 재료 영역 자동 분류
CT에서 material {1, 2, 7} 자동 할당 방법:
- **Material 7 (periosteum)**: 뼈 표면에서 일정 거리 이내의 피부 정점
- **Material 1 (boundary)**: 메시 가장자리 정점 (기하학적 경계 감지)
- **Material 2 (skinSurface)**: 나머지 전부

---

## 리스크 및 완화

| 리스크 | 영향 | 완화 방법 |
|--------|------|----------|
| CT 세그멘테이션 품질 불균일 | 메시 위상 오류 | 검증 도구 + 수동 수정 가이드 |
| Marching Cubes 계단 아티팩트 | 비현실적 표면 | 스무딩 + 적절한 해상도 선택 |
| 대규모 메시 → 물리 성능 저하 | 실시간성 상실 | 메시 단순화 목표 설정 |
| 단일 매니폴드 요건 위반 | "Solid ordering error" | 강력한 검증 + 자동 수정 |
| .bed 매핑 부정확 | 언더마이닝 오류 | 최근접점 + 법선 방향 투영 병용 |
