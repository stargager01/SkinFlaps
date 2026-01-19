# SkinFlaps 초보자 체크리스트 (Beginner Checklist)

SkinFlaps 프로젝트를 처음 시작하는 분들을 위한 단계별 가이드입니다.

> **SkinFlaps**는 피부 플랩 수술(특히 구순열/구개열 교정)을 시뮬레이션하는 물리 기반 소프트웨어입니다.

---

## Quick Reference

| 단계 | 목표 | 난이도 |
|------|------|--------|
| 1. 환경 준비 | 필수/권장 도구 설치 | ⭐ |
| 2. 프로젝트 빌드 | 실행 파일 생성 | ⭐⭐ |
| 3. 예제 실행 | 기본 시뮬레이션 확인 | ⭐ |
| 4. 모델 수정 | 파라미터/메쉬 변경 실험 | ⭐⭐⭐ |
| 5. 기여 준비 | Issue/문서 기여 시작 | ⭐⭐ |

---

## 1. 환경 준비 단계

### 1.1 플랫폼 지원 현황

| 플랫폼 | 지원 | 비고 |
|--------|------|------|
| Windows 10/11 | ✅ 기본 | Visual Studio 2022 권장 |
| Ubuntu Linux | ✅ 가능 | CMake 빌드 |
| macOS | ❌ 미지원 | Intel oneAPI 미지원 (Apple Silicon) |

### 1.2 필수 도구

#### Windows (권장)

```powershell
# Visual Studio 2022 설치 확인
# "Desktop development with C++" 워크로드 필수

# Intel oneAPI 설치 (MKL + TBB)
# https://www.intel.com/content/www/us/en/developer/tools/oneapi/base-toolkit-download.html
```

**체크리스트:**
- [ ] Visual Studio 2022 설치됨 (v143 툴셋)
- [ ] "Desktop development with C++" 워크로드 선택됨
- [ ] Intel oneAPI Base Toolkit 설치됨 (MKL + TBB 포함)
- [ ] Git 설치됨

#### Linux (Ubuntu)

```bash
# 설치 확인 명령어
cmake --version        # 최소 3.8 이상
g++ --version          # C++11 지원 필수 (GCC 7+)
git --version

# Intel oneAPI 설치
# https://www.intel.com/content/www/us/en/developer/tools/oneapi/base-toolkit-download.html
source /opt/intel/oneapi/setvars.sh
```

**체크리스트:**
- [ ] CMake 3.8+ 설치됨
- [ ] GCC 7+ 또는 Clang 설치됨 (C++11 지원)
- [ ] Intel oneAPI Base Toolkit 설치됨
- [ ] GLFW3 개발 라이브러리 설치됨 (`apt install libglfw3-dev`)
- [ ] Git 설치됨

### 1.3 하드웨어 요구사항

| 항목 | 최소 | 권장 |
|------|------|------|
| CPU | Intel 64-bit (AVX 지원) | Intel Core i7+ |
| RAM | 8GB | 16GB+ |
| GPU | OpenGL 3.0 지원 | CUDA 지원 GPU |
| 저장공간 | 2GB | 10GB+ (텍스처 포함) |

**체크리스트:**
- [ ] 64-bit Intel CPU 사용 중 (AVX 명령어 지원)
- [ ] OpenGL 3.0+ 지원 그래픽 카드
- [ ] 충분한 RAM (8GB+)

### 1.4 권장 도구

| 도구 | 용도 | 설치 링크 |
|------|------|-----------|
| CUDA Toolkit 11+ | GPU 가속 (선택) | developer.nvidia.com/cuda-toolkit |
| Blender 3.0+ | 메쉬 편집, 시각화 | blender.org |
| VS Code | 코드 편집 (Linux) | code.visualstudio.com |

---

## 2. 프로젝트 빌드 단계

### 2.1 리포지토리 클론

```bash
# 리포지토리 클론
git clone https://github.com/stargater01/SkinFlaps.git
cd SkinFlaps

# 디렉토리 구조 확인
ls -la
```

**체크리스트:**
- [ ] `git clone` 성공
- [ ] 다음 디렉토리 존재 확인:
  - [ ] `SkinFlaps/src/` (메인 소스코드)
  - [ ] `PDTetPhysics/` (물리 엔진)
  - [ ] `gl3wGraphics/` (그래픽스 라이브러리)
  - [ ] `Model/` (3D 모델 파일)
  - [ ] `History/` (예제 시뮬레이션)

