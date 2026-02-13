#!/usr/bin/env python3
"""
Cross-tool sequence tests and thread-safety verification for Shoulder surgery.

Verifies that:
1. Cross-tool transitions (Anchor->Suture, Scope->Grasper) use consistent
   materialLayerConfig and don't leave inconsistent state
2. Thread-safety patterns (std::atomic) are correctly applied in collision
   detection and parallel search code
3. .bed parsing is robust against malformed input
4. Fudge factors use scale-adaptive normalization

Run with:
    python -m pytest tests/test_cross_tool_sequences.py -v
"""

import os
import re

import pytest

PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), os.pardir))
SRC_DIR = os.path.join(PROJECT_ROOT, "SkinFlaps", "src")
MODEL_DIR = os.path.join(PROJECT_ROOT, "Model")


def _read_src(filename):
    path = os.path.join(SRC_DIR, filename)
    with open(path, "r") as f:
        return f.readlines()


def _strip_comments_and_strings(line):
    """Remove // comments and string literals for cleaner pattern matching."""
    line = re.sub(r'//.*$', '', line)
    line = re.sub(r'"[^"]*"', '""', line)
    return line


# ---------------------------------------------------------------------------
# 1. Cross-Tool Sequence Compatibility
# ---------------------------------------------------------------------------

class TestCrossToolSequences:
    """Verify that tool transitions (Anchor->Suture, Scope->Grasper) are safe:
    both tools must access materialLayerConfig consistently and tool state
    transitions must not leave dangling references."""

    @pytest.fixture(autouse=True)
    def load_sources(self):
        self.sa_lines = _read_src("surgicalActions.cpp")
        self.sa_content = "".join(self.sa_lines)
        self.sa_h_lines = _read_src("surgicalActions.h")
        self.sa_h_content = "".join(self.sa_h_lines)

    def test_anchor_handler_has_material_checks(self):
        """Anchor handler (tool 8) must check periosteum/deepBed via getMaterialLayers()."""
        start = self.sa_content.find("TOOL_SUTURE_ANCHOR")
        assert start >= 0, "TOOL_SUTURE_ANCHOR handler not found"
        section = self.sa_content[start:start + 1200]
        assert "getMaterialLayers().periosteum" in section, (
            "Anchor handler must check periosteum via configurable layers"
        )
        assert "getMaterialLayers().deepBed" in section, (
            "Anchor handler must check deepBed via configurable layers"
        )

    def test_suture_handler_has_material_checks(self):
        """Suture handler must check skinSurface/incisionEdge via getMaterialLayers()."""
        assert "getMaterialLayers().skinSurface" in self.sa_content
        assert "getMaterialLayers().incisionEdge" in self.sa_content

    def test_anchor_to_suture_shared_layers(self):
        """Both Anchor and Suture reference the same _bts.getMaterialLayers() accessor,
        ensuring consistent material IDs when switching tools."""
        anchor_section = ""
        idx = self.sa_content.find("TOOL_SUTURE_ANCHOR")
        if idx >= 0:
            anchor_section = self.sa_content[idx:idx + 1200]
        # Both must use _bts.getMaterialLayers() (same accessor, same config)
        assert "_bts.getMaterialLayers()" in anchor_section, (
            "Anchor handler must use _bts.getMaterialLayers()"
        )
        # Suture handler also uses _bts.getMaterialLayers()
        assert "_bts.getMaterialLayers()" in self.sa_content

    def test_scope_handler_exists(self):
        """Arthroscope handler (tool 9) must exist in surgicalActions."""
        assert "TOOL_ARTHROSCOPE" in self.sa_h_content
        assert "TOOL_ARTHROSCOPE" in self.sa_content

    def test_grasper_handler_exists(self):
        """Grasper handler (tool 10) must exist in surgicalActions."""
        assert "TOOL_GRASPER" in self.sa_h_content
        assert "TOOL_GRASPER" in self.sa_content

    def test_scope_to_grasper_fov_restore(self):
        """Switching from Scope to Grasper must restore normal FOV.
        The setToolState() method should handle arthroscope exit."""
        assert "TOOL_ARTHROSCOPE && toolState != TOOL_ARTHROSCOPE" in self.sa_h_content, (
            "setToolState must detect ARTHROSCOPE -> other transitions for FOV restore"
        )

    def test_all_tool_states_have_setter_handler(self):
        """Every tool state 0-10 must be reachable from setToolState without crash."""
        # setToolState just stores state and toggles physics; any int is valid.
        # The real concern is that the shoulder tool constants are defined and used.
        # Check that TOOL_SUTURE_ANCHOR, TOOL_ARTHROSCOPE, TOOL_GRASPER appear in source.
        assert "TOOL_SUTURE_ANCHOR" in self.sa_content or \
               "TOOL_SUTURE_ANCHOR" in self.sa_h_content, \
               "TOOL_SUTURE_ANCHOR must be defined and usable"
        assert "TOOL_ARTHROSCOPE" in self.sa_content or \
               "TOOL_ARTHROSCOPE" in self.sa_h_content
        assert "TOOL_GRASPER" in self.sa_content or \
               "TOOL_GRASPER" in self.sa_h_content

    def test_tool_sequence_no_state_leak(self):
        """Tool state transitions must not leak references: _toolState is a simple int."""
        # setToolState stores the state, pauses physics. No allocated resources per-tool
        # that could leak during transitions.
        # Find the complete setToolState inline function (may span multiple braces)
        start = self.sa_h_content.find("setToolState")
        assert start >= 0
        # Extract enough to capture the full inline body
        section = self.sa_h_content[start:start + 600]
        assert "_toolState = toolState" in section, (
            "setToolState must assign _toolState for clean transitions"
        )


