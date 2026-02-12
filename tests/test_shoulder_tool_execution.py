#!/usr/bin/env python3
"""
Tests for ShoulderMinimal model tool execution compatibility.

Verifies that:
1. All surgical tool handlers use configurable materialLayerConfig (no hardcoded IDs)
2. Tool execution paths are reachable for SHOULDER anatomy type
3. ShoulderMinimal material layer IDs are compatible with all tool code paths
4. History serialization uses configurable material IDs

Run with:
    python -m pytest tests/test_shoulder_tool_execution.py -v
"""

import json
import os
import re

import pytest

PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), os.pardir))
SRC_DIR = os.path.join(PROJECT_ROOT, "SkinFlaps", "src")
MODEL_DIR = os.path.join(PROJECT_ROOT, "Model")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_src(filename):
    path = os.path.join(SRC_DIR, filename)
    with open(path, "r") as f:
        return f.readlines()


def _load_smd(path):
    with open(path, "r") as f:
        return json.load(f)


def _strip_comments_and_strings(line):
    """Remove // comments and string literals for cleaner pattern matching."""
    line = re.sub(r'//.*$', '', line)
    line = re.sub(r'"[^"]*"', '""', line)
    return line


# ---------------------------------------------------------------------------
# 1. No Hardcoded Material Variable Comparisons
# ---------------------------------------------------------------------------

class TestNoHardcodedMaterialVarComparisons:
    """Verify that material-related local variables are not compared against
    hardcoded integer literals in surgicalActions.cpp.

    This catches patterns like 'triMat == 2', 'material == 3', 'mat == 6'
    that the triangleMaterial() scan in test_material_layers.py would miss.
    """

    # Variable names commonly used for material IDs
    MATERIAL_VARS = r'(?:triMat|material|mat|prevMat|nextMaterial|splitMat)'

    # Patterns: material variable compared to hardcoded integer 2-10
    FORBIDDEN_PATTERNS = [
        rf'{MATERIAL_VARS}\s*==\s*[2-8](?!\d)',     # == 2..8
        rf'{MATERIAL_VARS}\s*==\s*10\b',             # == 10
        rf'{MATERIAL_VARS}\s*!=\s*[2-8](?!\d)',      # != 2..8
        rf'{MATERIAL_VARS}\s*!=\s*10\b',             # != 10
        rf'{MATERIAL_VARS}\s*>\s*[2-7](?!\d)',       # > 2..7 (range checks)
        rf'{MATERIAL_VARS}\s*<\s*[3-8](?!\d)',       # < 3..8 (range checks)
        rf'\[\s*"material"\s*\]\s*=\s*[2-8](?!\d)',  # ["material"] = 2..8
    ]

    def _scan_file(self, filename):
        lines = _read_src(filename)
        findings = []
        for i, raw_line in enumerate(lines, 1):
            line = _strip_comments_and_strings(raw_line)
            if not line.strip():
                continue
            for pattern in self.FORBIDDEN_PATTERNS:
                for m in re.finditer(pattern, line):
                    findings.append((i, m.group(), raw_line.strip()))
        return findings

    def test_surgicalActions_no_hardcoded_material_vars(self):
        """surgicalActions.cpp must not compare material vars to hardcoded IDs."""
        findings = self._scan_file("surgicalActions.cpp")
        if findings:
            details = "\n".join(
                f"  Line {ln}: {match!r} in: {ctx}" for ln, match, ctx in findings
            )
            pytest.fail(
                f"Found {len(findings)} hardcoded material variable comparisons "
                f"in surgicalActions.cpp:\n{details}"
            )

    def test_deepCut_no_hardcoded_material_assignment(self):
        """deepCut.cpp must not assign hardcoded material IDs to tri.material."""
        lines = _read_src("deepCut.cpp")
        findings = []
        for i, raw_line in enumerate(lines, 1):
            line = _strip_comments_and_strings(raw_line)
            # Check for .material = <hardcoded int>
            m = re.search(r'\.material\s*=\s*[2-8](?!\d)', line)
            if m:
                findings.append((i, m.group(), raw_line.strip()))
        if findings:
            details = "\n".join(
                f"  Line {ln}: {match!r} in: {ctx}" for ln, match, ctx in findings
            )
            pytest.fail(
                f"Found {len(findings)} hardcoded material assignments "
                f"in deepCut.cpp:\n{details}"
            )