### 2.2 Windows 빌드 (Visual Studio 2022)

```
1. Build/msvc_2022/SkinFlaps.sln 열기
2. 솔루션 구성: Release / x64 선택
3. 빌드 → 솔루션 빌드 (Ctrl+Shift+B)

# CUDA 버전 (GPU 가속):
Build/msvc_2022/SkinFlaps_CUDA.sln 사용
```

**체크리스트:**
- [ ] `SkinFlaps.sln` 열림
- [ ] Release / x64 구성 선택됨
- [ ] 빌드 성공 (오류 0개)
- [ ] `SkinFlaps.exe` 생성됨

#### Windows 빌드 문제 해결

| 오류 | 원인 | 해결 방법 |
|------|------|-----------|
| "MKL not found" | Intel oneAPI 미설치 | oneAPI Base Toolkit 설치 |
| "TBB not found" | Intel oneAPI 미설치 | oneAPI에 TBB 포함됨 |
| "v143 toolset not found" | VS 2022 미설치 | Visual Studio 2022 설치 |
| "AVX not supported" | 구형 CPU | Intel CPU (2011년 이후) 필요 |

### 2.3 Linux 빌드 (CMake)

```bash
# Intel oneAPI 환경 설정
source /opt/intel/oneapi/setvars.sh

# 빌드 디렉토리 생성
mkdir build && cd build

# CMake 설정 (MKL 경로 자동 탐지)
cmake .. -DCMAKE_BUILD_TYPE=Release

# 빌드 실행
cmake --build . -j$(nproc)
```

**체크리스트:**
- [ ] Intel oneAPI 환경 변수 설정됨
- [ ] `cmake ..` 오류 없이 완료
- [ ] MKL/TBB 라이브러리 감지됨
- [ ] 빌드 완료 (오류 0개)
- [ ] 실행 파일 생성됨

---

## 3. 예제 실행 단계

### 3.1 프로젝트 구조 이해

```
SkinFlaps/
├── Model/                          # 3D 모델 및 텍스처
│   ├── FacialFlaps.smd            # 메인 얼굴 모델
│   ├── unilatCleftLip_complete.smd # 구순열 모델
│   ├── *.obj                       # 메쉬 파일들
│   └── *.jpg                       # 텍스처 파일들
│
├── History/                        # 사전 녹화된 수술 예제
│   ├── cleft_CuttingRepair.hst    # Dr. Cutting 구순열 교정
│   ├── cleft_FisherRepair.hst     # Fisher 기법
│   ├── foreheadFlapToNose.hst     # 이마 플랩 → 코
│   └── cervicoFacialFlap.hst      # 경안면 플랩
│
└── SkinFlaps/src/                  # 소스 코드
    ├── main.cpp                   # 진입점
    ├── FacialFlapsGui.cpp         # GUI 프레임워크
    └── surgicalActions.cpp        # 수술 도구 로직
```

### 3.2 프로그램 실행

```bash
# Windows
cd Build/msvc_2022/x64/Release
./SkinFlaps.exe

# Linux
cd build
./SkinFlaps
```

**체크리스트:**
- [ ] 프로그램 창 표시됨
- [ ] OpenGL 렌더링 정상 (3D 뷰어 표시)
- [ ] GUI 메뉴 표시됨 (ImGui 기반)

### 3.3 예제 모델 로드

```
1. File → Open Model
2. Model/ 디렉토리에서 .smd 파일 선택
   - FacialFlaps.smd (기본 얼굴)
   - unilatCleftLip_complete.smd (구순열)
3. 모델 로드 확인
```

**체크리스트:**
- [ ] 모델 파일 선택 가능
- [ ] 3D 얼굴 모델 표시됨
- [ ] 텍스처 정상 적용됨
- [ ] 카메라 조작 가능 (마우스 드래그)

### 3.4 사전 녹화된 수술 예제 재생

```
1. File → Open History
2. History/ 디렉토리에서 .hst 파일 선택
3. "NEXT" 버튼으로 단계별 재생
```

**추천 시작 예제:**

