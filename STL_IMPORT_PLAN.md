# STL Import Pipeline — Implementation Plan

## Goal
SkinFlaps 코드베이스에 STL 사용자 모델을 안전하게 통합하는 Python 전처리 파이프라인을 구축한다.
C++ 코드 변경 없음. 기존 검증/TDD 인프라와 완전 호환.

---

## Phase 1: STL → OBJ Converter (`tools/convert_stl_to_obj.py`, ~350 lines)

### 1.1 Core Conversion
- **입력**: ASCII/Binary STL
- **출력**: SkinFlaps 호환 OBJ (`v/vt` + `usemtl <int>` + `s 1`)
- **의존성**: trimesh, numpy
- **처리 순서**:
  1. `trimesh.load()` → STL 파싱
  2. `remove_degenerate_faces()` → zero-area face 제거
  3. `merge_vertices()` → STL face-soup 정점 통합
  4. non-manifold edge/vertex 감지 및 수리
  5. `fix_normals()` → outward-facing 법선 통일
  6. UV 합성 (planar 기본값)
  7. Material 할당 ({1,2,7})
  8. OBJ 출력 (**1-based 인덱스**, `s 1` 포함)

### 1.2 UV 합성 (`--uv-method`)
- **기본: `planar`** — seam 없음, 가장 안정적
- 옵션: `planar` | `spherical` | `cylindrical`
- SkinFlaps는 텍스처를 시각적으로만 사용 → seam 품질보다 안정성 우선

### 1.3 Material 할당 (`--material-mode`)
- **`manual`**: 전체 `usemtl 2` → 사용자 수동 편집
- **`auto`**: `merge_shoulder_layers.py` 알고리즘 재사용 (법선+위치 기반)
- **`interactive`**: 영역별 face 수 표시 후 확인

### 1.4 Mesh Quality Checks (변환 중 자동)
- 종횡비 > 30 경고, face 수 > 20K 경고
- Euler V-E+F=2, connected components=1 검증
- 선택적 decimation (`--decimate N`)

### 1.5 Smoothing Group
- **항상 `s 1` 출력** — `readObjFile()` 파싱 필수

---

## Phase 2: .bed 생성기 일반화 (`tools/generate_bed.py`, ~150 lines)

- `generate_shoulder_bed.py`의 KD-tree 알고리즘을 일반화
- `--reference-obj`: 별도 deep bed OBJ → closest-point projection
- `--offset`: 법선 방향 오프셋 자동 생성 (기본 -5mm)
- 검증: `.bed` 항목 수 == OBJ 정점 수

---

## Phase 3: .smd 템플릿 생성기 (`tools/generate_smd.py`, ~120 lines)

- OBJ 파일명 기반 최소 .smd 자동 생성
- `--anatomy generic|facial|shoulder` → 기본 파라미터 프리셋
- `quick_test.py --validate-smd`로 자동 검증

---

## Phase 4: 검증 파이프라인 확장

### 4.1 `quick_test.py --validate-stl` 추가 (~40 lines)
- watertight, manifold, face count 검증
- 기존 `--validate-obj/smd/hst` 패턴 동일

### 4.2 TDD 스킬 확장
- VALIDATE-STL 단계 + `.stl` 자동 감지 + failure patterns

### 4.3 `tools/fix_stl_manifold.py` (~100 lines)
- Non-manifold edge/vertex 분할, hole 채움

---

## Phase 5: 테스트 (`tests/test_stl_import.py`, ~250 lines)

- Binary/ASCII STL 변환, degenerate 제거, material 할당
- UV 합성, decimation, 1-based index, `s 1` 확인
- .bed/.smd 생성 검증, 전체 파이프라인 통합 테스트
- 테스트 fixtures: test_sphere.stl, test_nonmanifold.stl, test_degenerate.stl

---

## Phase 6: 사용자 가이드 (`docs/stl_import_guide.md`)

- 워크플로우, 커맨드 레퍼런스, material 할당 가이드, 트러블슈팅

---

## 파일 변경 요약

| 파일 | 액션 | 추정 |
|------|------|------|
| `tools/convert_stl_to_obj.py` | 신규 | ~350 lines |
| `tools/generate_bed.py` | 신규 | ~150 lines |
| `tools/generate_smd.py` | 신규 | ~120 lines |
| `tools/fix_stl_manifold.py` | 신규 | ~100 lines |
| `scripts/quick_test.py` | 수정 | +40 lines |
| `.claude/skills/tdd-loop-assistant/SKILL.md` | 수정 | +20 lines |
| `tests/test_stl_import.py` | 신규 | ~250 lines |
| `tests/fixtures/*.stl` | 신규 | 3 files |
| `docs/stl_import_guide.md` | 신규 | ~200 lines |
| `requirements.txt` | 수정 | +2 lines |
| **C++ 코드** | **없음** | 0 lines |

## 위험 요소

| 위험 | 완화 |
|------|------|
| trimesh UV unwrap 불안정 | planar projection 기본값 |
| Non-manifold vertex (bowtie) | fix_stl_manifold.py + vertex manifold 체크 |
| STL 법선 vs 정점 순서 불일치 | fix_normals() → fix_obj_winding.py 이중 검증 |
| 과다 메시 (>20K faces) | --decimate + 경고 |
| .bed 정점 수 불일치 | 자동 카운트 비교 검증 |
