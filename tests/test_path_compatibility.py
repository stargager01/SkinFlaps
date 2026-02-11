#!/usr/bin/env python3
"""
Tests for Linux path compatibility in SkinFlaps.

Validates that path construction in the codebase uses platform-appropriate
separators and that all referenced files are accessible with forward-slash
paths (Linux/macOS compatible).
"""

import json
import os
import re
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(PROJECT_ROOT, "Model")
SRC_DIR = os.path.join(PROJECT_ROOT, "SkinFlaps", "src")


class TestPathSeparators:
    """Verify no hardcoded Windows backslash paths remain in critical code."""

    def test_no_hardcoded_backslash_append_in_gui(self):
        """FacialFlapsGui.cpp should use PATH_SEP, not hardcoded backslash."""
        gui_path = os.path.join(SRC_DIR, "FacialFlapsGui.cpp")
        with open(gui_path, "r") as f:
            content = f.read()
        # Find all .append("\\") calls that are NOT inside #ifdef WIN32 blocks
        # Simple check: count direct .append("\\") occurrences
        pattern = r'\.append\("\\\\"\)'
        matches = re.findall(pattern, content)
        assert len(matches) == 0, (
            f"Found {len(matches)} hardcoded .append(\"\\\\\") in FacialFlapsGui.cpp. "
            f"Should use PATH_SEP instead."
        )

    def test_path_sep_defined_in_header(self):
        """FacialFlapsGui.h should define PATH_SEP for both platforms."""
        header_path = os.path.join(SRC_DIR, "FacialFlapsGui.h")
        with open(header_path, "r") as f:
            content = f.read()
        assert 'PATH_SEP' in content, "PATH_SEP macro not defined in FacialFlapsGui.h"
        assert 'PATH_SEP_CHAR' in content, "PATH_SEP_CHAR macro not defined in FacialFlapsGui.h"

    def test_gui_uses_path_sep_macro(self):
        """FacialFlapsGui.cpp should reference PATH_SEP for directory construction."""
        gui_path = os.path.join(SRC_DIR, "FacialFlapsGui.cpp")
        with open(gui_path, "r") as f:
            content = f.read()
        path_sep_count = content.count("PATH_SEP")
        assert path_sep_count >= 4, (
            f"Expected at least 4 PATH_SEP usages in FacialFlapsGui.cpp, "
            f"found {path_sep_count}"
        )

    def test_linux_default_directories_defined(self):
        """FacialFlapsGui.cpp should have Linux fallback directories (not just C:\\)."""
        gui_path = os.path.join(SRC_DIR, "FacialFlapsGui.cpp")
        with open(gui_path, "r") as f:
            content = f.read()
        # Should have #else block with Linux-compatible paths
        assert 'getenv("HOME")' in content or "getenv(\"HOME\")" in content, (
            "No HOME environment variable usage found for Linux default paths"
        )


