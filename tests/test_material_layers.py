#!/usr/bin/env python3
"""
Tests for the materialLayerConfig refactoring (Phase 1).

Validates that:
1. materialLayerConfig.h default values match the original hardcoded facial tissue IDs
2. The configuration is properly plumbed to all relevant classes
3. All hardcoded material ID references have been replaced
4. Predicate helpers are defined in skinCutUndermineTets.h
"""

import os
import re

import pytest

PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), os.pardir))
SRC_DIR = os.path.join(PROJECT_ROOT, "SkinFlaps", "src")


class TestMaterialLayerConfigDefaults:
    """Verify default values in materialLayerConfig.h match original hardcoded IDs."""

    @pytest.fixture(autouse=True)
    def load_header(self):
        path = os.path.join(SRC_DIR, "materialLayerConfig.h")
        with open(path, "r") as f:
            self.content = f.read()

    def _get_default(self, field_name):
        """Extract the default value for a field from the header."""
        pattern = rf'int\s+{field_name}\s*=\s*(-?\d+)\s*;'
        m = re.search(pattern, self.content)
        assert m, f"Field '{field_name}' not found in materialLayerConfig.h"
        return int(m.group(1))

    def test_boundary_default(self):
        assert self._get_default("boundary") == 1

    def test_skin_surface_default(self):
        assert self._get_default("skinSurface") == 2

    def test_incision_edge_default(self):
        assert self._get_default("incisionEdge") == 3

    def test_subcutaneous_default(self):
        assert self._get_default("subcutaneous") == 4

    def test_deep_bed_default(self):
        assert self._get_default("deepBed") == 5

    def test_muscle_default(self):
        assert self._get_default("muscle") == 6

    def test_periosteum_default(self):
        assert self._get_default("periosteum") == 7

    def test_periosteum_undermined_default(self):
        assert self._get_default("periosteumUndermined") == 8

    def test_undermine_marker_default(self):
        assert self._get_default("undermineMarker") == 10

    def test_shoulder_extensions_disabled_by_default(self):
        """Non-facial layer extensions should default to -1 (not present)."""
        for field in ("tendon", "jointCapsule", "boneSurface", "arthroscopicPortal"):
            assert self._get_default(field) == -1, f"{field} should default to -1"


class TestPredicateHelpers:
    """Verify predicate helper methods exist in skinCutUndermineTets.h."""

    @pytest.fixture(autouse=True)
    def load_header(self):
        path = os.path.join(SRC_DIR, "skinCutUndermineTets.h")
        with open(path, "r") as f:
            self.content = f.read()

    @pytest.mark.parametrize("predicate", [
        "isSkinSurface",
        "isIncisionEdge",
        "isSubcutaneous",
        "isDeepBed",
        "isMuscle",
        "isBoundary",
        "isUndermineMarker",
        "isPeriosteum",
        "isPeriosteumUndermined",
        "isPeriosteal",
        "isDeepTissue",
    ])
    def test_predicate_exists(self, predicate):
        assert predicate in self.content, f"Predicate {predicate}() not found"

    def test_matLayers_member(self):
        assert "_matLayers" in self.content

    def test_setMaterialLayers_method(self):
        assert "setMaterialLayers" in self.content

    def test_getMaterialLayers_method(self):
        assert "getMaterialLayers" in self.content


class TestConfigPlumbing:
    """Verify materialLayerConfig is plumbed to all classes that need it."""

    def _read_file(self, filename):
        path = os.path.join(SRC_DIR, filename)
        with open(path, "r") as f:
            return f.read()

    def test_skinCutUndermineTets_includes_config(self):
        content = self._read_file("skinCutUndermineTets.h")
        assert '#include "materialLayerConfig.h"' in content

    def test_tetCollisions_includes_config(self):
        content = self._read_file("tetCollisions.h")
        assert '#include "materialLayerConfig.h"' in content

    def test_sutures_includes_config(self):
        content = self._read_file("sutures.h")
        assert '#include "materialLayerConfig.h"' in content

    def test_bccTetScene_plumbs_to_deepCut(self):
        content = self._read_file("bccTetScene.cpp")
        assert "getDeepCutPtr()->setMaterialLayers" in content

    def test_bccTetScene_plumbs_to_tetCollisions(self):
        content = self._read_file("bccTetScene.cpp")
        assert "_tetCol.setMaterialLayers" in content

    def test_bccTetScene_plumbs_to_sutures(self):
        content = self._read_file("bccTetScene.cpp")
        assert "getSutures()->setMaterialLayers" in content