# ---------------------------------------------------------------------------
# 2. Tool Handlers Use getMaterialLayers()
# ---------------------------------------------------------------------------

class TestToolHandlersUseConfigurableLayers:
    """Verify that critical tool handler sections in surgicalActions.cpp
    reference getMaterialLayers() for material comparisons."""

    @pytest.fixture(autouse=True)
    def load_source(self):
        self.lines = _read_src("surgicalActions.cpp")
        self.content = "".join(self.lines)

    def test_suture_handler_uses_skinSurface(self):
        """Suture tool handler must use getMaterialLayers().skinSurface."""
        assert "getMaterialLayers().skinSurface" in self.content, (
            "Suture handler must use configurable skinSurface"
        )

    def test_suture_handler_uses_incisionEdge(self):
        """Suture handler must use getMaterialLayers().incisionEdge."""
        assert "getMaterialLayers().incisionEdge" in self.content

    def test_suture_handler_uses_muscle(self):
        """Suture handler must use getMaterialLayers().muscle."""
        assert "getMaterialLayers().muscle" in self.content

    def test_excise_handler_uses_incisionEdge(self):
        """Excise handler must reference configurable incisionEdge."""
        # Check that at least one getMaterialLayers().incisionEdge exists
        count = self.content.count("getMaterialLayers().incisionEdge")
        assert count >= 2, (
            f"Expected >=2 getMaterialLayers().incisionEdge refs, found {count}"
        )

    def test_setHistoryAttachPoint_uses_configurable_layers(self):
        """setHistoryAttachPoint must use configurable material checks."""
        # Find setHistoryAttachPoint function body
        start = self.content.find("surgicalActions::setHistoryAttachPoint")
        assert start >= 0, "setHistoryAttachPoint not found"
        # Look within ~250 lines for configurable patterns
        end = min(start + 6000, len(self.content))
        section = self.content[start:end]
        assert "getMaterialLayers().incisionEdge" in section, (
            "setHistoryAttachPoint must use configurable incisionEdge"
        )
        assert "getMaterialLayers().muscle" in section or "ml.muscle" in section, (
            "setHistoryAttachPoint must use configurable muscle"
        )

    def test_isBorderTriangle_lambda_uses_configurable_layers(self):
        """isBorderTriangle lambda must use configurable material IDs, not hardcoded ranges."""
        # The lambda should reference ml.incisionEdge and ml.muscle
        assert "ml.incisionEdge" in self.content, (
            "isBorderTriangle lambda must use ml.incisionEdge"
        )
        assert "ml.muscle" in self.content, (
            "isBorderTriangle lambda must use ml.muscle"
        )

    def test_anchor_handler_uses_configurable_layers(self):
        """Suture anchor handler must use configurable deepBed/periosteum IDs."""
        start = self.content.find("TOOL_SUTURE_ANCHOR")
        assert start >= 0
        section = self.content[start:start+800]
        assert "getMaterialLayers().deepBed" in section, (
            "Anchor handler must use configurable deepBed"
        )
        assert "getMaterialLayers().periosteum" in section, (
            "Anchor handler must use configurable periosteum"
        )
        assert "getMaterialLayers().periosteumUndermined" in section, (
            "Anchor handler must use configurable periosteumUndermined"
        )

    def test_history_playback_uses_configurable_skinSurface(self):
        """nextHistoryAction must use configurable skinSurface for findEdge."""
        start = self.content.find("surgicalActions::nextHistoryAction")
        if start < 0:
            start = self.content.find("nextHistoryAction")
        assert start >= 0, "nextHistoryAction not found"
        section = self.content[start:]
        assert "getMaterialLayers().skinSurface" in section, (
            "nextHistoryAction must use configurable skinSurface for findEdge"
        )

    def test_undermine_history_uses_configurable_material(self):
        """Undermine history save must use configurable skinSurface, not hardcoded 2."""
        # Search for the undermine history section
        assert '["material"] = _bts.getMaterialLayers().skinSurface' in self.content, (
            "Undermine history must use configurable skinSurface"
        )

    def test_getHistoryAttachPoint_uses_configurable_layers(self):
        """getHistoryAttachPoint must use configurable periosteumUndermined/undermineMarker."""
        start = self.content.find("surgicalActions::getHistoryAttachPoint")
        assert start >= 0
        section = self.content[start:]
        assert "getMaterialLayers().periosteumUndermined" in section
        assert "getMaterialLayers().undermineMarker" in section


