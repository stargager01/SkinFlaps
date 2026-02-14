#!/usr/bin/env python3
"""
Tests for the STL import pipeline.

Validates:
  1. STL -> OBJ conversion (convert_stl_to_obj.py)
  2. STL manifold repair (fix_stl_manifold.py)
  3. .bed file generation (generate_bed.py)
  4. .smd file generation (generate_smd.py)
  5. quick_test.py STL/BED validation modes
  6. End-to-end pipeline integration

Uses temporary STL files created with trimesh for reproducible testing.
"""

import json
import os
import sys
import tempfile
import shutil

import numpy as np
import pytest

# Add project directories to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "tools"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import trimesh


# ── Test Fixtures ────────────────────────────────────────────────────


@pytest.fixture
def tmp_dir():
    """Create a temporary directory for test outputs."""
    d = tempfile.mkdtemp(prefix="skinflaps_stl_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def sphere_stl(tmp_dir):
    """Create a watertight sphere STL for testing."""
    mesh = trimesh.creation.icosphere(subdivisions=2, radius=5.0)
    path = os.path.join(tmp_dir, "sphere.stl")
    mesh.export(path)
    return path


@pytest.fixture
def cube_stl(tmp_dir):
    """Create a watertight cube STL for testing."""
    mesh = trimesh.creation.box(extents=[4.0, 6.0, 4.0])
    path = os.path.join(tmp_dir, "cube.stl")
    mesh.export(path)
    return path


@pytest.fixture
def cylinder_stl(tmp_dir):
    """Create a watertight cylinder STL for testing."""
    mesh = trimesh.creation.cylinder(radius=3.0, height=8.0, sections=24)
    path = os.path.join(tmp_dir, "cylinder.stl")
    mesh.export(path)
    return path


@pytest.fixture
def non_manifold_stl(tmp_dir):
    """Create a non-manifold STL (two separate cubes)."""
    box1 = trimesh.creation.box(extents=[2, 2, 2],
                                 transform=trimesh.transformations.translation_matrix([0, 0, 0]))
    box2 = trimesh.creation.box(extents=[2, 2, 2],
                                 transform=trimesh.transformations.translation_matrix([5, 0, 0]))
    combined = trimesh.util.concatenate([box1, box2])
    path = os.path.join(tmp_dir, "non_manifold.stl")
    combined.export(path)
    return path


@pytest.fixture
def valid_obj(tmp_dir):
    """Create a minimal valid SkinFlaps OBJ."""
    mesh = trimesh.creation.icosphere(subdivisions=1, radius=3.0)
    obj_path = os.path.join(tmp_dir, "valid.obj")

    verts = mesh.vertices
    faces = mesh.faces
    n_faces = len(faces)

    with open(obj_path, 'w') as f:
        f.write("# Test OBJ\n")
        for v in verts:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        for v in verts:
            u = (np.arctan2(v[0], v[2]) + np.pi) / (2 * np.pi)
            vv = np.arccos(np.clip(v[1] / 3.0, -1, 1)) / np.pi
            f.write(f"vt {u:.6f} {vv:.6f}\n")
        f.write("s 1\n")
        # Bottom 20% boundary, top 20% periosteum, rest skin
        sorted_faces = sorted(range(n_faces),
                               key=lambda i: mesh.triangles_center[i, 1])
        n_boundary = max(6, n_faces // 5)
        n_periosteum = max(6, n_faces // 5)
        mat_map = {}
        for i, fi in enumerate(sorted_faces):
            if i < n_boundary:
                mat_map[fi] = 1
            elif i >= n_faces - n_periosteum:
                mat_map[fi] = 7
            else:
                mat_map[fi] = 2

        for mat_id in (1, 2, 7):
            f.write(f"usemtl {mat_id}\n")
            for fi in range(n_faces):
                if mat_map[fi] == mat_id:
                    v0, v1, v2 = faces[fi]
                    f.write(f"f {v0+1}/{v0+1} {v1+1}/{v1+1} {v2+1}/{v2+1}\n")

    return obj_path


# ── Test: convert_stl_to_obj.py ──────────────────────────────────────


class TestConvertStlToObj:
    """Tests for the STL to OBJ conversion tool."""

    def test_sphere_conversion_planar(self, sphere_stl, tmp_dir):
        """Convert sphere STL with planar UV."""
        from convert_stl_to_obj import convert_stl_to_obj
        obj_path = os.path.join(tmp_dir, "sphere.obj")
        result = convert_stl_to_obj(sphere_stl, obj_path, uv_method="planar",
                                     material_mode="auto")
        assert result is not None
        assert os.path.isfile(obj_path)
        _, n_verts, n_faces = result
        assert n_verts > 0
        assert n_faces > 0

    def test_sphere_conversion_spherical(self, sphere_stl, tmp_dir):
        """Convert sphere STL with spherical UV."""
        from convert_stl_to_obj import convert_stl_to_obj
        obj_path = os.path.join(tmp_dir, "sphere_sph.obj")
        result = convert_stl_to_obj(sphere_stl, obj_path, uv_method="spherical",
                                     material_mode="auto")
        assert result is not None

    def test_sphere_conversion_cylindrical(self, sphere_stl, tmp_dir):
        """Convert sphere STL with cylindrical UV."""
        from convert_stl_to_obj import convert_stl_to_obj
        obj_path = os.path.join(tmp_dir, "sphere_cyl.obj")
        result = convert_stl_to_obj(sphere_stl, obj_path, uv_method="cylindrical",
                                     material_mode="auto")
        assert result is not None

    def test_cube_conversion(self, cube_stl, tmp_dir):
        """Convert cube STL to OBJ."""
        from convert_stl_to_obj import convert_stl_to_obj
        obj_path = os.path.join(tmp_dir, "cube.obj")
        result = convert_stl_to_obj(cube_stl, obj_path, material_mode="auto")
        assert result is not None

    def test_cylinder_conversion(self, cylinder_stl, tmp_dir):
        """Convert cylinder STL to OBJ."""
        from convert_stl_to_obj import convert_stl_to_obj
        obj_path = os.path.join(tmp_dir, "cylinder.obj")
        result = convert_stl_to_obj(cylinder_stl, obj_path, material_mode="auto")
        assert result is not None

    def test_output_has_correct_materials(self, sphere_stl, tmp_dir):
        """Verify output OBJ only uses materials {1, 2, 7}."""
        from convert_stl_to_obj import convert_stl_to_obj
        obj_path = os.path.join(tmp_dir, "sphere_mat.obj")
        convert_stl_to_obj(sphere_stl, obj_path, material_mode="auto")

        materials = set()
        with open(obj_path) as f:
            for line in f:
                if line.startswith("usemtl "):
                    materials.add(int(line.split()[1]))

        assert materials.issubset({1, 2, 7}), f"Bad materials: {materials}"
        assert 1 in materials, "Missing boundary (material 1)"
        assert 2 in materials, "Missing skin (material 2)"
        assert 7 in materials, "Missing periosteum (material 7)"

    def test_output_has_texcoords(self, sphere_stl, tmp_dir):
        """Verify output OBJ has texture coordinates."""
        from convert_stl_to_obj import convert_stl_to_obj
        obj_path = os.path.join(tmp_dir, "sphere_vt.obj")
        convert_stl_to_obj(sphere_stl, obj_path)

        n_v = 0
        n_vt = 0
        with open(obj_path) as f:
            for line in f:
                if line.startswith("v "):
                    n_v += 1
                elif line.startswith("vt "):
                    n_vt += 1

        assert n_v > 0, "No vertices"
        assert n_vt == n_v, f"Vertex/texcoord mismatch: {n_v} v, {n_vt} vt"

    def test_output_has_smoothing_group(self, sphere_stl, tmp_dir):
        """Verify output OBJ has smoothing group directive."""
        from convert_stl_to_obj import convert_stl_to_obj
        obj_path = os.path.join(tmp_dir, "sphere_sg.obj")
        convert_stl_to_obj(sphere_stl, obj_path)

        has_sg = False
        with open(obj_path) as f:
            for line in f:
                if line.startswith("s "):
                    has_sg = True
                    break
        assert has_sg, "Missing smoothing group"

    def test_no_material_5_in_output(self, sphere_stl, tmp_dir):
        """CRITICAL: Material 5 (deepBed) must NEVER appear in OBJ."""
        from convert_stl_to_obj import convert_stl_to_obj
        obj_path = os.path.join(tmp_dir, "sphere_no5.obj")
        convert_stl_to_obj(sphere_stl, obj_path, material_mode="auto")

        with open(obj_path) as f:
            for line in f:
                if line.startswith("usemtl "):
                    mat = int(line.split()[1])
                    assert mat != 5, "Material 5 (deepBed) found in OBJ!"

    def test_default_output_path(self, sphere_stl, tmp_dir):
        """Test that default output path is derived from input."""
        from convert_stl_to_obj import convert_stl_to_obj
        result = convert_stl_to_obj(sphere_stl)
        assert result is not None
        expected_obj = os.path.splitext(sphere_stl)[0] + ".obj"
        assert result[0] == expected_obj
        assert os.path.isfile(expected_obj)
        # Cleanup
        os.remove(expected_obj)

    def test_min_face_count_rejection(self, tmp_dir):
        """Mesh with too few faces should be rejected."""
        from convert_stl_to_obj import convert_stl_to_obj
        # Create a tiny mesh (tetrahedron = 4 faces)
        verts = np.array([[0, 0, 0], [1, 0, 0], [0.5, 1, 0], [0.5, 0.5, 1]], dtype=float)
        faces_arr = np.array([[0, 1, 2], [0, 1, 3], [1, 2, 3], [0, 2, 3]])
        mesh = trimesh.Trimesh(vertices=verts, faces=faces_arr)
        stl_path = os.path.join(tmp_dir, "tiny.stl")
        mesh.export(stl_path)

        obj_path = os.path.join(tmp_dir, "tiny.obj")
        result = convert_stl_to_obj(stl_path, obj_path, material_mode="auto")
        # 4 faces is below the 12-face minimum
        assert result is None


# ── Test: UV Generation ──────────────────────────────────────────────


class TestUVGeneration:
    """Tests for UV coordinate generation functions."""

    def test_planar_uv_range(self):
        """Planar UVs should be in [0, 1] range."""
        from convert_stl_to_obj import generate_uv_planar
        verts = np.array([[0, 0, 0], [10, 5, 10], [5, 2.5, 5]], dtype=float)
        uvs = generate_uv_planar(verts, axis="y")
        assert uvs.shape == (3, 2)
        assert np.all(uvs >= 0.0)
        assert np.all(uvs <= 1.0)

    def test_spherical_uv_range(self):
        """Spherical UVs should be in [0, 1] range."""
        from convert_stl_to_obj import generate_uv_spherical
        mesh = trimesh.creation.icosphere(subdivisions=1)
        uvs = generate_uv_spherical(mesh.vertices)
        assert uvs.shape[0] == len(mesh.vertices)
        assert uvs.shape[1] == 2
        assert np.all(uvs >= 0.0)
        assert np.all(uvs <= 1.0)

    def test_cylindrical_uv_range(self):
        """Cylindrical UVs should be in [0, 1] range."""
        from convert_stl_to_obj import generate_uv_cylindrical
        mesh = trimesh.creation.cylinder(radius=1, height=2)
        uvs = generate_uv_cylindrical(mesh.vertices, axis="y")
        assert uvs.shape[0] == len(mesh.vertices)
        assert np.all(uvs >= -0.001)  # small tolerance for float precision
        assert np.all(uvs <= 1.001)

    def test_planar_uv_axes(self):
        """Test all three planar UV projection axes."""
        from convert_stl_to_obj import generate_uv_planar
        verts = np.random.randn(50, 3)
        for axis in ("x", "y", "z"):
            uvs = generate_uv_planar(verts, axis=axis)
            assert uvs.shape == (50, 2)


# ── Test: Material Assignment ────────────────────────────────────────


class TestMaterialAssignment:
    """Tests for material region assignment."""

    def test_auto_assigns_all_three_materials(self):
        """Auto mode should assign materials 1, 2, and 7."""
        from convert_stl_to_obj import assign_materials_auto
        mesh = trimesh.creation.icosphere(subdivisions=2)
        materials = assign_materials_auto(mesh, axis="y")
        unique_mats = set(materials)
        assert unique_mats == {1, 2, 7}

    def test_auto_minimum_face_counts(self):
        """Each material should have at least 6 faces."""
        from convert_stl_to_obj import assign_materials_auto
        mesh = trimesh.creation.icosphere(subdivisions=2)
        materials = assign_materials_auto(mesh, axis="y")
        assert np.sum(materials == 1) >= 6
        assert np.sum(materials == 7) >= 6

    def test_manual_defaults_to_skin(self):
        """Manual mode with no overrides should default to material 2."""
        from convert_stl_to_obj import assign_materials_manual
        mesh = trimesh.creation.icosphere(subdivisions=1)
        materials = assign_materials_manual(mesh)
        assert np.all(materials == 2)

    def test_manual_with_overrides(self):
        """Manual mode with explicit overrides."""
        from convert_stl_to_obj import assign_materials_manual
        mesh = trimesh.creation.icosphere(subdivisions=1)
        materials = assign_materials_manual(mesh,
                                             boundary_faces=[0, 1, 2],
                                             periosteum_faces=[3, 4, 5])
        assert materials[0] == 1
        assert materials[3] == 7
        assert materials[10] == 2  # unspecified face = skin

    def test_no_material_5_ever(self):
        """Material 5 must never be assigned."""
        from convert_stl_to_obj import assign_materials_auto
        mesh = trimesh.creation.icosphere(subdivisions=3)
        materials = assign_materials_auto(mesh)
        assert 5 not in materials, "Material 5 (deepBed) must never be in OBJ"


# ── Test: fix_stl_manifold.py ────────────────────────────────────────


class TestFixStlManifold:
    """Tests for STL manifold diagnosis and repair."""

    def test_diagnose_healthy_mesh(self, sphere_stl):
        """Healthy sphere should have no issues."""
        from fix_stl_manifold import diagnose_mesh
        mesh = trimesh.load(sphere_stl, force='mesh')
        diag = diagnose_mesh(mesh)
        assert diag["watertight"] is True
        assert diag["boundary_edges"] == 0
        assert diag["non_manifold_edges"] == 0
        assert diag["degenerate_faces"] == 0

    def test_diagnose_multi_component(self, non_manifold_stl):
        """Multiple components should be detected."""
        from fix_stl_manifold import diagnose_mesh
        mesh = trimesh.load(non_manifold_stl, force='mesh')
        diag = diagnose_mesh(mesh)
        assert diag["connected_components"] >= 2

    def test_repair_keeps_largest_component(self, non_manifold_stl):
        """Repair should keep only the largest component."""
        from fix_stl_manifold import repair_mesh
        mesh = trimesh.load(non_manifold_stl, force='mesh')
        repaired, actions = repair_mesh(mesh, verbose=False)
        # After keeping largest, should be single component
        components = repaired.split(only_watertight=False)
        assert len(components) == 1

    def test_fix_stl_file_end_to_end(self, sphere_stl, tmp_dir):
        """Full fix_stl_file pipeline on a healthy mesh."""
        from fix_stl_manifold import fix_stl_file
        output = os.path.join(tmp_dir, "sphere_fixed.stl")
        success, issues, actions = fix_stl_file(sphere_stl, output)
        assert success is True
        assert len(issues) == 0


# ── Test: generate_bed.py ────────────────────────────────────────────


class TestGenerateBed:
    """Tests for .bed file generation."""

    def test_offset_bed_generation(self, valid_obj, tmp_dir):
        """Offset method should produce correct entry count."""
        from generate_bed import parse_obj_vertices_and_normals, generate_bed_offset, write_bed_file
        verts, normals = parse_obj_vertices_and_normals(valid_obj)
        bed_pos = generate_bed_offset(verts, normals, offset=-2.0)
        bed_path = os.path.join(tmp_dir, "test.bed")
        n = write_bed_file(bed_path, bed_pos)
        assert n == len(verts)
        assert os.path.isfile(bed_path)

    def test_bed_format(self, valid_obj, tmp_dir):
        """Check .bed file format: 'index x y z' per line."""
        from generate_bed import parse_obj_vertices_and_normals, generate_bed_offset, write_bed_file
        verts, normals = parse_obj_vertices_and_normals(valid_obj)
        bed_pos = generate_bed_offset(verts, normals, offset=-1.0)
        bed_path = os.path.join(tmp_dir, "format.bed")
        write_bed_file(bed_path, bed_pos)

        with open(bed_path) as f:
            for i, line in enumerate(f):
                parts = line.strip().split()
                assert len(parts) == 4, f"Line {i}: expected 4 fields, got {len(parts)}"
                assert int(parts[0]) == i, f"Line {i}: index mismatch"
                for p in parts[1:]:
                    float(p)  # should not raise

    def test_bed_vertex_count_matches_obj(self, valid_obj, tmp_dir):
        """CRITICAL: .bed entry count must match OBJ vertex count."""
        from generate_bed import parse_obj_vertices_and_normals, generate_bed_offset, write_bed_file
        verts, normals = parse_obj_vertices_and_normals(valid_obj)
        bed_pos = generate_bed_offset(verts, normals, offset=-3.0)
        bed_path = os.path.join(tmp_dir, "count.bed")
        n = write_bed_file(bed_path, bed_pos)

        # Count OBJ vertices
        n_obj = 0
        with open(valid_obj) as f:
            for line in f:
                if line.startswith("v ") and not line.startswith("vt"):
                    n_obj += 1

        assert n == n_obj, f".bed entries ({n}) != OBJ vertices ({n_obj})"

    def test_offset_moves_vertices_inward(self, valid_obj, tmp_dir):
        """Negative offset should move vertices closer to centroid."""
        from generate_bed import parse_obj_vertices_and_normals, generate_bed_offset
        verts, normals = parse_obj_vertices_and_normals(valid_obj)
        centroid = verts.mean(axis=0)

        bed_pos = generate_bed_offset(verts, normals, offset=-2.0)

        # Most bed positions should be closer to centroid than original
        orig_dist = np.linalg.norm(verts - centroid, axis=1)
        bed_dist = np.linalg.norm(bed_pos - centroid, axis=1)
        closer = np.sum(bed_dist < orig_dist)
        assert closer > len(verts) * 0.7, \
            f"Only {closer}/{len(verts)} bed positions closer to centroid"

    def test_reference_bed_generation(self, valid_obj, tmp_dir):
        """Reference method using a separate OBJ."""
        from generate_bed import parse_obj_vertices_and_normals, generate_bed_reference, write_bed_file

        # Create a smaller reference OBJ (same center, smaller radius)
        ref_mesh = trimesh.creation.icosphere(subdivisions=2, radius=1.5)
        ref_path = os.path.join(tmp_dir, "ref.obj")
        with open(ref_path, 'w') as f:
            for v in ref_mesh.vertices:
                f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")

        verts, _ = parse_obj_vertices_and_normals(valid_obj)
        bed_pos = generate_bed_reference(verts, ref_path)

        bed_path = os.path.join(tmp_dir, "ref.bed")
        n = write_bed_file(bed_path, bed_pos)
        assert n == len(verts)


# ── Test: generate_smd.py ────────────────────────────────────────────


class TestGenerateSmd:
    """Tests for .smd scene file generation."""

    def test_generate_generic_smd(self):
        """Generic anatomy preset should produce valid .smd."""
        from generate_smd import generate_smd, validate_smd
        smd = generate_smd("TestModel.obj", anatomy="generic")
        issues = validate_smd(smd)
        errors = [i for i in issues if i[0] == "ERROR"]
        assert len(errors) == 0, f"Validation errors: {errors}"

    def test_generate_facial_smd(self):
        """Facial anatomy preset should include tissue regions."""
        from generate_smd import generate_smd
        smd = generate_smd("FaceModel.obj", anatomy="facial")
        assert "tissueRegions" in smd
        assert "cheek" in smd["tissueRegions"]
        assert "eyelid" in smd["tissueRegions"]

    def test_generate_shoulder_smd(self):
        """Shoulder anatomy preset should include extended materials."""
        from generate_smd import generate_smd
        smd = generate_smd("ShoulderModel.obj", anatomy="shoulder")
        ml = smd["materialLayers"]
        assert ml.get("tendon") == 11
        assert ml.get("jointCapsule") == 12
        assert ml.get("boneSurface") == 13
        assert smd.get("fragmentShader") == "shoulderFragmentShader.txt"

    def test_smd_has_required_sections(self):
        """Generated .smd must have dynamicObjects and tetrahedralProperties."""
        from generate_smd import generate_smd
        smd = generate_smd("Model.obj")
        assert "dynamicObjects" in smd
        assert "tetrahedralProperties" in smd
        assert "Model.obj" in smd["dynamicObjects"]

    def test_smd_physics_parameters(self):
        """All 14 physics parameters must be present."""
        from generate_smd import generate_smd
        smd = generate_smd("Model.obj", anatomy="generic")
        tp = smd["tetrahedralProperties"]
        required_params = [
            "minStrain", "maxStrain", "lowTetWeight", "highTetWeight",
            "TJunctionWeight", "collisionWeight", "selfCollisionWeight",
            "fixedWeight", "periferalWeight", "hookWeight", "sutureWeight",
            "autoSutureSpacing", "nTetSizeLevels", "maxDimMegatetSubdivs",
        ]
        for param in required_params:
            assert param in tp, f"Missing parameter: {param}"

    def test_smd_material_layer_uniqueness(self):
        """Material layer IDs must be unique."""
        from generate_smd import generate_smd
        for anatomy in ("generic", "facial", "shoulder"):
            smd = generate_smd("Model.obj", anatomy=anatomy)
            ml = smd["materialLayers"]
            positive_vals = [v for v in ml.values() if isinstance(v, int) and v > 0]
            assert len(positive_vals) == len(set(positive_vals)), \
                f"Duplicate material IDs in {anatomy}: {positive_vals}"

    def test_smd_strain_range(self):
        """minStrain must be less than maxStrain."""
        from generate_smd import generate_smd
        for anatomy in ("generic", "facial", "shoulder"):
            smd = generate_smd("Model.obj", anatomy=anatomy)
            tp = smd["tetrahedralProperties"]
            assert tp["minStrain"] < tp["maxStrain"], \
                f"{anatomy}: minStrain ({tp['minStrain']}) >= maxStrain ({tp['maxStrain']})"

    def test_smd_scene_name(self):
        """Scene name should be derived from OBJ filename."""
        from generate_smd import generate_smd
        smd = generate_smd("MyCustomModel.obj")
        assert smd["sceneName"] == "MyCustomModel"

        smd2 = generate_smd("Model.obj", scene_name="CustomName")
        assert smd2["sceneName"] == "CustomName"

    def test_smd_write_and_read(self, tmp_dir):
        """Write .smd to file and verify it's valid JSON."""
        from generate_smd import generate_smd
        smd = generate_smd("Model.obj", anatomy="generic")
        smd_path = os.path.join(tmp_dir, "test.smd")

        with open(smd_path, 'w') as f:
            json.dump(smd, f, indent=4)

        with open(smd_path, 'r') as f:
            loaded = json.load(f)

        assert loaded["sceneName"] == "Model"
        assert "dynamicObjects" in loaded


# ── Test: quick_test.py Validators ───────────────────────────────────


class TestQuickTestValidators:
    """Tests for quick_test.py validation modes."""

    def test_validate_stl_healthy(self, sphere_stl):
        """Healthy STL should pass all checks."""
        # Import from scripts directory
        sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))
        from quick_test import validate_stl

        results = validate_stl(sphere_stl)
        failed = [r for r in results if not r[1]]
        assert len(failed) == 0, f"Failed checks: {failed}"

    def test_validate_stl_missing_file(self):
        """Missing file should fail."""
        sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))
        from quick_test import validate_stl

        results = validate_stl("/nonexistent/file.stl")
        assert results[0][0] == "file_exists"
        assert results[0][1] is False

    def test_validate_bed_valid(self, valid_obj, tmp_dir):
        """Valid .bed file should pass."""
        sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))
        from quick_test import validate_bed

        # Generate a valid bed file
        from generate_bed import parse_obj_vertices_and_normals, generate_bed_offset, write_bed_file
        verts, normals = parse_obj_vertices_and_normals(valid_obj)
        bed_pos = generate_bed_offset(verts, normals, offset=-1.0)
        bed_path = os.path.join(tmp_dir, "valid.bed")
        write_bed_file(bed_path, bed_pos)

        results = validate_bed(bed_path, obj_path=valid_obj)
        failed = [r for r in results if not r[1]]
        assert len(failed) == 0, f"Failed checks: {failed}"

    def test_validate_bed_count_mismatch(self, valid_obj, tmp_dir):
        """Bed file with wrong count should fail obj cross-check."""
        sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))
        from quick_test import validate_bed

        bed_path = os.path.join(tmp_dir, "bad.bed")
        with open(bed_path, 'w') as f:
            f.write("0 1.0 2.0 3.0\n")
            f.write("1 4.0 5.0 6.0\n")

        results = validate_bed(bed_path, obj_path=valid_obj)
        match_results = [r for r in results if r[0] == "matches_obj"]
        assert len(match_results) == 1
        assert match_results[0][1] is False  # should fail