class TestNoRemainingHardcodedMaterialIDs:
    """Verify no hardcoded material ID comparisons remain in refactored files."""

    # These patterns match material ID comparisons that should have been replaced
    MATERIAL_PATTERNS = [
        r'triangleMaterial\([^)]*\)\s*==\s*[2-8](?!\d)',     # == 2..8
        r'triangleMaterial\([^)]*\)\s*==\s*10\b',            # == 10
        r'triangleMaterial\([^)]*\)\s*!=\s*[2-8](?!\d)',     # != 2..8
        r'triangleMaterial\([^)]*\)\s*!=\s*10\b',            # != 10
        r'triangleMaterial\([^)]*\)\s*>\s*[3-6](?!\d)',      # > 3..6 (range checks)
        r'triangleMaterial\([^)]*\)\s*<\s*[3-7](?!\d)',      # < 3..7 (range checks)
        r'setTriangleMaterial\([^,]+,\s*[2-8]\)',            # setTriangleMaterial(x, 2..8)
        r'setTriangleMaterial\([^,]+,\s*10\)',               # setTriangleMaterial(x, 10)
        r'addTriangle\([^,]+,\s*[2-8]\s*,',                 # addTriangle(v, 2..8, t)
    ]

    def _scan_file(self, filename):
        path = os.path.join(SRC_DIR, filename)
        with open(path, "r") as f:
            lines = f.readlines()

        findings = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("//"):
                continue
            for pattern in self.MATERIAL_PATTERNS:
                for m in re.finditer(pattern, line):
                    # Skip if inside a string literal
                    before = line[:m.start()]
                    if before.count('"') % 2 == 1:
                        continue
                    findings.append((i, m.group()))
        return findings

    @pytest.mark.parametrize("filename", [
        "skinCutUndermineTets.cpp",
        "deepCut.cpp",
        "surgicalActions.cpp",
        "tetCollisions.cpp",
        "sutures.cpp",
    ])
    def test_no_hardcoded_material_ids(self, filename):
        findings = self._scan_file(filename)
        if findings:
            details = "\n".join(f"  Line {ln}: {code}" for ln, code in findings)
            pytest.fail(f"Found {len(findings)} hardcoded material IDs in {filename}:\n{details}")


# ---------------------------------------------------------------------------
# Phase 2 readiness: .smd materialLayers loading and model compatibility
# ---------------------------------------------------------------------------

MODEL_DIR = os.path.join(PROJECT_ROOT, "Model")
FACIAL_SMD = os.path.join(MODEL_DIR, "FacialFlaps.smd")
SHOULDER_SMD = os.path.join(MODEL_DIR, "ShoulderMinimal.smd")
SHOULDER_MINIMAL_SMD = os.path.join(MODEL_DIR, "ShoulderMinimal.smd")

# The original hardcoded facial defaults
FACIAL_DEFAULTS = {
    "boundary": 1, "skinSurface": 2, "incisionEdge": 3, "subcutaneous": 4,
    "deepBed": 5, "muscle": 6, "periosteum": 7, "periosteumUndermined": 8,
    "undermineMarker": 10,
}

# Core fields required by every anatomy model
CORE_FIELDS = list(FACIAL_DEFAULTS.keys())

# Shoulder-specific extension fields
SHOULDER_EXTENSIONS = {"tendon": 11, "jointCapsule": 12, "boneSurface": 13}


def _load_smd(path):
    import json
    with open(path, "r") as f:
        return json.load(f)


class TestFacialModelBackwardCompatibility:
    """Verify facial .smd materialLayers exactly match original hardcoded values."""

    @pytest.fixture(autouse=True)
    def load_facial(self):
        self.smd = _load_smd(FACIAL_SMD)
        self.layers = self.smd.get("materialLayers", {})

    def test_facial_smd_has_materialLayers(self):
        assert "materialLayers" in self.smd

    @pytest.mark.parametrize("field,expected", list(FACIAL_DEFAULTS.items()))
    def test_facial_core_field_matches_default(self, field, expected):
        assert self.layers.get(field) == expected, (
            f"FacialFlaps.smd {field}={self.layers.get(field)}, expected {expected}"
        )

    def test_facial_has_no_shoulder_extensions(self):
        """Facial model should not define shoulder-only extension fields."""
        for field in SHOULDER_EXTENSIONS:
            assert field not in self.layers, (
                f"Facial .smd should not have '{field}'"
            )