# ---------------------------------------------------------------------------
# 3. deepCut.cpp Uses _matLayers
# ---------------------------------------------------------------------------

class TestDeepCutUsesMatLayers:
    """Verify deepCut.cpp uses _matLayers for material assignments."""

    @pytest.fixture(autouse=True)
    def load_source(self):
        self.lines = _read_src("deepCut.cpp")
        self.content = "".join(self.lines)

    def test_polygon_triangles_use_matLayers_muscle(self):
        """makePolygonTriangles must use _matLayers.muscle for interior triangles."""
        assert "_matLayers.muscle" in self.content, (
            "deepCut.cpp must use _matLayers.muscle for polygon triangle material"
        )

    def test_addTriangle_uses_matLayers(self):
        """All addTriangle() calls should use _matLayers, not hardcoded IDs."""
        count_configurable = self.content.count("_matLayers.muscle")
        assert count_configurable >= 3, (
            f"Expected >=3 _matLayers.muscle refs in deepCut.cpp, found {count_configurable}"
        )


# ---------------------------------------------------------------------------
# 4. ShoulderMinimal Material Compatibility
# ---------------------------------------------------------------------------

class TestShoulderMinimalToolCompatibility:
    """Verify ShoulderMinimal.smd material layer IDs are compatible with
    all tool code paths (same IDs as facial defaults)."""

    @pytest.fixture(autouse=True)
    def load_configs(self):
        self.shoulder = _load_smd(os.path.join(MODEL_DIR, "ShoulderMinimal.smd"))
        self.facial = _load_smd(os.path.join(MODEL_DIR, "FacialFlaps.smd"))

    def test_core_material_ids_match_facial(self):
        """ShoulderMinimal core material IDs must match facial defaults."""
        core_fields = [
            "boundary", "skinSurface", "incisionEdge", "subcutaneous",
            "deepBed", "muscle", "periosteum", "periosteumUndermined",
            "undermineMarker",
        ]
        s_layers = self.shoulder["materialLayers"]
        f_layers = self.facial["materialLayers"]
        for field in core_fields:
            assert s_layers[field] == f_layers[field], (
                f"ShoulderMinimal {field}={s_layers[field]} != "
                f"Facial {field}={f_layers[field]}"
            )

    def test_shoulder_has_hook_weight(self):
        """ShoulderMinimal must define hookWeight for hook tool."""
        props = self.shoulder["tetrahedralProperties"]
        assert "hookWeight" in props, "Missing hookWeight for hook tool"
        assert props["hookWeight"] > 0

    def test_shoulder_has_suture_weight(self):
        """ShoulderMinimal must define sutureWeight for suture tool."""
        props = self.shoulder["tetrahedralProperties"]
        assert "sutureWeight" in props, "Missing sutureWeight for suture tool"
        assert props["sutureWeight"] > 0

    def test_shoulder_skin_has_incisable_surface(self):
        """ShoulderSkin.obj must have material 2 (skinSurface) faces for knife tool."""
        skin_mat = self.shoulder["materialLayers"]["skinSurface"]
        obj_path = os.path.join(MODEL_DIR, "ShoulderSkin.obj")
        mat_faces = {}
        current_mat = None
        with open(obj_path) as f:
            for line in f:
                if line.startswith("usemtl "):
                    current_mat = int(line.split()[1])
                elif line.startswith("f ") and current_mat is not None:
                    mat_faces[current_mat] = mat_faces.get(current_mat, 0) + 1
        assert skin_mat in mat_faces, (
            f"ShoulderSkin.obj has no faces with material {skin_mat} (skinSurface)"
        )
        assert mat_faces[skin_mat] > 100, (
            f"ShoulderSkin.obj has only {mat_faces[skin_mat]} skinSurface faces, "
            f"need >100 for meaningful incisions"
        )

    def test_shoulder_skin_has_periosteum_for_deep_tools(self):
        """ShoulderSkin.obj must have periosteum faces for deep cut and periosteal tools."""
        perio_mat = self.shoulder["materialLayers"]["periosteum"]
        obj_path = os.path.join(MODEL_DIR, "ShoulderSkin.obj")
        mat_faces = {}
        current_mat = None
        with open(obj_path) as f:
            for line in f:
                if line.startswith("usemtl "):
                    current_mat = int(line.split()[1])
                elif line.startswith("f ") and current_mat is not None:
                    mat_faces[current_mat] = mat_faces.get(current_mat, 0) + 1
        assert perio_mat in mat_faces, (
            f"ShoulderSkin.obj has no periosteum faces (mat {perio_mat})"
        )

    def test_bed_file_enables_deep_bed_assignment(self):
        """A .bed file must exist to enable runtime deep bed material assignment."""
        obj_name = list(self.shoulder["dynamicObjects"].keys())[0]
        bed_name = obj_name.replace(".obj", ".bed")
        bed_path = os.path.join(MODEL_DIR, bed_name)
        assert os.path.isfile(bed_path), (
            f".bed file '{bed_name}' required for deep bed (material "
            f"{self.shoulder['materialLayers']['deepBed']}) assignment"
        )


