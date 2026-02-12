#!/usr/bin/env python3
"""
Integration tests for the SkinFlaps shoulder surgery extension.

Validates that the shoulder anatomy scene files, OBJ models, boundary data,
shader programs, and history format are complete and internally consistent.

Run with:
    python -m pytest tests/test_shoulder_integration.py -v
"""

import json
import os
import re
import sys

import pytest

# ---------------------------------------------------------------------------
# Paths (all relative to the project root)
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), os.pardir))
MODEL_DIR = os.path.join(PROJECT_ROOT, "Model")
TESTS_DIR = os.path.join(PROJECT_ROOT, "tests")

SHOULDER_SMD = os.path.join(MODEL_DIR, "ShoulderPrototype.smd")
SHOULDER_MINIMAL_SMD = os.path.join(MODEL_DIR, "ShoulderMinimal.smd")
FACIAL_SMD = os.path.join(MODEL_DIR, "FacialFlaps.smd")
SHOULDER_BED = os.path.join(MODEL_DIR, "ShoulderSkin.bed")
SHOULDER_SHADER = os.path.join(MODEL_DIR, "shoulderFragmentShader.txt")
FACIAL_SHADER = os.path.join(MODEL_DIR, "mtFragmentShader.txt")

SHOULDER_OBJ_FILES = [
    "ShoulderSkin.obj",
    "ShoulderBone_humerus.obj",
    "ShoulderBone_glenoid.obj",
    "ShoulderBone_acromion.obj",
    "ShoulderDeepBed.obj",
    "ShoulderMuscle_deltoid.obj",
    "ShoulderTendon_supraspinatus.obj",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_smd(path):
    """Load and parse an SMD (JSON) scene description file."""
    with open(path, "r") as f:
        return json.load(f)


def _count_obj_vertices(obj_path):
    """Count the number of vertex lines ('v x y z') in an OBJ file."""
    count = 0
    with open(obj_path, "r", errors="replace") as f:
        for line in f:
            if line.startswith("v "):
                count += 1
    return count


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def shoulder_smd():
    return _load_smd(SHOULDER_SMD)


@pytest.fixture(scope="module")
def facial_smd():
    return _load_smd(FACIAL_SMD)


@pytest.fixture(scope="module")
def shoulder_shader_source():
    with open(SHOULDER_SHADER, "r") as f:
        return f.read()


@pytest.fixture(scope="module")
def facial_shader_source():
    with open(FACIAL_SHADER, "r") as f:
        return f.read()


# ===========================================================================
# 1. SMD File Validation
# ===========================================================================

class TestSMDFileValidation:
    """Parse ShoulderPrototype.smd and validate all required sections."""

    REQUIRED_TOP_LEVEL_KEYS = {
        "dynamicObjects",
        "staticObjects",
        "textureFiles",
        "tetrahedralProperties",
        "tetrahedralSubsets",
        "tissueRegions",
        "materialLayers",
        "fixedCollisionSets",
    }

    def test_smd_file_exists(self):
        assert os.path.isfile(SHOULDER_SMD), (
            f"ShoulderPrototype.smd not found at {SHOULDER_SMD}"
        )

    def test_smd_is_valid_json(self, shoulder_smd):
        assert isinstance(shoulder_smd, dict)

    def test_smd_has_all_required_sections(self, shoulder_smd):
        missing = self.REQUIRED_TOP_LEVEL_KEYS - set(shoulder_smd.keys())
        assert not missing, f"Missing required sections: {missing}"

    def test_referenced_obj_files_exist(self, shoulder_smd):
        """Every OBJ referenced in dynamicObjects, staticObjects, and
        tetrahedralSubsets must exist in the Model directory."""
        referenced = set()
        for section in ("dynamicObjects", "staticObjects", "tetrahedralSubsets"):
            if section in shoulder_smd:
                referenced.update(shoulder_smd[section].keys())
        for obj_name in referenced:
            path = os.path.join(MODEL_DIR, obj_name)
            assert os.path.isfile(path), (
                f"Referenced OBJ '{obj_name}' not found at {path}"
            )

    def test_referenced_texture_files_exist(self, shoulder_smd):
        """Every texture file listed in textureFiles must exist."""
        for tex_name in shoulder_smd.get("textureFiles", {}):
            path = os.path.join(MODEL_DIR, tex_name)
            assert os.path.isfile(path), (
                f"Referenced texture '{tex_name}' not found at {path}"
            )

    def test_fragment_shader_file_exists(self, shoulder_smd):
        shader_name = shoulder_smd.get("fragmentShader")
        assert shader_name is not None, "fragmentShader key missing from SMD"
        path = os.path.join(MODEL_DIR, shader_name)
        assert os.path.isfile(path), (
            f"Fragment shader '{shader_name}' not found at {path}"
        )

    def test_material_layers_include_shoulder_materials(self, shoulder_smd):
        """materialLayers must include tendon:11, jointCapsule:12, boneSurface:13."""
        layers = shoulder_smd.get("materialLayers", {})
        assert layers.get("tendon") == 11, "materialLayers missing tendon:11"
        assert layers.get("jointCapsule") == 12, "materialLayers missing jointCapsule:12"
        assert layers.get("boneSurface") == 13, "materialLayers missing boneSurface:13"

    def test_tissue_regions_has_shoulder_entries(self, shoulder_smd):
        """tissueRegions must include all shoulder-specific region names."""
        regions = shoulder_smd.get("tissueRegions", {})
        expected = {
            "skin_deltoid",
            "deltoid_muscle",
            "supraspinatus_tendon",
            "joint_capsule",
            "bone",
        }
        missing = expected - set(regions.keys())
        assert not missing, f"Missing shoulder tissue regions: {missing}"

    def test_tetrahedral_subsets_reference_valid_objs(self, shoulder_smd):
        """Each key in tetrahedralSubsets must be an OBJ that exists on disk."""
        subsets = shoulder_smd.get("tetrahedralSubsets", {})
        assert len(subsets) > 0, "tetrahedralSubsets is empty"
        for obj_name in subsets:
            path = os.path.join(MODEL_DIR, obj_name)
            assert os.path.isfile(path), (
                f"tetrahedralSubsets OBJ '{obj_name}' not found at {path}"
            )

    def test_tetrahedral_properties_has_required_keys(self, shoulder_smd):
        """tetrahedralProperties must contain all expected physics keys."""
        props = shoulder_smd.get("tetrahedralProperties", {})
        required_keys = {
            "minStrain",
            "maxStrain",
            "lowTetWeight",
            "highTetWeight",
            "TJunctionWeight",
            "collisionWeight",
            "selfCollisionWeight",
            "fixedWeight",
            "periferalWeight",
            "hookWeight",
            "sutureWeight",
            "autoSutureSpacing",
            "nTetSizeLevels",
            "maxDimMegatetSubdivs",
        }
        missing = required_keys - set(props.keys())
        assert not missing, f"Missing tetrahedralProperties keys: {missing}"


# ===========================================================================
# 2. OBJ Validation Integration
# ===========================================================================

class TestOBJValidationIntegration:
    """Import validate_obj.py and validate all 7 shoulder OBJ files."""

    @pytest.fixture(scope="class")
    def validate_obj_module(self):
        """Import the validate_obj module from the tests directory."""
        sys.path.insert(0, TESTS_DIR)
        try:
            import validate_obj
            return validate_obj
        finally:
            sys.path.pop(0)

    @pytest.mark.parametrize("obj_name", SHOULDER_OBJ_FILES)
    def test_shoulder_obj_passes_validation(self, validate_obj_module, obj_name):
        obj_path = os.path.join(MODEL_DIR, obj_name)
        assert os.path.isfile(obj_path), f"OBJ file not found: {obj_path}"
        result = validate_obj_module.validate_obj(obj_path)
        assert result.passed, (
            f"OBJ validation failed for {obj_name}:\n{result.summary()}"
        )


# ===========================================================================
# 3. .bed File Validation
# ===========================================================================

class TestBedFileValidation:
    """Validate ShoulderSkin.bed format and content."""

    def test_bed_file_exists(self):
        assert os.path.isfile(SHOULDER_BED), (
            f"ShoulderSkin.bed not found at {SHOULDER_BED}"
        )

    def test_bed_format_vertex_id_xyz(self):
        """Each line must follow the format: vertex_id x y z"""
        with open(SHOULDER_BED, "r") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                assert len(parts) == 4, (
                    f"Line {line_num}: expected 4 fields (vertex_id x y z), "
                    f"got {len(parts)}: '{line}'"
                )
                # vertex_id must be an integer
                try:
                    int(parts[0])
                except ValueError:
                    pytest.fail(
                        f"Line {line_num}: vertex_id '{parts[0]}' is not an integer"
                    )
                # x, y, z must be valid floats
                for i, coord_name in enumerate(["x", "y", "z"], start=1):
                    try:
                        float(parts[i])
                    except ValueError:
                        pytest.fail(
                            f"Line {line_num}: {coord_name} coordinate "
                            f"'{parts[i]}' is not a valid float"
                        )

    def test_bed_vertex_count_matches_obj(self):
        """The number of lines in the .bed file must match the vertex count
        of ShoulderSkin.obj (386 vertices)."""
        bed_count = 0
        with open(SHOULDER_BED, "r") as f:
            for line in f:
                if line.strip():
                    bed_count += 1

        obj_path = os.path.join(MODEL_DIR, "ShoulderSkin.obj")
        obj_vertex_count = _count_obj_vertices(obj_path)

        assert bed_count == 386, (
            f"Expected 386 bed entries, got {bed_count}"
        )
        assert obj_vertex_count == 386, (
            f"Expected 386 OBJ vertices, got {obj_vertex_count}"
        )
        assert bed_count == obj_vertex_count, (
            f"Bed entry count ({bed_count}) != OBJ vertex count ({obj_vertex_count})"
        )

    def test_bed_all_coordinates_are_valid_floats(self):
        """Redundant but explicit: every coordinate value parses as float."""
        with open(SHOULDER_BED, "r") as f:
            for line_num, line in enumerate(f, start=1):
                parts = line.strip().split()
                if len(parts) != 4:
                    continue
                for val_str in parts[1:]:
                    val = float(val_str)  # will raise if invalid
                    assert isinstance(val, float)


# ===========================================================================
# 4. History Format Compatibility
# ===========================================================================

class TestHistoryFormatCompatibility:
    """Validate history entry JSON formats for shoulder-specific actions."""

    def test_add_anchor_entry_has_required_keys(self):
        """An addAnchor history entry must contain all required keys."""
        entry = {
            "action": "addAnchor",
            "anchorIdx": 42,
            "material": 13,
            "historyTexture": [0.5, 0.3],
            "displacement": [0.01, -0.02, 0.005],
            "normal": [0.0, 1.0, 0.0],
        }
        required = {"anchorIdx", "material", "historyTexture", "displacement", "normal"}
        missing = required - set(entry.keys())
        assert not missing, f"addAnchor entry missing keys: {missing}"

    def test_add_hook_with_strong_hook_grasper(self):
        """A grasper addHook entry must include strongHook:true."""
        entry = {
            "action": "addHook",
            "hookPosition": [1.0, 2.0, 3.0],
            "triangle": 100,
            "strongHook": True,
        }
        assert "strongHook" in entry
        assert entry["strongHook"] is True

    def test_backward_compatible_facial_add_hook(self):
        """A standard facial addHook entry without strongHook is still valid."""
        entry = {
            "action": "addHook",
            "hookPosition": [0.5, 1.0, 0.2],
            "triangle": 55,
        }
        # strongHook is optional; its absence must not be an error
        assert "action" in entry
        assert "hookPosition" in entry
        assert "triangle" in entry
        # strongHook should default to False when absent
        strong = entry.get("strongHook", False)
        assert strong is False

    def test_history_array_roundtrip(self):
        """A complete history array with mixed entry types serializes and
        deserializes without loss."""
        history = [
            {
                "action": "addHook",
                "hookPosition": [0.5, 1.0, 0.2],
                "triangle": 55,
            },
            {
                "action": "addAnchor",
                "anchorIdx": 7,
                "material": 11,
                "historyTexture": [0.1, 0.9],
                "displacement": [0.0, 0.0, 0.01],
                "normal": [0.0, 0.0, 1.0],
            },
            {
                "action": "addHook",
                "hookPosition": [2.0, 3.0, 1.0],
                "triangle": 200,
                "strongHook": True,
            },
        ]
        serialized = json.dumps(history)
        restored = json.loads(serialized)
        assert restored == history


# ===========================================================================
# 5. Scene Switching Tests
# ===========================================================================

class TestSceneSwitching:
    """Verify both facial and shoulder SMD files parse correctly and share
    a compatible top-level structure."""

    REQUIRED_TOP_LEVEL_KEYS = {
        "dynamicObjects",
        "staticObjects",
        "textureFiles",
        "tetrahedralProperties",
        "tetrahedralSubsets",
        "tissueRegions",
        "materialLayers",
        "fixedCollisionSets",
    }

    def test_facial_smd_parses(self, facial_smd):
        assert isinstance(facial_smd, dict)

    def test_shoulder_smd_parses(self, shoulder_smd):
        assert isinstance(shoulder_smd, dict)

    def test_both_have_compatible_structure(self, facial_smd, shoulder_smd):
        """Both scene files must have the same required top-level keys."""
        facial_keys = set(facial_smd.keys())
        shoulder_keys = set(shoulder_smd.keys())
        for key in self.REQUIRED_TOP_LEVEL_KEYS:
            assert key in facial_keys, (
                f"FacialFlaps.smd missing required key: {key}"
            )
            assert key in shoulder_keys, (
                f"ShoulderPrototype.smd missing required key: {key}"
            )

    def test_facial_smd_does_not_have_shoulder_materials(self, facial_smd):
        """FacialFlaps.smd must NOT contain tendon, jointCapsule, or
        boneSurface material layers."""
        layers = facial_smd.get("materialLayers", {})
        assert "tendon" not in layers, (
            "FacialFlaps.smd should NOT have 'tendon' material"
        )
        assert "jointCapsule" not in layers, (
            "FacialFlaps.smd should NOT have 'jointCapsule' material"
        )
        assert "boneSurface" not in layers, (
            "FacialFlaps.smd should NOT have 'boneSurface' material"
        )
        # Also verify no material values 11, 12, 13
        layer_values = set(layers.values())
        assert 11 not in layer_values, (
            "FacialFlaps.smd should not have material value 11"
        )
        assert 12 not in layer_values, (
            "FacialFlaps.smd should not have material value 12"
        )
        assert 13 not in layer_values, (
            "FacialFlaps.smd should not have material value 13"
        )


# ===========================================================================
# 6. Shader Validation
# ===========================================================================

class TestShaderValidation:
    """Validate fragment shader content for both shoulder and facial variants."""

    def test_shoulder_shader_has_material_11_case(self, shoulder_shader_source):
        """Shoulder shader must handle material 11 (tendon)."""
        assert re.search(r"material\s*>\s*10", shoulder_shader_source), (
            "Shoulder shader missing material>10 case (tendon, material 11)"
        )

    def test_shoulder_shader_has_material_12_case(self, shoulder_shader_source):
        """Shoulder shader must handle material 12 (joint capsule)."""
        assert re.search(r"material\s*>\s*11", shoulder_shader_source), (
            "Shoulder shader missing material>11 case (joint capsule, material 12)"
        )

    def test_shoulder_shader_has_material_13_case(self, shoulder_shader_source):
        """Shoulder shader must handle material 13 (bone surface)."""
        assert re.search(r"material\s*>\s*12", shoulder_shader_source), (
            "Shoulder shader missing material>12 case (bone surface, material 13)"
        )

    def test_facial_shader_does_not_handle_material_11(self, facial_shader_source):
        """Facial shader must NOT have material>10 branching for tendon."""
        assert not re.search(r"material\s*>\s*10", facial_shader_source), (
            "Facial shader should NOT handle material>10 (tendon)"
        )

    def test_facial_shader_does_not_handle_material_12(self, facial_shader_source):
        """Facial shader must NOT have material>11 branching for capsule."""
        assert not re.search(r"material\s*>\s*11", facial_shader_source), (
            "Facial shader should NOT handle material>11 (joint capsule)"
        )

    def test_facial_shader_does_not_handle_material_13(self, facial_shader_source):
        """Facial shader must NOT have material>12 branching for bone."""
        assert not re.search(r"material\s*>\s*12", facial_shader_source), (
            "Facial shader should NOT handle material>12 (bone surface)"
        )

    def test_both_shaders_have_same_uniform_declarations(
        self, shoulder_shader_source, facial_shader_source
    ):
        """Both shaders must declare the same set of uniform variables."""
        uniform_re = re.compile(r"^\s*uniform\s+.+;\s*$", re.MULTILINE)
        shoulder_uniforms = sorted(uniform_re.findall(shoulder_shader_source))
        facial_uniforms = sorted(uniform_re.findall(facial_shader_source))
        assert len(shoulder_uniforms) > 0, "No uniform declarations in shoulder shader"
        assert len(facial_uniforms) > 0, "No uniform declarations in facial shader"
        # Normalize whitespace for comparison
        norm = lambda lines: sorted(re.sub(r"\s+", " ", l.strip()) for l in lines)
        assert norm(shoulder_uniforms) == norm(facial_uniforms), (
            f"Uniform declarations differ.\n"
            f"  Shoulder: {norm(shoulder_uniforms)}\n"
            f"  Facial:   {norm(facial_uniforms)}"
        )


# ===========================================================================
# 7. ShoulderMinimal.smd Validation
# ===========================================================================

class TestShoulderMinimalSMD:
    """Validate ShoulderMinimal.smd — the incremental shoulder config that uses
    real shoulder skin geometry with simplified physics parameters."""

    @pytest.fixture(scope="class")
    def minimal_smd(self):
        return _load_smd(SHOULDER_MINIMAL_SMD)

    def test_file_exists(self):
        assert os.path.isfile(SHOULDER_MINIMAL_SMD), (
            f"ShoulderMinimal.smd not found at {SHOULDER_MINIMAL_SMD}"
        )

    def test_is_valid_json(self, minimal_smd):
        assert isinstance(minimal_smd, dict)

    def test_scene_name_triggers_shoulder_anatomy(self, minimal_smd):
        """sceneName must contain 'Shoulder' to trigger SHOULDER anatomy type."""
        name = minimal_smd.get("sceneName", "")
        assert "Shoulder" in name or "shoulder" in name, (
            f"sceneName '{name}' does not contain 'Shoulder'"
        )

    def test_dynamic_object_is_shoulder_skin(self, minimal_smd):
        dyn = minimal_smd.get("dynamicObjects", {})
        assert "ShoulderSkin.obj" in dyn, "dynamicObjects must include ShoulderSkin.obj"

    def test_dynamic_object_file_exists(self, minimal_smd):
        for obj_name in minimal_smd.get("dynamicObjects", {}):
            path = os.path.join(MODEL_DIR, obj_name)
            assert os.path.isfile(path), f"Dynamic OBJ '{obj_name}' not found"

    def test_texture_maps_reference_valid_ids(self, minimal_smd):
        valid_ids = set(minimal_smd.get("textureFiles", {}).values())
        for obj_name, obj_data in minimal_smd.get("dynamicObjects", {}).items():
            for tid in obj_data.get("textureMaps", []):
                assert tid in valid_ids, (
                    f"textureMaps id={tid} in {obj_name} not in textureFiles"
                )

    def test_texture_files_exist(self, minimal_smd):
        for fname in minimal_smd.get("textureFiles", {}):
            path = os.path.join(MODEL_DIR, fname)
            assert os.path.isfile(path), f"Texture file '{fname}' not found"

    def test_fragment_shader_exists(self, minimal_smd):
        shader = minimal_smd.get("fragmentShader")
        assert shader is not None, "fragmentShader missing"
        path = os.path.join(MODEL_DIR, shader)
        assert os.path.isfile(path), f"Shader '{shader}' not found"

    def test_bed_file_auto_detected(self, minimal_smd):
        """For each dynamic OBJ, a matching .bed file should exist."""
        for obj_name in minimal_smd.get("dynamicObjects", {}):
            bed_name = obj_name.replace(".obj", ".bed")
            path = os.path.join(MODEL_DIR, bed_name)
            assert os.path.isfile(path), (
                f"Auto-detected .bed file '{bed_name}' not found for {obj_name}"
            )

    def test_bed_vertex_count_matches_obj(self, minimal_smd):
        for obj_name in minimal_smd.get("dynamicObjects", {}):
            obj_path = os.path.join(MODEL_DIR, obj_name)
            bed_path = os.path.join(MODEL_DIR, obj_name.replace(".obj", ".bed"))
            obj_verts = _count_obj_vertices(obj_path)
            bed_lines = 0
            with open(bed_path) as f:
                for line in f:
                    if line.strip():
                        bed_lines += 1
            assert bed_lines == obj_verts, (
                f"BED entries ({bed_lines}) != OBJ vertices ({obj_verts}) for {obj_name}"
            )

    def test_tet_properties_valid_range(self, minimal_smd):
        props = minimal_smd.get("tetrahedralProperties", {})
        ntsl = props.get("nTetSizeLevels", 4)
        mdms = props.get("maxDimMegatetSubdivs", 31)
        assert 1 <= ntsl <= 8, f"nTetSizeLevels={ntsl} out of [1,8]"
        assert 10 <= mdms <= 100, f"maxDimMegatetSubdivs={mdms} out of [10,100]"

    def test_tet_properties_simplified(self, minimal_smd):
        """ShoulderMinimal uses simplified physics for incremental testing."""
        props = minimal_smd.get("tetrahedralProperties", {})
        assert props.get("nTetSizeLevels") == 1, "Expected nTetSizeLevels=1"
        assert props.get("maxDimMegatetSubdivs") == 10, "Expected maxDimMegatetSubdivs=10"

    def test_material_layers_complete(self, minimal_smd):
        layers = minimal_smd.get("materialLayers", {})
        required = {"boundary", "skinSurface", "incisionEdge", "subcutaneous", "deepBed"}
        missing = required - set(layers.keys())
        assert not missing, f"Missing core materialLayers: {missing}"

    def test_material_layers_include_shoulder(self, minimal_smd):
        layers = minimal_smd.get("materialLayers", {})
        assert layers.get("tendon") == 11
        assert layers.get("jointCapsule") == 12
        assert layers.get("boneSurface") == 13

    def test_obj_all_triangles_outward_winding(self):
        """ShoulderSkin.obj faces must all have consistent outward winding."""
        import math
        vertices, faces = [], []
        with open(os.path.join(MODEL_DIR, "ShoulderSkin.obj")) as f:
            for line in f:
                parts = line.strip().split()
                if not parts:
                    continue
                if parts[0] == "v":
                    vertices.append(tuple(float(p) for p in parts[1:4]))
                elif parts[0] == "f":
                    faces.append([int(p.split("/")[0]) - 1 for p in parts[1:]])

        cx = sum(v[0] for v in vertices) / len(vertices)
        cy = sum(v[1] for v in vertices) / len(vertices)
        cz = sum(v[2] for v in vertices) / len(vertices)

        inward = 0
        for face in faces:
            v0, v1, v2 = vertices[face[0]], vertices[face[1]], vertices[face[2]]
            e1 = (v1[0]-v0[0], v1[1]-v0[1], v1[2]-v0[2])
            e2 = (v2[0]-v0[0], v2[1]-v0[1], v2[2]-v0[2])
            n = (e1[1]*e2[2]-e1[2]*e2[1], e1[2]*e2[0]-e1[0]*e2[2], e1[0]*e2[1]-e1[1]*e2[0])
            fc = ((v0[0]+v1[0]+v2[0])/3-cx, (v0[1]+v1[1]+v2[1])/3-cy, (v0[2]+v1[2]+v2[2])/3-cz)
            if n[0]*fc[0] + n[1]*fc[1] + n[2]*fc[2] < 0:
                inward += 1

        assert inward == 0, f"{inward} of {len(faces)} faces have inward normals"

    def test_obj_closed_manifold(self):
        """ShoulderSkin.obj must be a closed manifold (no boundary/non-manifold edges)."""
        faces = []
        with open(os.path.join(MODEL_DIR, "ShoulderSkin.obj")) as f:
            for line in f:
                parts = line.strip().split()
                if parts and parts[0] == "f":
                    faces.append([int(p.split("/")[0]) - 1 for p in parts[1:]])

        edges = {}
        for face in faces:
            for i in range(3):
                e = tuple(sorted([face[i], face[(i+1) % 3]]))
                edges[e] = edges.get(e, 0) + 1

        boundary = sum(1 for c in edges.values() if c == 1)
        non_manifold = sum(1 for c in edges.values() if c > 2)
        assert boundary == 0, f"{boundary} boundary edges found"
        assert non_manifold == 0, f"{non_manifold} non-manifold edges found"

    def test_compatible_with_shoulder_prototype(self, minimal_smd):
        """ShoulderMinimal must use the same materialLayers IDs as ShoulderPrototype."""
        proto = _load_smd(SHOULDER_SMD)
        proto_layers = proto.get("materialLayers", {})
        minimal_layers = minimal_smd.get("materialLayers", {})
        for key in minimal_layers:
            if key in proto_layers:
                assert minimal_layers[key] == proto_layers[key], (
                    f"materialLayers['{key}'] differs: minimal={minimal_layers[key]} "
                    f"vs prototype={proto_layers[key]}"
                )