| 파일명 | 수술 기법 | 난이도 |
|--------|-----------|--------|
| `cleft_CuttingRepair.hst` | Dr. Cutting 구순열 교정 | ⭐ |
| `cleft_FisherRepair.hst` | Fisher 구순열 기법 | ⭐⭐ |
| `cervicoFacialFlap.hst` | 경안면 회전 플랩 | ⭐⭐ |
| `foreheadFlapToNose.hst` | 이마 → 코 플랩 | ⭐⭐⭐ |

**체크리스트:**
- [ ] History 파일 로드됨
- [ ] "NEXT" 버튼으로 수술 단계 진행
- [ ] 피부 절개/변형 시뮬레이션 확인
- [ ] 물리 시뮬레이션 실시간 동작 확인

### 3.5 YouTube 튜토리얼

| 주제 | 링크 |
|------|------|
| 사용자 가이드 | https://youtu.be/xuKLgMS5gzk |
| 구순열 수술 튜토리얼 | https://youtu.be/CzBiVJ5Q508 |

---

## 4. 모델 수정 단계

### 4.1 수술 도구 사용

프로그램 내 수술 도구:

| 도구 | 기능 | 단축키 |
|------|------|--------|
| Scalpel | 피부 절개 | - |
| Undermine | 피부 박리 | - |
| Deep Cut | 깊은 절개 | - |
| Suture | 봉합 | - |
| Hook | 조직 견인 | - |
| Fence | 경계 설정 | - |

**체크리스트:**
- [ ] 각 도구 선택 및 사용 가능
- [ ] 절개 후 물리 시뮬레이션 동작
- [ ] 봉합 기능 테스트

### 4.2 Blender로 커스텀 메쉬 생성

```
1. Blender 실행 → File → Import → Wavefront (.obj)
2. Model/ 디렉토리의 .obj 파일 선택
   예: unilatCompleteCleft.obj
3. Edit Mode에서 메쉬 수정:
   - G 키: 버텍스 이동
   - S 키: 스케일 조정
   - E 키: Extrude
4. File → Export → Wavefront (.obj)
   → 새 이름으로 저장 (my_model.obj)
```

**체크리스트:**
- [ ] 예제 .obj 파일 Blender에서 열림
- [ ] 메쉬 구조 이해 (버텍스, 면)
- [ ] 간단한 수정 후 내보내기 완료

### 4.3 물리 파라미터 이해

소스 코드에서 주요 물리 파라미터 (`PDTetPhysics/`):

```cpp
// PDTetSolver.h에서 주요 파라미터
struct SimulationParams {
    float timestep;         // 시뮬레이션 시간 간격
    int max_iterations;     // 최대 반복 횟수
    float tolerance;        // 수렴 허용 오차
    float young_modulus;    // Young's modulus (강성)
    float poisson_ratio;    // Poisson's ratio
    float density;          // 밀도
};
```

**파라미터 조정 효과:**

| 파라미터 | 증가 시 | 감소 시 |
|----------|---------|---------|
| `young_modulus` | 더 단단함 | 더 부드러움 |
| `timestep` | 빠른 시뮬레이션 (불안정 가능) | 안정적 (느림) |
| `max_iterations` | 더 정확함 (느림) | 덜 정확함 (빠름) |

### 4.4 소스 코드 수정

주요 소스 파일:

| 파일 | 위치 | 역할 |
|------|------|------|
| `main.cpp` | `SkinFlaps/src/` | 프로그램 진입점 |
| `surgicalActions.cpp` | `SkinFlaps/src/` | 수술 동작 로직 |
| `deepCut.cpp` | `SkinFlaps/src/` | 깊은 절개 알고리즘 |
| `sutures.cpp` | `SkinFlaps/src/` | 봉합 알고리즘 |
| `PDTetSolver.cpp` | `PDTetPhysics/src/` | 물리 솔버 |

**체크리스트:**
- [ ] 소스 코드 구조 이해
- [ ] 간단한 파라미터 수정 후 재빌드
- [ ] 변경 효과 확인

---

## 5. 기여 준비 단계

### 5.1 Issue 보고

**좋은 Issue 작성법:**

```markdown
## 환경
- OS: Windows 11 / Ubuntu 22.04
- Visual Studio: 2022 (17.x)
- Intel oneAPI: 2024.x
- GPU: NVIDIA RTX 3080

## 문제 설명
[구체적인 문제 설명]

## 재현 단계
1. 프로그램 실행
2. Model/FacialFlaps.smd 로드
3. [문제 발생 단계]

## 예상 동작
[정상적으로 기대하는 동작]

## 실제 동작
[실제 발생한 동작/오류]

## 스크린샷/로그
[관련 이미지 또는 오류 메시지]
```