# ---------------------------------------------------------------------------
# 5. Anatomy Type Detection
# ---------------------------------------------------------------------------

class TestAnatomyTypeDetection:
    """Verify scene name triggers correct anatomy type in bccTetScene."""

    @pytest.fixture(autouse=True)
    def load_source(self):
        self.lines = _read_src("bccTetScene.cpp")
        self.content = "".join(self.lines)

    def test_shoulder_detection_keywords(self):
        """loadScene must detect 'Shoulder' or 'shoulder' in sceneName."""
        assert '"Shoulder"' in self.content or '"shoulder"' in self.content

    def test_anatomy_type_enum_has_shoulder(self):
        header = "".join(_read_src("bccTetScene.h"))
        assert "SHOULDER" in header, "AnatomyType enum missing SHOULDER"

    def test_shoulder_tools_visible_in_gui(self):
        """FacialFlapsGui must show shoulder tools when anatomy is SHOULDER."""
        gui_lines = _read_src("FacialFlapsGui.cpp")
        gui_content = "".join(gui_lines)
        assert "AnatomyType::SHOULDER" in gui_content, (
            "GUI must check for SHOULDER anatomy to show shoulder tools"
        )

    def test_facial_tools_always_visible(self):
        """Facial tools (Hook, Knife, etc.) must be visible for all anatomy types."""
        gui_lines = _read_src("FacialFlapsGui.cpp")
        gui_content = "".join(gui_lines)
        # The facial tool menu items should NOT be behind an anatomy check
        # Find the Hook menu item - it should not be inside a SHOULDER conditional
        hook_idx = gui_content.find('"Hook"')
        assert hook_idx >= 0, "Hook tool menu item not found"
        # Check that there's no SHOULDER conditional between the Tools menu and Hook
        tools_menu_idx = gui_content.rfind("Tools", 0, hook_idx)
        section = gui_content[tools_menu_idx:hook_idx]
        assert "AnatomyType::SHOULDER" not in section, (
            "Facial tools should not be gated behind SHOULDER anatomy check"
        )
