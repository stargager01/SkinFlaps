---
name: tdd-loop-assistant
description: >
  Automated test-driven development assistant that writes code, runs tests,
  analyzes failures, and iteratively fixes code until all tests pass.
  Specialized for the SkinFlaps surgical simulation project (C++/Python/JSON)
  with domain-aware validation for OBJ meshes, .smd/.hst file formats,
  material layer configurations, and physics parameters.
  Triggers when users need to:
  (1) write code with automatic test verification,
  (2) debug failing tests with iterative fixes,
  (3) implement features using TDD workflow,
  (4) validate SkinFlaps file formats (.obj, .smd, .hst, .bed),
  (5) verify mesh integrity (manifold, winding, material IDs),
  (6) test surgical tool implementations or physics parameters,
  (7) create robust code through test-driven iterations.
  Supports Python (pytest), JavaScript (Jest), C++ (CMake/CTest), and
  SkinFlaps-specific validation scripts. Always use this skill when the user
  mentions TDD, test loops, iterative debugging, validation scripts, or
  asks to verify SkinFlaps models/files.
---

# TDD Loop Assistant

자동 테스트-수정 루프를 통해 견고한 코드를 작성하는 개발 도우미 스킬입니다.
SkinFlaps 수술 시뮬레이터 프로젝트에 특화된 도메인 검증을 포함합니다.

## Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│  1. ANALYZE → 요구사항 분석 + 도메인 감지 (SkinFlaps / General) │
│       ↓                                                         │
│  2. CODE → 초기 구현 작성                                       │
│       ↓                                                         │
│  3. VALIDATE → 도메인 사전 검증 (SkinFlaps인 경우)              │
│       ↓                                                         │
│  4. TEST → 테스트 실행                                          │
│       ↓                                                         │
│  5. DIAGNOSE → 실패 분석 (실패 시)                              │
│       ↓                                                         │
│  6. FIX → 코드 수정                                             │
│       ↓                                                         │
│  └──→ 4번으로 돌아가기 (모든 테스트 통과할 때까지)              │
│       ↓                                                         │
│  7. ENHANCE → 성능/보안/메시 품질 개선 (선택)                   │
│       ↓                                                         │
│  ✅ 완료                                                        │
└─────────────────────────────────────────────────────────────────┘
```

## Domain Detection

작업 시작 시 도메인을 자동으로 감지합니다:

| 트리거 | 도메인 | 추가 검증 |
|--------|--------|-----------|
| `.obj`, `.smd`, `.hst`, `.bed` 파일 언급 | SkinFlaps | 메시/파일 형식 검증 포함 |
| `materialTriangles`, `deepCut`, `bccTetScene` 등 클래스 언급 | SkinFlaps C++ | 빌드 + 단위 테스트 |
| `materialLayerConfig`, material ID, tissue region 언급 | SkinFlaps Config | JSON 스키마 + 정합성 검증 |
| `validate_obj.py`, `validate_history.py` 언급 | SkinFlaps Validation | 기존 검증 스크립트 활용 |
| 일반 Python/JS/TS 코드 | General | 표준 TDD 루프 |

## Output Format

각 반복(iteration)마다 아래 형식으로 출력:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔄 Iteration [N]  [도메인: SkinFlaps / General]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 요구사항
[사용자 요구사항 요약]

🔍 사전 검증 (SkinFlaps 도메인 시)
[파일 형식/메시 무결성 검증 결과]

💻 코드
[코드 블록]

🧪 테스트 결과
[PASS/FAIL 상태 및 출력]

🔍 분석 (실패 시)
[실패 원인 분석 - 도메인별 진단 포함]

🔧 수정 사항 (실패 시)
[수정 내용 설명]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

최종 성공 시: `✅ 모든 테스트 통과 (N회 반복)`

## Test Execution

### Python (pytest)
```bash
cd /home/claude && pytest test_*.py -v --tb=short 2>&1
```

### JavaScript (Jest)
```bash
cd /home/claude && npx jest --verbose 2>&1
```

### C++ (CMake + CTest)
```bash
cd /home/claude/build && cmake .. -DCMAKE_BUILD_TYPE=Debug && make -j$(nproc) 2>&1
ctest --output-on-failure 2>&1
```

### SkinFlaps Validation Scripts
```bash
# OBJ 무결성 검증 (manifold, winding, materials)
python3 tests/validate_obj.py path/to/model.obj

# 히스토리 파일 검증
python3 tests/validate_history.py path/to/procedure.hst

