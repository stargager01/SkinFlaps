# SkinFlaps Validation Checks Reference

TDD 루프에서 SkinFlaps 도메인이 감지될 때 자동으로 포함되는 검증 항목입니다.

## 1. OBJ 메시 무결성 검증

### 필수 조건
- [ ] 단일 연결 컴포넌트 (face adjacency graph에서 component = 1)
- [ ] 폐합 매니폴드 (Euler 특성: V - E + F = 2, genus 0)
- [ ] 경계 엣지 없음 (모든 엣지가 정확히 2개 면에 공유)
- [ ] 일관된 CCW(반시계) 면 와인딩 (OpenGL 규약)
- [ ] Material ID가 허용 범위 내: 1(boundary), 2(skin), 7(periosteum)
- [ ] Material 5(deepBed)가 OBJ에 포함되지 않음 (런타임 BCC tet cutter가 할당)

### 검증 명령
```bash
python3 tests/validate_obj.py path/to/model.obj
```

### 와인딩 자동 수정
```bash
python3 tools/fix_obj_winding.py path/to/model.obj
```
BFS 기반으로 반전된 면 법선을 일괄 수정합니다.

### 단일 매니폴드 확인 방법
```python
def check_single_manifold(faces, vertices):
    """면 인접 그래프로 연결 컴포넌트 수 확인"""
    # 1. edge→face 매핑 구축
    # 2. BFS/DFS로 연결 컴포넌트 탐색
    # 3. component_count == 1 확인
    # 4. V - E + F == 2 확인
    pass
```

### 자주 발생하는 OBJ 문제
| 증상 | 원인 | 해결 |
|------|------|------|
| `getConnectedComponents` "Solid ordering error" | 분리된 쉘 2개 (피부 돔 + 딥베드 돔) | boundary strip으로 두 림을 연결 |
| 면이 안쪽에서만 보임 | 와인딩 방향 반전 | `fix_obj_winding.py` 실행 |
| 물리 solver singular matrix | material 1/7 삼각형 없음 | boundary + periosteum 면 추가 |
| 봉합/훅 도구 crash | fixedVertices 비어 있음 | periosteum 면 최소 1개 이상 보장 |

---

## 2. .smd 씬 파일 검증

### JSON 구조 검증
```bash
python3 -m json.tool path/to/scene.smd
```

### 필수 섹션
- [ ] `dynamicObjects` (Object) — 최소 1개의 동적 OBJ 참조
- [ ] `tetrahedralProperties` (Object) — 물리 파라미터

### 선택적 섹션
- `sceneName` — AnatomyType 자동 감지에 사용
- `staticObjects` — 충돌체 (GPU 렌더링 전용)
- `textureFiles` — 텍스처 매핑
- `materialLayers` — 커스텀 material ID 매핑
- `tissueRegions` — 조직별 strain limit
- `fixedCollisionSets` — 충돌 프록시

### tetrahedralProperties 13개 필드 범위

| 필드 | 기본값 | 유효 범위 | 설명 |
|------|--------|-----------|------|
| `minStrain` | 0.8 | 0.0–1.0 | 최소 압축 한계 |
| `maxStrain` | 1.26 | 1.0–5.0 | 최대 신장 한계 |
| `lowTetWeight` | 500.0 | > 0 | 저해상도 tet 강성 |
| `highTetWeight` | 1000.0 | > 0 | 고해상도 tet 강성 |
| `TJunctionWeight` | 50.0 | ≥ 0 | T-junction 제약 가중치 |
| `collisionWeight` | 40000.0 | > 0 | 충돌 가중치 |
| `selfCollisionWeight` | 80000.0 | > 0 | 자기 충돌 가중치 |
| `fixedWeight` | 10000.0 | > 0 | 고정 정점 가중치 |
| `periferalWeight` | 1000.0 | > 0 | 주변부 구속 가중치 |
| `hookWeight` | 1000.0 | > 0 | 훅 스프링 가중치 |
| `sutureWeight` | 2000.0 | > 0 | 봉합 가중치 |
| `autoSutureSpacing` | 0.14 | > 0 | 자동 봉합 간격 |
| `nTetSizeLevels` | 4 | 1–4 | 격자 해상도 수준 |
| `maxDimMegatetSubdivs` | 34 | 16–64 | 최장 축 메가텟 분할 수 |

### materialLayers 정합성
- 모든 값은 양의 정수이고 고유해야 함
- `validateScene()` 호출로 참조 파일 존재 확인
- 어깨 모델: tendon=11, jointCapsule=12, boneSurface=13 선언 확인

### AnatomyType 자동 감지 규칙
- `sceneName`에 "Shoulder" 또는 "shoulder" 포함 → `SHOULDER`
- `sceneName`에 "Facial" 또는 "Face" 포함 → `FACIAL`
- 그 외 → `GENERIC`