class TestModelFileAccess:
    """Verify all model files are accessible with forward-slash paths."""

    def _load_smd(self, filename):
        smd_path = os.path.join(MODEL_DIR, filename)
        with open(smd_path, "r") as f:
            return json.load(f)

    @pytest.mark.parametrize("smd_file", ["ShoulderPrototype.smd", "FacialFlaps.smd"])
    def test_smd_file_exists(self, smd_file):
        smd_path = os.path.join(MODEL_DIR, smd_file)
        assert os.path.isfile(smd_path), f"Scene file not found: {smd_path}"

    def test_shoulder_textures_accessible_with_forward_slash(self):
        """Simulate Linux path construction: Model/ + filename."""
        smd = self._load_smd("ShoulderPrototype.smd")
        for texture_name in smd["textureFiles"]:
            path = MODEL_DIR + "/" + texture_name
            assert os.path.isfile(path), f"Texture not found at: {path}"

    def test_shoulder_static_objs_accessible(self):
        smd = self._load_smd("ShoulderPrototype.smd")
        for obj_name in smd["staticObjects"]:
            path = MODEL_DIR + "/" + obj_name
            assert os.path.isfile(path), f"Static OBJ not found at: {path}"

    def test_shoulder_dynamic_objs_accessible(self):
        smd = self._load_smd("ShoulderPrototype.smd")
        for obj_name in smd["dynamicObjects"]:
            path = MODEL_DIR + "/" + obj_name
            assert os.path.isfile(path), f"Dynamic OBJ not found at: {path}"

    def test_shoulder_shader_accessible(self):
        smd = self._load_smd("ShoulderPrototype.smd")
        shader_name = smd.get("fragmentShader", "shoulderFragmentShader.txt")
        path = MODEL_DIR + "/" + shader_name
        assert os.path.isfile(path), f"Fragment shader not found at: {path}"

    def test_shoulder_subset_objs_accessible(self):
        smd = self._load_smd("ShoulderPrototype.smd")
        if "tetrahedralSubsets" in smd:
            for obj_name in smd["tetrahedralSubsets"]:
                path = MODEL_DIR + "/" + obj_name
                assert os.path.isfile(path), f"Tet subset OBJ not found at: {path}"

    def test_shoulder_bed_file_accessible(self):
        """The .bed file must exist for deep cut/undermine operations."""
        path = MODEL_DIR + "/ShoulderSkin.bed"
        assert os.path.isfile(path), f"Bed file not found at: {path}"

    def test_vertex_shader_exists(self):
        """mtVertexShader.txt must exist in the Model directory."""
        path = MODEL_DIR + "/mtVertexShader.txt"
        assert os.path.isfile(path), f"Vertex shader not found at: {path}"

    @pytest.mark.parametrize("smd_file", ["ShoulderPrototype.smd", "FacialFlaps.smd"])
    def test_all_texture_ids_match(self, smd_file):
        """Texture IDs referenced in objects must be defined in textureFiles."""
        smd = self._load_smd(smd_file)
        defined_ids = set(smd["textureFiles"].values())
        for obj_name, obj_data in smd.get("dynamicObjects", {}).items():
            if "textureMaps" in obj_data:
                for tid in obj_data["textureMaps"]:
                    assert tid in defined_ids, (
                        f"{smd_file}: Dynamic object {obj_name} references "
                        f"texture ID {tid} not in textureFiles {defined_ids}"
                    )
        for obj_name, obj_data in smd.get("staticObjects", {}).items():
            for key in ("textureMap", "normalMap"):
                if key in obj_data:
                    tid = obj_data[key]
                    assert tid in defined_ids, (
                        f"{smd_file}: Static object {obj_name} references "
                        f"texture ID {tid} not in textureFiles {defined_ids}"
                    )


class TestErrorMessageQuality:
    """Verify error messages in bccTetScene.cpp include file paths."""

    def test_texture_error_includes_path(self):
        src = os.path.join(SRC_DIR, "bccTetScene.cpp")
        with open(src, "r") as f:
            content = f.read()
        assert "Texture file not found:" in content, (
            "bccTetScene.cpp should have file-existence check before texture loading"
        )

    def test_static_obj_error_includes_path(self):
        src = os.path.join(SRC_DIR, "bccTetScene.cpp")
        with open(src, "r") as f:
            content = f.read()
        assert "Unable to load static object:" in content, (
            "Static OBJ error should include file path"
        )

    def test_dynamic_obj_error_includes_path(self):
        src = os.path.join(SRC_DIR, "bccTetScene.cpp")
        with open(src, "r") as f:
            content = f.read()
        assert "Unable to load dynamic object:" in content, (
            "Dynamic OBJ error should include file path"
        )

    def test_shader_error_includes_path(self):
        src = os.path.join(SRC_DIR, "bccTetScene.cpp")
        with open(src, "r") as f:
            content = f.read()
        assert "shader not found:" in content, (
            "Shader error should include file path"
        )

    def test_parameter_validation_exists(self):
        src = os.path.join(SRC_DIR, "bccTetScene.cpp")
        with open(src, "r") as f:
            content = f.read()
        assert "Parameter Warning" in content, (
            "Parameter validation warnings should exist in bccTetScene.cpp"
        )
