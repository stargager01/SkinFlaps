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
