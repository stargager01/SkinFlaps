#!/usr/bin/env python3
"""
Quick Test Runner - Framework-independent test execution.
Runs tests by importing module and test file, executing test functions.
Includes SkinFlaps domain validation for .obj, .smd, .hst, .bed, .stl files.

Usage:
    python3 quick_test.py <module_path> <test_path>
    python3 quick_test.py --validate-obj <obj_path>
    python3 quick_test.py --validate-smd <smd_path>
    python3 quick_test.py --validate-hst <hst_path>
    python3 quick_test.py --validate-stl <stl_path>
    python3 quick_test.py --validate-bed <bed_path> [--obj <obj_path>]

Example:
    python3 quick_test.py solution.py test_solution.py
    python3 quick_test.py --validate-obj Model/ShoulderSkin.obj
    python3 quick_test.py --validate-stl Model/MyModel.stl
"""
import sys
import importlib.util
import traceback
import time
import json
import struct
from pathlib import Path
from typing import Callable, List, Tuple, Optional
from collections import defaultdict

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


def validate_stl(stl_path: str) -> List[Tuple[str, bool, str]]:
    """Validate an STL file for SkinFlaps import readiness.

    Checks: file format, watertight, manifold, face count, component count.
    Uses pure Python parsing (no trimesh dependency for validation).
    """
    results = []
    path = Path(stl_path)

    if not path.exists():
        return [("file_exists", False, f"File not found: {stl_path}")]
    results.append(("file_exists", True, "OK"))

    # Detect ASCII vs Binary STL
    file_size = path.stat().st_size
    if file_size < 84:
        results.append(("file_size", False, f"File too small ({file_size} bytes)"))
        return results

    with open(path, 'rb') as f:
        header = f.read(80)
        is_ascii = header[:5] == b'solid' and b'\x00' not in header
        if not is_ascii:
            # Binary STL: 80-byte header + 4-byte triangle count + 50 bytes per tri
            f.seek(80)
            n_triangles = struct.unpack('<I', f.read(4))[0]
            expected_size = 84 + n_triangles * 50
            if file_size != expected_size:
                # Could still be ASCII that doesn't start with "solid"
                is_ascii = True

    results.append(("format_detected", True,
                     f"{'ASCII' if is_ascii else 'Binary'} STL ({file_size} bytes)"))

    # Parse triangles (use trimesh if available, else basic parse)
    vertices = []
    faces = []

    try:
        import trimesh
        mesh = trimesh.load(stl_path, force='mesh')
        vertices = mesh.vertices
        faces = mesh.faces
        n_verts = len(vertices)
        n_faces = len(faces)
        is_watertight = mesh.is_watertight
        euler = mesh.euler_number

        try:
            components = mesh.split(only_watertight=False)
            n_components = len(components)
        except Exception:
            n_components = -1

        # Degenerate faces
        areas = mesh.area_faces
        n_degenerate = int((areas < 1e-12).sum())

    except ImportError:
        # Basic binary STL parse without trimesh
        with open(path, 'rb') as f:
            f.seek(80)
            n_faces_raw = struct.unpack('<I', f.read(4))[0]
            n_faces = n_faces_raw
            n_verts = n_faces * 3  # STL has per-face vertices (pre-merge)
            is_watertight = None
            euler = None
            n_components = None
            n_degenerate = None

    results.append(("has_faces", n_faces > 0, f"{n_faces} faces"))
    if n_faces > 0:
        results.append(("face_count_sufficient", n_faces >= 12,
                         f"{n_faces} faces (need >=12 for boundary+skin+periosteum)"))

    if is_watertight is not None:
        results.append(("watertight", is_watertight,
                         "Watertight" if is_watertight else
                         "NOT watertight (holes detected)"))

    if euler is not None:
        results.append(("euler_characteristic", euler == 2,
                         f"Euler number: {euler}" +
                         (" (expected 2)" if euler != 2 else "")))

    if n_components is not None and n_components >= 0:
        results.append(("single_component", n_components == 1,
                         f"{n_components} connected component(s)" +
                         (" (need exactly 1)" if n_components != 1 else "")))

    if n_degenerate is not None:
        results.append(("no_degenerate", n_degenerate == 0,
                         f"{n_degenerate} degenerate (zero-area) faces"))

    # Non-manifold edge check (if trimesh was available)
    if len(faces) > 0 and hasattr(faces, '__len__'):
        edge_count = defaultdict(int)
        for face in faces:
            for i in range(3):
                e = tuple(sorted([int(face[i]), int(face[(i + 1) % 3])]))
                edge_count[e] += 1
        non_manifold = sum(1 for c in edge_count.values() if c > 2)
        results.append(("manifold_edges", non_manifold == 0,
                         f"{non_manifold} non-manifold edges" if non_manifold > 0
                         else "All edges manifold"))

    return results