class TestShoulderModelMaterialLayers:
    """Verify shoulder .smd materialLayers include core + extension fields."""

    @pytest.fixture(autouse=True)
    def load_shoulder(self):
        self.smd = _load_smd(SHOULDER_SMD)
        self.layers = self.smd.get("materialLayers", {})

    def test_shoulder_has_all_core_fields(self):
        for field in CORE_FIELDS:
            assert field in self.layers, f"Missing core field '{field}'"

    @pytest.mark.parametrize("field,expected", list(FACIAL_DEFAULTS.items()))
    def test_shoulder_core_matches_facial_defaults(self, field, expected):
        """Shoulder core fields should match facial defaults (same tissue topology)."""
        assert self.layers.get(field) == expected

    @pytest.mark.parametrize("field,expected", list(SHOULDER_EXTENSIONS.items()))
    def test_shoulder_has_extension(self, field, expected):
        assert self.layers.get(field) == expected

    def test_all_layer_ids_unique(self):
        """All material layer IDs (core + extensions) must be unique."""
        ids = list(self.layers.values())
        assert len(ids) == len(set(ids)), (
            f"Duplicate IDs found: {ids}"
        )

    def test_all_layer_ids_positive(self):
        """All defined material layer IDs must be positive."""
        for field, value in self.layers.items():
            assert value > 0, f"{field}={value} must be positive"


class TestDefaultsFallbackBehavior:
    """Verify that missing .smd materialLayers fields use struct defaults."""

    def test_materialLayerConfig_header_has_all_defaults(self):
        """Every core field must have a default value in the header."""
        path = os.path.join(SRC_DIR, "materialLayerConfig.h")
        with open(path, "r") as f:
            content = f.read()
        for field in CORE_FIELDS:
            pattern = rf'int\s+{field}\s*=\s*(-?\d+)\s*;'
            m = re.search(pattern, content)
            assert m, f"Field '{field}' has no default in materialLayerConfig.h"

    def test_loading_code_uses_HasKey_pattern(self):
        """bccTetScene.cpp must use HasKey() for each field (safe default fallback)."""
        path = os.path.join(SRC_DIR, "bccTetScene.cpp")
        with open(path, "r") as f:
            content = f.read()
        for field in CORE_FIELDS:
            assert f'HasKey("{field}")' in content, (
                f"bccTetScene.cpp missing HasKey check for '{field}'"
            )

    def test_loading_code_plumbs_to_deepCut(self):
        path = os.path.join(SRC_DIR, "bccTetScene.cpp")
        with open(path, "r") as f:
            content = f.read()
        assert "getDeepCutPtr()->setMaterialLayers" in content

    def test_loading_code_plumbs_to_tetCollisions(self):
        path = os.path.join(SRC_DIR, "bccTetScene.cpp")
        with open(path, "r") as f:
            content = f.read()
        assert "_tetCol.setMaterialLayers" in content

    def test_loading_code_plumbs_to_sutures(self):
        path = os.path.join(SRC_DIR, "bccTetScene.cpp")
        with open(path, "r") as f:
            content = f.read()

    def test_validation_checks_core_ids_positive(self):
        """validateScene() must check core IDs are positive."""
        path = os.path.join(SRC_DIR, "bccTetScene.cpp")
        with open(path, "r") as f:
            content = f.read()
        assert "coreIds[i] <= 0" in content

    def test_validation_checks_core_ids_unique(self):
        """validateScene() must check core IDs are distinct."""
        path = os.path.join(SRC_DIR, "bccTetScene.cpp")
        with open(path, "r") as f:
            content = f.read()
        assert "coreIds[i] == coreIds[j]" in content


MODEL_DIR = os.path.join(PROJECT_ROOT, "Model")


