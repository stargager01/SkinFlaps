#!/usr/bin/env python3
"""
Quick Test Runner - Framework-independent test execution.
Runs tests by importing module and test file, executing test functions.
Includes SkinFlaps domain validation for .obj, .smd, .hst, .bed files.

Usage:
    python3 quick_test.py <module_path> <test_path>
    python3 quick_test.py --validate-obj <obj_path>
    python3 quick_test.py --validate-smd <smd_path>
    python3 quick_test.py --validate-hst <hst_path>

Example:
    python3 quick_test.py solution.py test_solution.py
    python3 quick_test.py --validate-obj Model/ShoulderSkin.obj
"""
import sys
import importlib.util
import traceback
import time
import json
from pathlib import Path
from typing import Callable, List, Tuple, Optional

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def load_module(path: str, name: str):
    """Dynamically load a Python module from file path."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def discover_tests(test_module) -> List[Tuple[str, Callable]]:
    """Find all test functions (starting with 'test_') in a module."""
    tests = []
    for name in dir(test_module):
        if name.startswith("test_"):
            func = getattr(test_module, name)
            if callable(func):
                tests.append((name, func))
    return sorted(tests, key=lambda x: x[0])


def run_single_test(name: str, func: Callable) -> Tuple[bool, str, float]:
    """Run a single test and return (passed, message, duration)."""
    start = time.perf_counter()
    try:
        func()
        duration = time.perf_counter() - start
        return True, "PASSED", duration
    except AssertionError as e:
        duration = time.perf_counter() - start
        tb = traceback.format_exc()
        return False, f"ASSERTION FAILED:\n{tb}", duration
    except Exception as e:
        duration = time.perf_counter() - start
        tb = traceback.format_exc()
        return False, f"ERROR:\n{tb}", duration


# ── SkinFlaps Domain Validators ──────────────────────────────────────


def validate_obj(obj_path: str) -> List[Tuple[str, bool, str]]:
    """Validate an OBJ file for SkinFlaps compatibility.

    Returns list of (check_name, passed, message)."""
    results = []
    path = Path(obj_path)

    if not path.exists():
        return [("file_exists", False, f"File not found: {obj_path}")]
    results.append(("file_exists", True, "OK"))

    vertices = []
    faces = []
    materials_used = set()
    current_material = None

    with open(path, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if line.startswith('v '):
                parts = line.split()
                if len(parts) >= 4:
                    vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
            elif line.startswith('f '):
                parts = line.split()[1:]
                face_verts = [int(p.split('/')[0]) for p in parts]
                faces.append((face_verts, current_material))
            elif line.startswith('usemtl '):
                try:
                    current_material = int(line.split()[1])
                    materials_used.add(current_material)
                except ValueError:
                    pass

    results.append(("vertex_count", len(vertices) > 0,
                     f"{len(vertices)} vertices"))
    results.append(("face_count", len(faces) > 0,
                     f"{len(faces)} faces"))

    # Check allowed materials (1=boundary, 2=skin, 7=periosteum)
    allowed = {1, 2, 7}
    disallowed = materials_used - allowed
    results.append(("material_ids", len(disallowed) == 0,
                     f"Materials: {materials_used}" +
                     (f" — DISALLOWED: {disallowed}" if disallowed else "")))

    # Check boundary and periosteum existence
    has_boundary = 1 in materials_used
    has_periosteum = 7 in materials_used
    results.append(("has_boundary", has_boundary,
                     "Material 1 (boundary) " +
                     ("present" if has_boundary else "MISSING — solver will fail")))
    results.append(("has_periosteum", has_periosteum,
                     "Material 7 (periosteum) " +
                     ("present" if has_periosteum else "MISSING — no fixed vertices")))

    # Check manifold: edge shared by exactly 2 faces
    edge_count = {}
    for face_verts, _ in faces:
        n = len(face_verts)
        for i in range(n):
            e = tuple(sorted([face_verts[i], face_verts[(i + 1) % n]]))
            edge_count[e] = edge_count.get(e, 0) + 1

    boundary_edges = sum(1 for c in edge_count.values() if c != 2)
    V = len(vertices)
    E = len(edge_count)
    F = len(faces)
    euler = V - E + F

    results.append(("manifold_edges", boundary_edges == 0,
                     f"Boundary edges: {boundary_edges}" +
                     (" (not manifold)" if boundary_edges > 0 else "")))
    results.append(("euler_characteristic", euler == 2,
                     f"V-E+F = {V}-{E}+{F} = {euler}" +
                     (" (expected 2)" if euler != 2 else "")))

    return results


def validate_smd(smd_path: str) -> List[Tuple[str, bool, str]]:
    """Validate an .smd scene file."""
    results = []
    path = Path(smd_path)

    if not path.exists():
        return [("file_exists", False, f"File not found: {smd_path}")]

    try:
        with open(path, 'r') as f:
            data = json.load(f)
        results.append(("json_valid", True, "Valid JSON"))
    except json.JSONDecodeError as e:
        return [("json_valid", False, f"JSON parse error: {e}")]

    # Required sections
    has_dynamic = "dynamicObjects" in data and isinstance(data["dynamicObjects"], dict)
    results.append(("has_dynamicObjects", has_dynamic,
                     "dynamicObjects " + ("present" if has_dynamic else "MISSING")))

    has_tet = "tetrahedralProperties" in data and isinstance(data["tetrahedralProperties"], dict)
    results.append(("has_tetrahedralProperties", has_tet,
                     "tetrahedralProperties " + ("present" if has_tet else "MISSING")))

    # Check materialLayers uniqueness
    if "materialLayers" in data and isinstance(data["materialLayers"], dict):
        ml = data["materialLayers"]
        values = [v for v in ml.values() if isinstance(v, int) and v > 0]
        unique = len(values) == len(set(values))
        results.append(("materialLayers_unique", unique,
                         f"materialLayers values: {values}" +
                         (" — DUPLICATES" if not unique else "")))

    # Check tet properties ranges
    if has_tet:
        tp = data["tetrahedralProperties"]
        if "minStrain" in tp and "maxStrain" in tp:
            valid = tp["minStrain"] < tp["maxStrain"]
            results.append(("strain_range", valid,
                             f"minStrain={tp['minStrain']} < maxStrain={tp['maxStrain']}" +
                             ("" if valid else " — INVALID")))

    return results


def validate_hst(hst_path: str) -> List[Tuple[str, bool, str]]:
    """Validate a .hst history file."""
    results = []
    path = Path(hst_path)

    if not path.exists():
        return [("file_exists", False, f"File not found: {hst_path}")]

    try:
        with open(path, 'r') as f:
            data = json.load(f)
        results.append(("json_valid", True, "Valid JSON"))
    except json.JSONDecodeError as e:
        return [("json_valid", False, f"JSON parse error: {e}")]

    is_array = isinstance(data, list)
    results.append(("is_array", is_array, "Top-level is " + ("array" if is_array else "NOT array")))

    if not is_array or len(data) == 0:
        return results

    # First action must be loadSceneFile
    first = data[0]
    has_load = isinstance(first, dict) and "loadSceneFile" in first
    results.append(("first_is_loadScene", has_load,
                     "First action: " + (str(first) if has_load else "NOT loadSceneFile")))

    # Each action has exactly one key
    recognized = {
        "loadSceneFile", "addHook", "moveHook", "deleteHook",
        "makeIncision", "undermine", "excise",
        "addSuture", "deleteSuture",
        "makeDeepCut", "periostealUndermine",
        "promoteSutureApproximations", "pausePhysics"
    }

    bad_keys = []
    unrecognized = set()
    for i, action in enumerate(data):
        if isinstance(action, dict):
            keys = list(action.keys())
            if len(keys) != 1:
                bad_keys.append(i)
            for k in keys:
                if k not in recognized:
                    unrecognized.add(k)

    results.append(("single_key_per_action", len(bad_keys) == 0,
                     f"Actions with != 1 key: {bad_keys[:5]}" if bad_keys else "All actions have single key"))
    results.append(("recognized_actions", len(unrecognized) == 0,
                     f"Unrecognized: {unrecognized}" if unrecognized else "All action types recognized"))

    return results


def run_validation(mode: str, filepath: str):
    """Run domain-specific validation and print results."""
    validators = {
        "--validate-obj": ("OBJ Mesh", validate_obj),
        "--validate-smd": ("SMD Scene", validate_smd),
        "--validate-hst": ("HST History", validate_hst),
    }

    label, validator = validators[mode]

    print(f"\n{BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    print(f"{CYAN}🔍 SkinFlaps {label} Validation{RESET}")
    print(f"{BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    print(f"  File: {filepath}\n")

    results = validator(filepath)

    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)

    for name, ok, msg in results:
        icon = f"{GREEN}✓{RESET}" if ok else f"{RED}✗{RESET}"
        print(f"  {icon} {name}: {msg}")

    print(f"\n{BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    if failed == 0:
        print(f"{GREEN}{BOLD}✅ 모든 검증 통과{RESET} ({passed}/{len(results)})\n")
    else:
        print(f"{RED}{BOLD}❌ 검증 실패{RESET} ({passed} passed, {failed} failed)\n")

    sys.exit(0 if failed == 0 else 1)


# ── Main ─────────────────────────────────────────────────────────────


def main():
    if len(sys.argv) < 2:
        print(f"{YELLOW}Usage:{RESET}")
        print(f"  python3 quick_test.py <module.py> <test_module.py>")
        print(f"  python3 quick_test.py --validate-obj <file.obj>")
        print(f"  python3 quick_test.py --validate-smd <file.smd>")
        print(f"  python3 quick_test.py --validate-hst <file.hst>")
        sys.exit(1)

    # SkinFlaps validation modes
    if sys.argv[1] in ("--validate-obj", "--validate-smd", "--validate-hst"):
        if len(sys.argv) < 3:
            print(f"{RED}Error: filepath required{RESET}")
            sys.exit(1)
        run_validation(sys.argv[1], sys.argv[2])
        return

    # Standard test mode
    if len(sys.argv) < 3:
        print(f"{YELLOW}Usage: python3 quick_test.py <module.py> <test_module.py>{RESET}")
        sys.exit(1)

    module_path = Path(sys.argv[1]).resolve()
    test_path = Path(sys.argv[2]).resolve()

    if not module_path.exists():
        print(f"{RED}Error: Module file not found: {module_path}{RESET}")
        sys.exit(1)
    if not test_path.exists():
        print(f"{RED}Error: Test file not found: {test_path}{RESET}")
        sys.exit(1)

    sys.path.insert(0, str(module_path.parent))

    print(f"\n{BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    print(f"{CYAN}🧪 TDD Loop - Quick Test Runner{RESET}")
    print(f"{BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}\n")

    try:
        print(f"📦 Loading module: {module_path.name}")
        solution_module = load_module(str(module_path), module_path.stem)

        print(f"📦 Loading tests: {test_path.name}\n")
        test_module = load_module(str(test_path), test_path.stem)
    except Exception as e:
        print(f"{RED}❌ Failed to load modules:{RESET}")
        print(traceback.format_exc())
        sys.exit(1)

    tests = discover_tests(test_module)

    if not tests:
        print(f"{YELLOW}⚠️  No test functions found (functions starting with 'test_'){RESET}")
        sys.exit(1)

    print(f"Found {len(tests)} test(s)\n")
    print(f"{BOLD}Running tests...{RESET}\n")

    passed = 0
    failed = 0
    failures = []
    total_time = 0

    for name, func in tests:
        success, message, duration = run_single_test(name, func)
        total_time += duration

        if success:
            passed += 1
            print(f"  {GREEN}✓{RESET} {name} ({duration*1000:.1f}ms)")
        else:
            failed += 1
            print(f"  {RED}✗{RESET} {name} ({duration*1000:.1f}ms)")
            failures.append((name, message))

    print(f"\n{BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")

    if failed == 0:
        print(f"\n{GREEN}{BOLD}✅ 모든 테스트 통과{RESET}")
        print(f"   {passed}/{len(tests)} tests passed in {total_time*1000:.1f}ms\n")
    else:
        print(f"\n{RED}{BOLD}❌ 테스트 실패{RESET}")
        print(f"   {passed} passed, {failed} failed in {total_time*1000:.1f}ms\n")
        print(f"{BOLD}Failure Details:{RESET}\n")
        for name, message in failures:
            print(f"{RED}── {name} ──{RESET}")
            for line in message.split('\n'):
                print(f"   {line}")
            print()

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