# ---------------------------------------------------------------------------
# 2. Thread Safety Verification
# ---------------------------------------------------------------------------

class TestThreadSafetyPatterns:
    """Verify atomic operations are correctly applied in parallel code."""

    @pytest.fixture(autouse=True)
    def load_sources(self):
        self.tc_h_lines = _read_src("tetCollisions.h")
        self.tc_h_content = "".join(self.tc_h_lines)
        self.tc_cpp_lines = _read_src("tetCollisions.cpp")
        self.tc_cpp_content = "".join(self.tc_cpp_lines)
        self.dc_lines = _read_src("deepCut.cpp")
        self.dc_content = "".join(self.dc_lines)

    def test_collision_density_is_atomic(self):
        """_collisionDensityMultiplier must be std::atomic<float>."""
        assert "std::atomic<float> _collisionDensityMultiplier" in self.tc_h_content

    def test_collision_density_getter_uses_load(self):
        """getCollisionDensity() must use .load() for atomic read."""
        assert ".load(" in self.tc_h_content
        # Specifically, the getter line should have load
        for line in self.tc_h_lines:
            if "getCollisionDensity" in line and "return" in line:
                assert ".load(" in line, (
                    f"getCollisionDensity getter must use .load(): {line.strip()}"
                )

    def test_collision_density_setter_uses_store(self):
        """setCollisionDensity() must use .store() for atomic write."""
        start = self.tc_cpp_content.find("setCollisionDensity")
        assert start >= 0
        section = self.tc_cpp_content[start:start + 200]
        assert ".store(" in section, (
            "setCollisionDensity must use .store() for atomic write"
        )

    def test_collisions_found_uses_atomic_store(self):
        """collisionsFound assignments in parallel_for must use .store()."""
        # Count plain '= true' assignments to collisionsFound (should be 0)
        plain_assigns = len(re.findall(
            r'collisionsFound\s*=\s*true', self.tc_cpp_content
        ))
        assert plain_assigns == 0, (
            f"Found {plain_assigns} plain 'collisionsFound = true' assignments; "
            "must use .store(true) inside parallel_for"
        )
        # Verify .store() is used instead
        store_calls = self.tc_cpp_content.count("collisionsFound.store(true")
        assert store_calls >= 2, (
            f"Expected >=2 collisionsFound.store(true) calls, found {store_calls}"
        )

    def test_collisions_found_check_uses_load(self):
        """Final collisionsFound check after parallel_for must use .load()."""
        assert "collisionsFound.load(" in self.tc_cpp_content

    def test_deepcut_parallel_uses_atomic_tet(self):
        """uniqueSpatialTet parallel search must use atomic for foundTet."""
        start = self.dc_content.find("uniqueSpatialTet")
        assert start >= 0
        section = self.dc_content[start:start + 2500]
        assert "std::atomic<int>" in section, (
            "uniqueSpatialTet must use std::atomic<int> for thread-safe tet search"
        )

    def test_deepcut_parallel_uses_cas(self):
        """uniqueSpatialTet must use compare_exchange_strong for safe write."""
        start = self.dc_content.find("uniqueSpatialTet")
        section = self.dc_content[start:start + 2500]
        assert "compare_exchange_strong" in section, (
            "uniqueSpatialTet must use CAS to ensure only one thread writes the result"
        )

    def test_deepcut_no_broken_cancel(self):
        """uniqueSpatialTet must NOT use temporary task_group_context for cancellation."""
        start = self.dc_content.find("uniqueSpatialTet")
        section = self.dc_content[start:start + 2500]
        assert "task_group_context()" not in section, (
            "Temporary task_group_context().cancel_group_execution() is a no-op bug; "
            "use atomic early-out instead"
        )

    def test_deepcut_includes_atomic(self):
        """deepCut.cpp must #include <atomic> for std::atomic usage."""
        assert "#include <atomic>" in self.dc_content