**체크리스트:**
- [ ] 버그/기능요청/질문 중 유형 선택
- [ ] 환경 정보 작성
- [ ] 재현 단계 명확히 기술
- [ ] 관련 로그/스크린샷 첨부

### 5.2 코드 기여

```bash
# 1. 포크 및 클론
git clone https://github.com/YOUR_USERNAME/SkinFlaps.git
cd SkinFlaps

# 2. 피처 브랜치 생성
git checkout -b feature/my-improvement

# 3. 변경 사항 작성
# ... 코드 수정 ...

# 4. 커밋
git add .
git commit -m "feat: Add my improvement"

# 5. 푸시
git push origin feature/my-improvement

# 6. GitHub에서 Pull Request 생성
```

**기여 유형별 난이도:**

| 기여 유형 | 난이도 | 설명 |
|-----------|--------|------|
| 문서 오타 수정 | ⭐ | README, 주석 |
| 버그 리포트 | ⭐ | Issue 작성 |
| 번역 | ⭐⭐ | 문서 번역 |
| 버그 수정 | ⭐⭐⭐ | 코드 수정 |
| 새 기능 추가 | ⭐⭐⭐⭐ | 수술 도구 등 |

**체크리스트:**
- [ ] 리포지토리 포크 완료
- [ ] 피처 브랜치 생성
- [ ] 코드 스타일 준수 (기존 코드 참조)
- [ ] 변경 사항 테스트
- [ ] Pull Request 생성

### 5.3 알려진 이슈 (BugsNeedingFix.txt)

현재 개선이 필요한 영역 (`Build/msvc_2022/BugsNeedingFix.txt` 참조):
- 사용자 인터페이스 개선
- 물리 시뮬레이션 안정성
- 성능 최적화

---

## 추가 학습 리소스

### 논문 및 문서

| 주제 | 링크 |
|------|------|
| Projective Dynamics 논문 | https://www.cs.utah.edu/~ladislav/bouaziz14projective/ |
| SkinFlaps 물리 구현 논문 | https://onlinelibrary.wiley.com/doi/10.1111/cgf.14385 |
| 메인 프로젝트 논문 (2022) | https://doi.org/10.1016/j.cmpb.2022.106730 |

### 도구 학습

| 주제 | 리소스 |
|------|--------|
| CMake 기초 | cmake.org/cmake/help/latest/guide/tutorial |
| Intel MKL 문서 | software.intel.com/content/www/us/en/develop/documentation/onemkl-developer-reference |
| Blender 메쉬 편집 | docs.blender.org/manual/en/latest/modeling |
| Git 협업 | learngitbranching.js.org |

---

## 문제 해결 FAQ

### Q: "MKL not found" 오류

**A:** Intel oneAPI Base Toolkit 설치 후 환경 변수 설정:
```bash
# Linux
source /opt/intel/oneapi/setvars.sh

# Windows
# Visual Studio에서 자동 감지, 또는 시스템 환경 변수에 MKL 경로 추가
```

### Q: 시뮬레이션이 느림

**A:**
1. Release 빌드 사용 (Debug 아님)
2. CUDA 버전 사용 (`SkinFlaps_CUDA.sln`)
3. 멀티스레딩 활성화 확인 (TBB)

### Q: macOS에서 빌드 불가

**A:** 현재 macOS는 지원되지 않습니다 (Intel oneAPI가 Apple Silicon 미지원).

### Q: 텍스처가 표시되지 않음

**A:** `Model/` 디렉토리의 .jpg 파일 존재 확인. 고해상도 텍스처 파일(normal.jpg 등)이 필요합니다.

---

## 버전 정보

- **SkinFlaps 버전**: 1.2.1
- **문서 작성일**: 2024
- **라이선스**: BSD-2-Clause

---

## 연락처

- **물리 엔진**: Qisi Wang, Eftychios Sifakis (UW-Madison)
- **수술 인터페이스**: Court Cutting MD (NYU Grossman)
- **GitHub Issues**: https://github.com/stargater01/SkinFlaps/issues