# ── Test: End-to-End Pipeline ────────────────────────────────────────


class TestEndToEndPipeline:
    """Integration tests for the full STL import pipeline."""

    def test_full_pipeline_sphere(self, sphere_stl, tmp_dir):
        """Full pipeline: STL -> OBJ -> .bed -> .smd."""
        from convert_stl_to_obj import convert_stl_to_obj
        from generate_bed import parse_obj_vertices_and_normals, generate_bed_offset, write_bed_file
        from generate_smd import generate_smd, validate_smd

        # Step 1: Convert STL to OBJ
        obj_path = os.path.join(tmp_dir, "pipeline.obj")
        result = convert_stl_to_obj(sphere_stl, obj_path, material_mode="auto")
        assert result is not None

        # Step 2: Generate .bed
        verts, normals = parse_obj_vertices_and_normals(obj_path)
        bed_pos = generate_bed_offset(verts, normals, offset=-2.0)
        bed_path = os.path.join(tmp_dir, "pipeline.bed")
        n_bed = write_bed_file(bed_path, bed_pos)
        assert n_bed == len(verts)

        # Step 3: Generate .smd
        smd = generate_smd("pipeline.obj", anatomy="generic")
        smd_path = os.path.join(tmp_dir, "pipeline.smd")
        with open(smd_path, 'w') as f:
            json.dump(smd, f, indent=4)

        # Step 4: Validate all outputs
        issues = validate_smd(smd)
        errors = [i for i in issues if i[0] == "ERROR"]
        assert len(errors) == 0

        # Verify all files exist
        assert os.path.isfile(obj_path)
        assert os.path.isfile(bed_path)
        assert os.path.isfile(smd_path)

    def test_full_pipeline_cylinder(self, cylinder_stl, tmp_dir):
        """Full pipeline with cylindrical UV mapping."""
        from convert_stl_to_obj import convert_stl_to_obj
        from generate_bed import parse_obj_vertices_and_normals, generate_bed_offset, write_bed_file
        from generate_smd import generate_smd

        obj_path = os.path.join(tmp_dir, "cyl_pipe.obj")
        result = convert_stl_to_obj(cylinder_stl, obj_path,
                                     uv_method="cylindrical",
                                     material_mode="auto")
        assert result is not None

        verts, normals = parse_obj_vertices_and_normals(obj_path)
        bed_pos = generate_bed_offset(verts, normals, offset=-1.5)
        bed_path = os.path.join(tmp_dir, "cyl_pipe.bed")
        n = write_bed_file(bed_path, bed_pos)
        assert n == len(verts)

        smd = generate_smd("cyl_pipe.obj", anatomy="shoulder")
        assert smd["materialLayers"]["tendon"] == 11

    def test_pipeline_obj_validates(self, sphere_stl, tmp_dir):
        """Converted OBJ should pass quick_test.py OBJ validation."""
        from convert_stl_to_obj import convert_stl_to_obj

        obj_path = os.path.join(tmp_dir, "validate_me.obj")
        convert_stl_to_obj(sphere_stl, obj_path, material_mode="auto")

        sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))
        from quick_test import validate_obj

        results = validate_obj(obj_path)
        failed = [r for r in results if not r[1]]
        assert len(failed) == 0, f"OBJ validation failures: {failed}"


# ── Test: Existing Model Validation ──────────────────────────────────


class TestExistingModels:
    """Validate existing model files still pass after pipeline changes."""

    def test_existing_bed_format(self):
        """Existing ShoulderSkin.bed should pass validation."""
        bed_path = os.path.join(PROJECT_ROOT, "Model", "ShoulderSkin.bed")
        if not os.path.exists(bed_path):
            pytest.skip("ShoulderSkin.bed not found")

        sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))
        from quick_test import validate_bed

        results = validate_bed(bed_path)
        failed = [r for r in results if not r[1]]
        assert len(failed) == 0, f"ShoulderSkin.bed validation failed: {failed}"

    def test_existing_smd_valid(self):
        """Existing .smd files should pass validation."""
        sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))
        from quick_test import validate_smd

        for smd_name in ("ShoulderMinimal.smd", "MinimalTest.smd"):
            smd_path = os.path.join(PROJECT_ROOT, "Model", smd_name)
            if not os.path.exists(smd_path):
                continue
            results = validate_smd(smd_path)
            failed = [r for r in results if not r[1]]
            assert len(failed) == 0, f"{smd_name} validation failed: {failed}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
