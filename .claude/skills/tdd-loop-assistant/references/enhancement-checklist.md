# Enhancement Checklist

테스트 통과 후 적용할 수 있는 선택적 개선 항목입니다.

## 1. 성능 최적화 (Performance)

### 시간 복잡도
- [ ] 불필요한 중첩 루프 제거
- [ ] 적절한 자료구조 선택 (dict/set for O(1) lookup)
- [ ] 캐싱/메모이제이션 적용
- [ ] 조기 종료(early return) 패턴 사용

### 공간 복잡도
- [ ] 제너레이터 사용 (대용량 데이터)
- [ ] 불필요한 복사 제거
- [ ] 스트리밍 처리 적용

### 측정 기준
```python
import time
start = time.perf_counter()
# ... code ...
print(f"Elapsed: {time.perf_counter() - start:.4f}s")
```

## 2. 보안 검토 (Security)

### 입력 검증
- [ ] 타입 검증
- [ ] 범위 검증 (min/max)
- [ ] 길이 제한
- [ ] 특수문자 이스케이프

### SQL 인젝션 방지
- [ ] 파라미터화된 쿼리 사용
- [ ] ORM 사용 권장

### 파일 처리
- [ ] 경로 순회 공격 방지
- [ ] 파일 확장자 검증
- [ ] 파일 크기 제한

## 3. 코드 품질 (Code Quality)

### 문서화
- [ ] 함수 docstring 추가
- [ ] 타입 힌트 추가
- [ ] 인라인 주석 (복잡한 로직)

### 린팅
```bash
# Python
pip install ruff --break-system-packages
ruff check .

# JavaScript
npx eslint .
```

### 구조화
- [ ] 단일 책임 원칙 (SRP)
- [ ] 매직 넘버 상수화
- [ ] 중복 코드 함수 추출

## 4. 테스트 강화 (Test Coverage)

### 추가 테스트 케이스
- [ ] 경계값 테스트
- [ ] 빈 입력 테스트
- [ ] 대용량 입력 테스트
- [ ] 예외 케이스 테스트

### 커버리지 측정
```bash
pytest --cov=. --cov-report=term-missing
```

## 5. SkinFlaps 메시 품질 (Mesh Quality)

### 삼각형 품질
- [ ] 퇴화 삼각형 없음 (면적 > 0)
- [ ] 종횡비(aspect ratio) 합리적 범위 (< 10:1 권장)
- [ ] 정점 밀도 균일성 확인

### 물리 파라미터 합리성
- [ ] minStrain < maxStrain
- [ ] lowTetWeight < highTetWeight
- [ ] collisionWeight와 selfCollisionWeight 비율 합리적
- [ ] nTetSizeLevels >= 2 (프로토타이핑 최소 권장)

### 조직 영역 (Tissue Region) 검증
- [ ] 영역별 strain 범위가 전역 설정과 호환
- [ ] subsetObj가 폐합 매니폴드
- [ ] 영역 간 겹침 없음 (의도적 겹침 제외)

## 6. SkinFlaps 히스토리 재현성 (History Reproducibility)

### 결정론적 재생
- [ ] .hst 녹화 → 재생 시 동일 결과
- [ ] 액션 순서 보존
- [ ] 좌표 정밀도 충분 (float 반올림 오류 확인)

### 새 도구 히스토리 등록
- [ ] `nextHistoryAction()`에 새 액션 타입 문자열 정의
- [ ] `saveSurgicalHistory()`에 직렬화 구현
- [ ] `nextHistoryAction()` 디스패치에 역직렬화 구현
- [ ] `tests/validate_history.py`에 새 액션 타입 인식 추가