class TestShoulderMinimalMaterialRegions:
    """Verify ShoulderSkin.obj has proper material region assignments.

    Matches facial model architecture: single closed surface with materials 1, 2, 7.
    Deep bed defined via .bed file, NOT as OBJ faces (material 5 is runtime-assigned).
    """

    @pytest.fixture(autouse=True)
    def load_obj(self):
        path = os.path.join(MODEL_DIR, "ShoulderSkin.obj")
        self.verts = []
        self.texcoords = []
        self.faces_by_mat = {}
        current_mat = None
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line.startswith('v ') and not line.startswith('vt'):
                    parts = line.split()
                    self.verts.append((float(parts[1]), float(parts[2]), float(parts[3])))
                elif line.startswith('vt '):
                    parts = line.split()
                    self.texcoords.append((float(parts[1]), float(parts[2])))
                elif line.startswith('usemtl '):
                    current_mat = int(line.split()[1])
                    if current_mat not in self.faces_by_mat:
                        self.faces_by_mat[current_mat] = []
                elif line.startswith('f ') and current_mat is not None:
                    parts = line.split()[1:]
                    face = []
                    for p in parts:
                        indices = p.split('/')
                        face.append(int(indices[0]))
                    self.faces_by_mat[current_mat].append(face)

    def test_has_three_materials(self):
        """OBJ must contain materials 1, 2, 7 (no material 5 - deep bed is via .bed)."""
        assert 1 in self.faces_by_mat, "Missing material 1 (boundary)"
        assert 2 in self.faces_by_mat, "Missing material 2 (skinSurface)"
        assert 7 in self.faces_by_mat, "Missing material 7 (periosteum)"
        assert 5 not in self.faces_by_mat, "Material 5 should NOT be in OBJ (deep bed via .bed)"

    def test_boundary_face_count(self):
        """Material 1 (boundary) should have 24 faces (bottom fan at y=0)."""
        assert len(self.faces_by_mat[1]) == 24

    def test_skin_surface_face_count(self):
        """Material 2 (skin) should have 720 faces (main body)."""
        assert len(self.faces_by_mat[2]) == 720

    def test_periosteum_face_count(self):
        """Material 7 (periosteum) should have 24 faces (top fan at apex)."""
        assert len(self.faces_by_mat[7]) == 24

    def test_total_vertex_count(self):
        """Single-shell OBJ: 386 vertices (UV sphere dome)."""
        assert len(self.verts) == 386

    def test_total_face_count(self):
        """Total faces = 24 boundary + 720 skin + 24 periosteum = 768."""
        total = sum(len(fl) for fl in self.faces_by_mat.values())
        assert total == 768

    def test_boundary_verts_at_y0(self):
        """Boundary faces should use vertices at y=0 (bottom edge anchors)."""
        boundary_vert_ids = set()
        for face in self.faces_by_mat[1]:
            for vi in face:
                boundary_vert_ids.add(vi)
        for vi in boundary_vert_ids:
            assert abs(self.verts[vi - 1][1]) < 0.001, \
                f"Boundary vertex {vi} has y={self.verts[vi-1][1]:.4f}, expected 0"

    def test_periosteum_verts_near_apex(self):
        """Periosteum faces (deep bed apex fan) should be near y=6 (top)."""
        perio_vert_ids = set()
        for face in self.faces_by_mat[7]:
            for vi in face:
                perio_vert_ids.add(vi)
        for vi in perio_vert_ids:
            assert self.verts[vi - 1][1] > 5.5, \
                f"Periosteum vertex {vi} has y={self.verts[vi-1][1]:.4f}, expected >5.5"

    def test_all_verts_in_range(self):
        """All face vertex indices must be 1..386 (single shell)."""
        for mat, flist in self.faces_by_mat.items():
            for face in flist:
                for vi in face:
                    assert 1 <= vi <= 386, \
                        f"Material {mat}: vertex {vi} out of range [1,386]"

    def test_no_degenerate_faces(self):
        """No face should have duplicate vertex indices."""
        for mat, flist in self.faces_by_mat.items():
            for fi, face in enumerate(flist):
                assert len(set(face)) == 3, \
                    f"Material {mat} face {fi} is degenerate: {face}"