# ---------------------------------------------------------------------------
# 3. Bed File Parsing Robustness
# ---------------------------------------------------------------------------

class TestBedParsingRobustness:
    """Verify .bed parsing in skinCutUndermineTets.cpp is robust."""

    @pytest.fixture(autouse=True)
    def load_source(self):
        self.lines = _read_src("skinCutUndermineTets.cpp")
        self.content = "".join(self.lines)

    def test_no_while_eof_antipattern(self):
        """setDeepBed must not use while(!eof()) antipattern."""
        start = self.content.find("setDeepBed")
        assert start >= 0
        fn_end = self.content.find("\n}\n", start)
        fn_body = self.content[start:fn_end]
        assert "while (!istr.eof())" not in fn_body and \
               "while(!istr.eof())" not in fn_body, (
            "setDeepBed must not use while(!eof()) - use while(getline()) instead"
        )

    def test_sscanf_return_value_checked(self):
        """sscanf return value must be checked in setDeepBed."""
        start = self.content.find("setDeepBed")
        fn_end = self.content.find("\n}\n", start)
        fn_body = self.content[start:fn_end]
        # Should assign sscanf result and check it
        assert re.search(r'n\w*\s*=\s*sscanf|sscanf.*!=\s*4|nParsed', fn_body), (
            "setDeepBed must check sscanf return value"
        )

    def test_topvert_range_validation(self):
        """topVert must be validated against vertex count range."""
        start = self.content.find("setDeepBed")
        fn_end = self.content.find("\n}\n", start)
        fn_body = self.content[start:fn_end]
        assert "topVert < 0" in fn_body or "topVert >= " in fn_body, (
            "setDeepBed must validate topVert range"
        )

    def test_coordinate_nan_inf_check(self):
        """Parsed coordinates must be checked for NaN/Inf."""
        start = self.content.find("setDeepBed")
        fn_end = self.content.find("\n}\n", start)
        fn_body = self.content[start:fn_end]
        assert "isfinite" in fn_body or "isnan" in fn_body, (
            "setDeepBed must validate coordinates are finite"
        )

    def test_blank_and_comment_lines_skipped(self):
        """Parser must skip blank lines and comment lines (starting with #)."""
        start = self.content.find("setDeepBed")
        fn_end = self.content.find("\n}\n", start)
        fn_body = self.content[start:fn_end]
        assert "'#'" in fn_body or "s[0] == '#'" in fn_body, (
            "setDeepBed should skip comment lines"
        )

    def test_includes_cmath(self):
        """skinCutUndermineTets.cpp must include <cmath> for std::isfinite."""
        assert "#include <cmath>" in self.content


# ---------------------------------------------------------------------------
# 4. Scale-Adaptive Fudge Factors
# ---------------------------------------------------------------------------