def validate_bed(bed_path: str, obj_path: str = None) -> List[Tuple[str, bool, str]]:
    """Validate a .bed (deep bed) file.

    Optionally cross-checks vertex count against an OBJ file.
    """
    results = []
    path = Path(bed_path)

    if not path.exists():
        return [("file_exists", False, f"File not found: {bed_path}")]
    results.append(("file_exists", True, "OK"))

    entries = []
    parse_errors = 0

    with open(path, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) != 4:
                parse_errors += 1
                continue
            try:
                idx = int(parts[0])
                x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                entries.append((idx, x, y, z))
            except ValueError:
                parse_errors += 1

    results.append(("parse_ok", parse_errors == 0,
                     f"{parse_errors} parse errors" if parse_errors > 0
                     else f"{len(entries)} entries parsed"))

    results.append(("has_entries", len(entries) > 0,
                     f"{len(entries)} bed entries"))

    # Check sequential indices
    if entries:
        indices = [e[0] for e in entries]
        expected = list(range(len(entries)))
        sequential = indices == expected
        results.append(("sequential_indices", sequential,
                         "Indices sequential (0..N-1)" if sequential
                         else f"Non-sequential indices (first mismatch at {next((i for i,v in enumerate(indices) if v != i), '?')})"))

    # Cross-check with OBJ vertex count
    if obj_path:
        obj_p = Path(obj_path)
        if obj_p.exists():
            n_obj_verts = 0
            with open(obj_p, 'r') as f:
                for line in f:
                    if line.startswith('v ') and not line.startswith('vt') and not line.startswith('vn'):
                        n_obj_verts += 1
            matches = len(entries) == n_obj_verts
            results.append(("matches_obj", matches,
                             f".bed entries ({len(entries)}) vs OBJ vertices ({n_obj_verts})" +
                             ("" if matches else " — MISMATCH will crash setDeepBed()")))

    return results


def run_validation(mode: str, filepath: str, extra_args: dict = None):
    """Run domain-specific validation and print results."""
    validators = {
        "--validate-obj": ("OBJ Mesh", validate_obj),
        "--validate-smd": ("SMD Scene", validate_smd),
        "--validate-hst": ("HST History", validate_hst),
        "--validate-stl": ("STL Mesh", validate_stl),
        "--validate-bed": ("BED Deep Bed", validate_bed),
    }

    label, validator = validators[mode]

    print(f"\n{BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    print(f"{CYAN}🔍 SkinFlaps {label} Validation{RESET}")
    print(f"{BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    print(f"  File: {filepath}\n")

    # Pass extra args for validators that accept them (e.g., validate_bed needs obj_path)
    if extra_args and mode == "--validate-bed":
        results = validator(filepath, **extra_args)
    else:
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
        print(f"  python3 quick_test.py --validate-stl <file.stl>")
        print(f"  python3 quick_test.py --validate-bed <file.bed> [--obj <file.obj>]")
        sys.exit(1)

    # SkinFlaps validation modes
    validation_modes = ("--validate-obj", "--validate-smd", "--validate-hst",
                        "--validate-stl", "--validate-bed")
    if sys.argv[1] in validation_modes:
        if len(sys.argv) < 3:
            print(f"{RED}Error: filepath required{RESET}")
            sys.exit(1)
        # Parse extra args for --validate-bed
        extra_args = {}
        if sys.argv[1] == "--validate-bed" and "--obj" in sys.argv:
            obj_idx = sys.argv.index("--obj")
            if obj_idx + 1 < len(sys.argv):
                extra_args["obj_path"] = sys.argv[obj_idx + 1]
        run_validation(sys.argv[1], sys.argv[2], extra_args=extra_args)
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