---

## 3. .hst 히스토리 파일 검증

### 구조 규칙
- [ ] 최상위는 JSON 배열
- [ ] 첫 번째 요소는 반드시 `{"loadSceneFile": "..."}`
- [ ] 각 요소는 정확히 하나의 키를 가진 객체
- [ ] 액션 순서 보존 (재정렬 금지)

### 좌표/인덱스 검증
- [ ] `historyTexture` UV 값이 [0, 1] 범위
- [ ] `displacement`는 3-요소 float 배열
- [ ] `pointNumber`가 후속 포인트 객체 수와 일치
- [ ] `hookNum`, `sutureNum`은 0-기반 순차 인덱스

### 인식되는 액션 타입 (13가지)
```
loadSceneFile, addHook, moveHook, deleteHook,
makeIncision, undermine, excise,
addSuture, deleteSuture,
makeDeepCut, periostealUndermine,
promoteSutureApproximations, pausePhysics
```

### 어깨 확장 액션
어깨 모델에서는 다음 도구 액션이 추가로 기록됩니다:
- `addHook` + `strongHook: true` → Grasp 도구 (Tool ID 10)
- Anchor 배치는 표준 hook 시스템 + material 5/7/8 대상
- Scope 진입/퇴출은 FOV 변경으로 기록 (별도 히스토리 액션 없음)

### 검증 명령
```bash
python3 tests/validate_history.py path/to/procedure.hst
```

---

## 4. .bed 파일 검증

### 구조
- 텍스트 파일, 한 줄에 하나의 3D 좌표 (x y z)
- 줄 수 = 동적 OBJ의 정점 수와 정확히 일치
- 파일명 = 동적 OBJ 기본 이름 + `.bed` (예: `ShoulderSkin.obj` → `ShoulderSkin.bed`)

### 검증 항목
- [ ] 파일 존재 + OBJ 기본 이름 일치
- [ ] 줄 수 = OBJ 정점 수
- [ ] 각 줄이 3개의 float 값

---

## 5. Material Layer 간 정합성 매트릭스

OBJ, .smd, C++ 코드 간 material ID가 일관되어야 합니다:

```
OBJ usemtl → .smd materialLayers → C++ materialLayerConfig → 런타임 검증
     1     →   boundary: 1       →   .boundary = 1        →   fixPeriferal()
     2     →   skinSurface: 2    →   .skinSurface = 2     →   isSkinSurface()
     7     →   periosteum: 7     →   .periosteum = 7      →   isPeriosteal()
   (없음)  →   deepBed: 5        →   .deepBed = 5         →   .bed 런타임 생성
   (없음)  →   incisionEdge: 3   →   .incisionEdge = 3    →   skinCut() 생성
   (없음)  →   subcutaneous: 4   →   .subcutaneous = 4    →   skinCut() 생성
   (없음)  →   muscle: 6         →   .muscle = 6          →   deepCut() 생성
```

### 정합성 검증 테스트 패턴
```python
def test_material_consistency(obj_path, smd_path):
    """OBJ의 usemtl 값이 .smd materialLayers와 일치하는지 확인"""
    obj_materials = parse_obj_materials(obj_path)
    smd_layers = parse_smd_material_layers(smd_path)

    # OBJ에는 boundary(1), skinSurface(2), periosteum(7)만 있어야 함
    allowed_in_obj = {
        smd_layers.get('boundary', 1),
        smd_layers.get('skinSurface', 2),
        smd_layers.get('periosteum', 7),
    }
    assert obj_materials.issubset(allowed_in_obj), \
        f"OBJ에 허용되지 않는 material ID: {obj_materials - allowed_in_obj}"

    # boundary와 periosteum 최소 존재 확인
    assert smd_layers.get('boundary', 1) in obj_materials, \
        "Material 1 (boundary) 삼각형이 OBJ에 없음 → solver 실패 위험"
    assert smd_layers.get('periosteum', 7) in obj_materials, \
        "Material 7 (periosteum) 삼각형이 OBJ에 없음 → fixedVertices 비어 있음"
```

---

## 6. 테스트 우선순위 가이드

SkinFlaps 도메인에서의 TDD 루프 진행 순서:

```
1단계: 파일 형식 검증 (JSON lint, OBJ manifold)
  ↓ 통과
2단계: Material 정합성 검증 (OBJ ↔ .smd ↔ .bed)
  ↓ 통과
3단계: 기능 단위 테스트 (도구 동작, 물리 파라미터)
  ↓ 통과
4단계: 통합 테스트 (히스토리 녹화/재생, 씬 로드)
  ↓ 통과
5단계: 선택적 품질 개선 (메시 해상도, 성능 최적화)
```