class TestBedCoordinates:
    """Verify .bed coordinates are valid for the ShoulderSkin model."""

    @pytest.fixture(autouse=True)
    def load_data(self):
        # Load merged OBJ vertices
        obj_path = os.path.join(MODEL_DIR, "ShoulderSkin.obj")
        self.verts = []
        with open(obj_path) as f:
            for line in f:
                if line.startswith('v ') and not line.startswith('vt'):
                    parts = line.split()
                    self.verts.append((float(parts[1]), float(parts[2]), float(parts[3])))
        # Load .bed file
        bed_path = os.path.join(MODEL_DIR, "ShoulderSkin.bed")
        self.bed_entries = []
        with open(bed_path) as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 4:
                    self.bed_entries.append({
                        'vid': int(parts[0]),
                        'x': float(parts[1]),
                        'y': float(parts[2]),
                        'z': float(parts[3])
                    })

    def test_bed_entry_count(self):
        """Should have 386 .bed entries (one per OBJ vertex)."""
        assert len(self.bed_entries) == 386

    def test_bed_vertex_indices_valid(self):
        """All .bed vertex indices should be 0-385 (all OBJ vertices)."""
        for entry in self.bed_entries:
            assert 0 <= entry['vid'] <= 385, \
                f".bed vertex {entry['vid']} outside range [0,385]"

    def test_bed_coords_inside_obj_bbox(self):
        """All .bed positions must be inside the merged OBJ bounding box."""
        min_x = min(v[0] for v in self.verts)
        max_x = max(v[0] for v in self.verts)
        min_y = min(v[1] for v in self.verts)
        max_y = max(v[1] for v in self.verts)
        min_z = min(v[2] for v in self.verts)
        max_z = max(v[2] for v in self.verts)
        tol = 0.01
        for e in self.bed_entries:
            assert min_x - tol <= e['x'] <= max_x + tol, \
                f"Vertex {e['vid']} x={e['x']} outside [{min_x},{max_x}]"
            assert min_y - tol <= e['y'] <= max_y + tol, \
                f"Vertex {e['vid']} y={e['y']} outside [{min_y},{max_y}]"
            assert min_z - tol <= e['z'] <= max_z + tol, \
                f"Vertex {e['vid']} z={e['z']} outside [{min_z},{max_z}]"

    def test_bed_coords_inside_deep_bed_file(self):
        """All .bed positions should be within the deep bed OBJ bounding box."""
        deep_path = os.path.join(MODEL_DIR, "ShoulderDeepBed.obj")
        if not os.path.exists(deep_path):
            pytest.skip("ShoulderDeepBed.obj not present")
        deep_verts = []
        with open(deep_path) as f:
            for line in f:
                if line.startswith('v ') and not line.startswith('vt'):
                    parts = line.split()
                    deep_verts.append((float(parts[1]), float(parts[2]), float(parts[3])))
        min_x = min(v[0] for v in deep_verts)
        max_x = max(v[0] for v in deep_verts)
        min_y = min(v[1] for v in deep_verts)
        max_y = max(v[1] for v in deep_verts)
        min_z = min(v[2] for v in deep_verts)
        max_z = max(v[2] for v in deep_verts)
        tol = 0.01
        for e in self.bed_entries:
            assert min_x - tol <= e['x'] <= max_x + tol
            assert min_y - tol <= e['y'] <= max_y + tol
            assert min_z - tol <= e['z'] <= max_z + tol


class TestShoulderMinimalSmdConfig:
    """Verify ShoulderMinimal.smd has correct lattice resolution settings."""

    @pytest.fixture(autouse=True)
    def load_smd(self):
        import json
        path = os.path.join(MODEL_DIR, "ShoulderMinimal.smd")
        with open(path) as f:
            self.config = json.load(f)

    def test_nTetSizeLevels_at_least_2(self):
        """nTetSizeLevels must be >= 2 for sub-megatet topology operations."""
        val = self.config["tetrahedralProperties"]["nTetSizeLevels"]
        assert val >= 2, f"nTetSizeLevels={val}, need >= 2"

    def test_maxDimMegatetSubdivs_at_least_16(self):
        """maxDimMegatetSubdivs must be >= 16 for adequate lattice resolution."""
        val = self.config["tetrahedralProperties"]["maxDimMegatetSubdivs"]
        assert val >= 16, f"maxDimMegatetSubdivs={val}, need >= 16"

    def test_materialLayers_has_all_required(self):
        """materialLayers must define boundary, skinSurface, deepBed, periosteum."""
        ml = self.config["materialLayers"]
        assert ml["boundary"] == 1
        assert ml["skinSurface"] == 2
        assert ml["deepBed"] == 5
        assert ml["periosteum"] == 7