# OBJ 면 법선 일괄 수정
python3 tools/fix_obj_winding.py path/to/model.obj
```

### Quick validation (without framework)
```bash
python3 scripts/quick_test.py <module> <test_file>
```

## SkinFlaps Domain-Specific Checks

SkinFlaps 도메인이 감지되면 테스트 루프에 아래 검증을 자동 포함합니다.
상세 체크리스트는 `references/skinflaps-checks.md`를 참조하세요.

### OBJ 메시 검증
- 단일 연결 컴포넌트 (connected component = 1)
- 폐합 매니폴드 (Euler: V-E+F = 2, 경계 엣지 = 0)
- 일관된 CCW 면 와인딩
- 허용된 Material ID만 사용 (1=boundary, 2=skin, 7=periosteum)
- Material 5(deepBed)는 OBJ에 포함하지 않음 (런타임 할당)

### .smd 씬 파일 검증
- 유효한 JSON 구문
- 필수 섹션 존재: `dynamicObjects`, `tetrahedralProperties`
- `materialLayers` 값이 양의 정수이고 고유한지 확인
- `tetrahedralProperties` 13개 필드 범위 검증
- 참조된 OBJ/텍스처 파일 존재 여부
- `AnatomyType` 자동 감지 일관성 (sceneName 기반)

### .hst 히스토리 파일 검증
- 유효한 JSON 배열
- 첫 번째 액션이 반드시 `loadSceneFile`
- 각 액션 객체에 정확히 하나의 키만 존재
- `historyTexture` UV 좌표가 [0, 1] 범위
- `pointNumber`와 실제 포인트 수 일치
- 인식된 액션 타입만 사용 (13가지)

### Material Layer 정합성
- OBJ의 `usemtl` 값과 .smd의 `materialLayers` 매핑 일치
- boundary(mat 1)과 periosteum(mat 7) 삼각형 존재 확인
- 어깨 확장 레이어(tendon=11, jointCapsule=12, boneSurface=13) 사용 시 .smd에 선언 확인

## Iteration Rules

1. **최대 반복 횟수**: 5회 (초과 시 사용자에게 확인 요청)
2. **실패 분석 필수**: 각 실패마다 root cause 설명
3. **점진적 수정**: 한 번에 하나의 문제만 해결
4. **회귀 방지**: 이전 통과 테스트가 실패하지 않도록 확인
5. **도메인 우선**: SkinFlaps 파일은 코드 테스트 전 형식 검증을 먼저 수행

## Failure Diagnosis — Domain-Specific Patterns

SkinFlaps 도메인에서 자주 발생하는 실패 패턴과 대응 방법:

| 오류 패턴 | 원인 | 수정 방향 |
|-----------|------|-----------|
| "Solid ordering error" | OBJ가 분리된 쉘(disconnected shells) | 두 레이어를 boundary strip으로 연결 |
| singular matrix / solver 실패 | material 1 또는 7 삼각형 부재 | 매니폴드 OBJ에 boundary + periosteum 추가 |
| "json mValueType==ObjectVal" | .smd JSON 파싱 오류 | JSON lint 후 타입 확인 (trailing comma 등) |
| hook/knife crash | fixedVertices 비어 있음 | `fixPeriostealPeriferalVertices()`용 앵커 확인 |
| undermine 실패 | .bed 파일 누락 또는 불일치 | .bed 파일 존재 + OBJ 기본 이름 일치 확인 |
| 앵커 배치 거부 | material 5/7/8 이외 표면 클릭 | 대상 material ID 확인 후 테스트 조건 수정 |
| deepCut topology error | 면 와인딩 불일치 | `fix_obj_winding.py`로 BFS 기반 법선 수정 |

## Edge Case Handling

- **무한 루프 감지**: 동일 오류 3회 반복 시 다른 접근법 제안
- **환경 문제**: 패키지 누락 시 설치 명령 제공
- **타임아웃**: 테스트가 30초 초과 시 최적화 제안
- **C++ 빌드 실패**: 컴파일 에러와 링크 에러를 구분하여 진단
- **메시 토폴로지 문제**: `validate_obj.py` 결과 기반으로 수정 스크립트 자동 제안

## Optional Enhancement Phases

테스트 통과 후 선택적 개선. 상세 기준은 `references/enhancement-checklist.md` 참조.

### General Enhancements
1. **성능 최적화**: 시간 복잡도 분석 및 개선
2. **보안 검토**: 입력 검증, SQL 인젝션 방지 등
3. **코드 품질**: 린팅, 타입 힌트, 문서화

### SkinFlaps-Specific Enhancements
4. **메시 품질**: 삼각형 종횡비, 정점 밀도 균일성
5. **물리 파라미터 범위**: strain limit, stiffness weight 합리성 검증
6. **히스토리 재현성**: .hst 녹화 → 재생 결정론적 동작 확인
7. **도구 상호작용**: 각 도구(Tool ID 0-10) 정상 동작 검증

## Tool ID Quick Reference

| ID | 도구 | 주요 테스트 관점 |
|----|------|-----------------|
| 0 | Viewer/Physics | 물리 시뮬레이션 일시정지/재개 |
| 1 | Hook | 조직 견인, 스프링 상수 |
| 2 | Knife | 피부 절개, 깊이 제한 |
| 3 | Undermine | 피하 박리, .bed 매핑 |
| 4 | Suture | 봉합, 간격 설정 |
| 5 | Excise | 병변 절제 |
| 6 | Deep Cut | 다층 절개, topology |
| 7 | Periosteal | 골막 박리 |
| 8 | Anchor | 봉합 앵커 (어깨 확장) |
| 9 | Scope | 관절경 FOV 0.7→0.35 |
| 10 | Grasp | 강력 조직 파지기 (어깨 확장) |