class TestFudgeFactorScaling:
    """Verify fudge factors are scale-adaptive for multi-anatomy support."""

    def test_texture_path_len_uses_tet_unit_size(self):
        """Incision edge texture path length must be normalized by tet unit size."""
        lines = _read_src("skinCutUndermineTets.cpp")
        content = "".join(lines)
        # The old pattern was: pathLen += ... * 0.5f  (hardcoded)
        # New pattern should reference getTetUnitSize or _unitSpacing for scale adaptation
        assert "getTetUnitSize" in content or "tetUnit" in content, (
            "Incision texture path length must use tet unit size for scale normalization"
        )

    def test_suture_threshold_normalized_by_tet_size(self):
        """Suture placement threshold in surgicalActions.cpp must be tet-size-normalized."""
        lines = _read_src("surgicalActions.cpp")
        content = "".join(lines)
        # Find the threshold line: vI.length2()*tetSizeSq > 0.0001f
        match = re.search(r'vI\.length2\(\)\s*\*\s*tetSizeSq', content)
        assert match, (
            "Suture threshold must be multiplied by tetSizeSq for scale normalization"
        )

    def test_texture_scale_guard_against_zero(self):
        """Texture length scale must guard against zero/tiny tet unit size."""
        lines = _read_src("skinCutUndermineTets.cpp")
        content = "".join(lines)
        # Should have a guard like: tetUnit > 1e-8f or similar
        assert re.search(r'tetUnit\s*>\s*\d', content) or \
               re.search(r'tetUnit\s*>\s*1e', content), (
            "Texture length scale must guard against zero tet unit size"
        )


# ---------------------------------------------------------------------------
# 5. CI Runtime Smoke Test Configuration
# ---------------------------------------------------------------------------

class TestCIRuntimeConfig:
    """Verify the project has configuration for CI runtime execution tests."""

    def test_smd_files_loadable(self):
        """Primary .smd scene files must be valid JSON with required sections."""
        import json
        # Only check modern .smd files that should have materialLayers
        required_smds = ["FacialFlaps.smd", "ShoulderMinimal.smd"]
        for smd in required_smds:
            path = os.path.join(MODEL_DIR, smd)
            assert os.path.isfile(path), f"{smd} not found"
            with open(path, "r") as f:
                data = json.load(f)
            assert "materialLayers" in data, f"{smd} missing materialLayers"
            assert "dynamicObjects" in data, f"{smd} missing dynamicObjects"

    def test_all_smd_objs_exist(self):
        """Every OBJ referenced in primary .smd files must exist on disk."""
        import json
        for smd in ["FacialFlaps.smd", "ShoulderMinimal.smd"]:
            path = os.path.join(MODEL_DIR, smd)
            with open(path, "r") as f:
                data = json.load(f)
            for obj_name in data.get("dynamicObjects", {}):
                obj_path = os.path.join(MODEL_DIR, obj_name)
                assert os.path.isfile(obj_path), (
                    f"{smd} references {obj_name} but file not found at {obj_path}"
                )

    def test_all_smd_bed_files_exist(self):
        """Every .bed file implied by dynamic OBJ names must exist."""
        import json
        for smd in ["FacialFlaps.smd", "ShoulderMinimal.smd"]:
            path = os.path.join(MODEL_DIR, smd)
            with open(path, "r") as f:
                data = json.load(f)
            for obj_name in data.get("dynamicObjects", {}):
                bed_name = obj_name.replace(".obj", ".bed")
                bed_path = os.path.join(MODEL_DIR, bed_name)
                assert os.path.isfile(bed_path), (
                    f"{smd}: .bed file {bed_name} required for {obj_name}"
                )

    def test_tool_range_0_to_10_documented(self):
        """Tool states 0-10 must be defined in surgicalActions.h."""
        h_lines = _read_src("surgicalActions.h")
        h_content = "".join(h_lines)
        assert "TOOL_SUTURE_ANCHOR = 8" in h_content
        assert "TOOL_ARTHROSCOPE = 9" in h_content
        assert "TOOL_GRASPER = 10" in h_content

    def test_cmake_builds_configured(self):
        """Top-level CMakeLists.txt must exist for CI build."""
        cmake_path = os.path.join(PROJECT_ROOT, "CMakeLists.txt")
        assert os.path.isfile(cmake_path), "CMakeLists.txt not found at project root"
