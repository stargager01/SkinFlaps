#!/usr/bin/env python3
"""
Loading pipeline validation tests.

Simulates bccTetScene::loadScene() logic in Python to verify each
step succeeds before the actual C++ runtime. This catches file-not-found,
JSON errors, and format issues without needing OpenGL.

Pipeline order (matching bccTetScene.cpp):
  1. Open and parse .smd as JSON
  2. Detect anatomy type from sceneName
  3. Load textureFiles (verify files exist)
  4. Load staticObjects (verify OBJ files exist)
  5. Load dynamicObjects (verify OBJ files, textureMaps match)
  6. Verify shaders exist (vertex + fragment)
  7. Check .bed file for dynamic object
  8. Parse fixedCollisionSets
  9. Parse tetrahedralProperties (validate ranges)
  10. Parse tetrahedralSubsets (verify OBJ files)
  11. Parse tissueRegions
  12. Parse materialLayers
"""

import json
import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(PROJECT_ROOT, "Model")


def simulate_load_scene(smd_filename, model_dir=None):
    """Simulate bccTetScene::loadScene() in Python.

    Returns (success: bool, errors: list[str]) tuple.
    """
    if model_dir is None:
        model_dir = MODEL_DIR
    errors = []

    # Step 1: Open and parse JSON
    smd_path = os.path.join(model_dir, smd_filename)
    if not os.path.isfile(smd_path):
        return False, [f"STEP 1 FAIL: Scene file not found: {smd_path}"]

    try:
        with open(smd_path, "r") as f:
            smd = json.load(f)
    except json.JSONDecodeError as e:
        return False, [f"STEP 1 FAIL: JSON parse error: {e}"]

    if not isinstance(smd, dict):
        return False, [f"STEP 1 FAIL: JSON root is not an object (got {type(smd).__name__})"]

    # Step 2: Detect anatomy type
    scene_name = smd.get("sceneName", "")
    if "Shoulder" in scene_name or "shoulder" in scene_name:
        anatomy = "SHOULDER"
    elif any(kw in scene_name for kw in ["Facial", "facial", "Cleft", "cleft", "Face", "face"]):
        anatomy = "FACIAL"
    else:
        anatomy = "GENERIC" if scene_name else "FACIAL"

    # Step 3: textureFiles (REQUIRED)
    if "textureFiles" not in smd:
        return False, [f"STEP 3 FAIL: No 'textureFiles' section in {smd_filename}"]
    if not isinstance(smd["textureFiles"], dict):
        return False, [f"STEP 3 FAIL: 'textureFiles' is not a JSON object"]

    texture_ids = {}
    for tex_name, tex_id in smd["textureFiles"].items():
        tex_path = os.path.join(model_dir, tex_name)
        if not os.path.isfile(tex_path):
            errors.append(f"STEP 3 FAIL: Texture file not found: {tex_path}")
        else:
            # Check file is not empty/corrupt (minimum size for any image)
            size = os.path.getsize(tex_path)
            if size < 100:
                errors.append(f"STEP 3 WARN: Texture suspiciously small ({size} bytes): {tex_path}")
            # Check supported format
            ext = os.path.splitext(tex_name)[1].lower()
            if ext not in (".bmp", ".jpg", ".jpeg", ".tga"):
                errors.append(f"STEP 3 FAIL: Unsupported texture format '{ext}': {tex_name}")
        texture_ids[tex_id] = tex_name

    if any("STEP 3 FAIL" in e for e in errors):
        return False, errors

    # Step 4: staticObjects (OPTIONAL)
    if "staticObjects" in smd:
        if not isinstance(smd["staticObjects"], dict):
            errors.append("STEP 4 FAIL: 'staticObjects' is not a JSON object")
        else:
            for obj_name, obj_data in smd["staticObjects"].items():
                obj_path = os.path.join(model_dir, obj_name)
                if not os.path.isfile(obj_path):
                    errors.append(f"STEP 4 FAIL: Static object not found: {obj_path}")
                if not isinstance(obj_data, dict):
                    errors.append(f"STEP 4 FAIL: Static object '{obj_name}' data is not a JSON object")
                else:
                    for key in obj_data:
                        if key not in ("textureMap", "normalMap"):
                            errors.append(f"STEP 4 FAIL: Unknown key '{key}' in static object '{obj_name}'")
                        else:
                            tid = obj_data[key]
                            if tid not in texture_ids:
                                errors.append(f"STEP 4 FAIL: Static '{obj_name}' references texture ID {tid} not in textureFiles")

    if any("STEP 4 FAIL" in e for e in errors):
        return False, errors

    # Step 5: dynamicObjects (REQUIRED)
    if "dynamicObjects" not in smd:
        return False, errors + ["STEP 5 FAIL: No 'dynamicObjects' section"]
    if not isinstance(smd["dynamicObjects"], dict):
        return False, errors + ["STEP 5 FAIL: 'dynamicObjects' is not a JSON object"]

    dynamic_objs = []
    for obj_name, obj_data in smd["dynamicObjects"].items():
        obj_path = os.path.join(model_dir, obj_name)
        if not os.path.isfile(obj_path):
            errors.append(f"STEP 5 FAIL: Dynamic object not found: {obj_path}")
        else:
            dynamic_objs.append(obj_name)
        if isinstance(obj_data, dict) and "textureMaps" in obj_data:
            for tid in obj_data["textureMaps"]:
                if tid not in texture_ids:
                    errors.append(f"STEP 5 FAIL: Dynamic '{obj_name}' textureMaps references ID {tid} not in textureFiles")

    if any("STEP 5 FAIL" in e for e in errors):
        return False, errors

    # Step 6: Shaders
    vtx_shader = os.path.join(model_dir, "mtVertexShader.txt")
    if not os.path.isfile(vtx_shader):
        errors.append(f"STEP 6 FAIL: Vertex shader not found: {vtx_shader}")

    if "fragmentShader" in smd:
        frg_name = smd["fragmentShader"]
    elif anatomy == "SHOULDER":
        frg_name = "shoulderFragmentShader.txt"
    else:
        frg_name = "mtFragmentShader.txt"
    frg_shader = os.path.join(model_dir, frg_name)
    if not os.path.isfile(frg_shader):
        errors.append(f"STEP 6 FAIL: Fragment shader not found: {frg_shader}")

    if any("STEP 6 FAIL" in e for e in errors):
        return False, errors

    # Step 7: .bed file (derived from dynamic object name)
    for obj_name in dynamic_objs:
        bed_name = os.path.splitext(obj_name)[0] + ".bed"
        bed_path = os.path.join(model_dir, bed_name)
        if os.path.isfile(bed_path):
            # Validate format
            with open(bed_path, "r") as f:
                for i, line in enumerate(f):
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split()
                    if len(parts) != 4:
                        errors.append(f"STEP 7 WARN: {bed_name} line {i+1}: expected 4 values, got {len(parts)}")
                        break
        # .bed file is optional - just note if missing

    # Step 8: fixedCollisionSets (optional)
    if "fixedCollisionSets" in smd:
        if not isinstance(smd["fixedCollisionSets"], dict):
            errors.append("STEP 8 FAIL: 'fixedCollisionSets' is not a JSON object")

    # Step 9: tetrahedralProperties
    if "tetrahedralProperties" in smd:
        if not isinstance(smd["tetrahedralProperties"], dict):
            errors.append("STEP 9 FAIL: 'tetrahedralProperties' is not a JSON object")
        else:
            tp = smd["tetrahedralProperties"]
            if "minStrain" in tp and "maxStrain" in tp:
                if tp["minStrain"] <= 0:
                    errors.append(f"STEP 9 WARN: minStrain={tp['minStrain']} <= 0")
                if tp["maxStrain"] <= tp["minStrain"]:
                    errors.append(f"STEP 9 WARN: maxStrain={tp['maxStrain']} <= minStrain={tp['minStrain']}")
            if "nTetSizeLevels" in tp:
                n = tp["nTetSizeLevels"]
                if n < 1 or n > 8:
                    errors.append(f"STEP 9 WARN: nTetSizeLevels={n} outside [1,8]")
            if "maxDimMegatetSubdivs" in tp:
                m = tp["maxDimMegatetSubdivs"]
                if m < 10 or m > 100:
                    errors.append(f"STEP 9 WARN: maxDimMegatetSubdivs={m} outside [10,100]")

    # Step 10: tetrahedralSubsets
    if "tetrahedralSubsets" in smd:
        if not isinstance(smd["tetrahedralSubsets"], dict):
            errors.append("STEP 10 FAIL: 'tetrahedralSubsets' is not a JSON object")
        else:
            for obj_name in smd["tetrahedralSubsets"]:
                obj_path = os.path.join(model_dir, obj_name)
                if not os.path.isfile(obj_path):
                    errors.append(f"STEP 10 FAIL: Tet subset OBJ not found: {obj_path}")

    # Step 11-12: tissueRegions, materialLayers (structure check only)
    for section in ("tissueRegions", "materialLayers"):
        if section in smd and not isinstance(smd[section], dict):
            errors.append(f"STEP 11-12 FAIL: '{section}' is not a JSON object")

    has_fail = any("FAIL" in e for e in errors)
    return not has_fail, errors


# ===================== TESTS =====================

class TestMinimalTestPipeline:
    """Validate MinimalTest.smd passes all loading pipeline steps."""

    def test_minimal_full_pipeline(self):
        ok, errors = simulate_load_scene("MinimalTest.smd")
        assert ok, f"MinimalTest.smd pipeline failed:\n" + "\n".join(errors)

    def test_minimal_obj_exists(self):
        assert os.path.isfile(os.path.join(MODEL_DIR, "MinimalTest.obj"))

    def test_minimal_bed_exists(self):
        assert os.path.isfile(os.path.join(MODEL_DIR, "MinimalTest.bed"))

    def test_minimal_smd_valid_json(self):
        with open(os.path.join(MODEL_DIR, "MinimalTest.smd")) as f:
            smd = json.load(f)
        assert isinstance(smd, dict)
        assert "dynamicObjects" in smd
        assert "textureFiles" in smd


class TestShoulderPrototypePipeline:
    """Validate ShoulderPrototype.smd passes all loading pipeline steps."""

    def test_shoulder_full_pipeline(self):
        ok, errors = simulate_load_scene("ShoulderPrototype.smd")
        assert ok, f"ShoulderPrototype.smd pipeline failed:\n" + "\n".join(errors)

    def test_shoulder_anatomy_detected(self):
        with open(os.path.join(MODEL_DIR, "ShoulderPrototype.smd")) as f:
            smd = json.load(f)
        name = smd.get("sceneName", "")
        assert "Shoulder" in name or "shoulder" in name


class TestFacialFlapsPipeline:
    """Validate FacialFlaps.smd passes all loading pipeline steps."""

    def test_facial_full_pipeline(self):
        ok, errors = simulate_load_scene("FacialFlaps.smd")
        assert ok, f"FacialFlaps.smd pipeline failed:\n" + "\n".join(errors)


class TestLoadSceneStepByStep:
    """Test each pipeline step individually for detailed diagnostics."""

    @pytest.fixture
    def shoulder_smd(self):
        with open(os.path.join(MODEL_DIR, "ShoulderPrototype.smd")) as f:
            return json.load(f)

    def test_step1_json_parse(self, shoulder_smd):
        assert isinstance(shoulder_smd, dict), "Root must be JSON object"

    def test_step3_all_textures_exist(self, shoulder_smd):
        for name in shoulder_smd["textureFiles"]:
            path = os.path.join(MODEL_DIR, name)
            assert os.path.isfile(path), f"Texture not found: {path}"
            assert os.path.getsize(path) > 100, f"Texture too small: {path}"

    def test_step4_all_static_objs_exist(self, shoulder_smd):
        for name in shoulder_smd.get("staticObjects", {}):
            path = os.path.join(MODEL_DIR, name)
            assert os.path.isfile(path), f"Static OBJ not found: {path}"

    def test_step5_all_dynamic_objs_exist(self, shoulder_smd):
        for name in shoulder_smd["dynamicObjects"]:
            path = os.path.join(MODEL_DIR, name)
            assert os.path.isfile(path), f"Dynamic OBJ not found: {path}"

    def test_step6_shaders_exist(self, shoulder_smd):
        vtx = os.path.join(MODEL_DIR, "mtVertexShader.txt")
        assert os.path.isfile(vtx), f"Vertex shader not found: {vtx}"
        frg_name = shoulder_smd.get("fragmentShader", "shoulderFragmentShader.txt")
        frg = os.path.join(MODEL_DIR, frg_name)
        assert os.path.isfile(frg), f"Fragment shader not found: {frg}"

    def test_step7_bed_file_format(self, shoulder_smd):
        for obj_name in shoulder_smd["dynamicObjects"]:
            bed_name = os.path.splitext(obj_name)[0] + ".bed"
            bed_path = os.path.join(MODEL_DIR, bed_name)
            if os.path.isfile(bed_path):
                with open(bed_path) as f:
                    for i, line in enumerate(f):
                        parts = line.strip().split()
                        assert len(parts) == 4, f"{bed_name}:{i+1} bad format"
                        int(parts[0])  # vertex ID must be integer
                        for p in parts[1:]:
                            float(p)  # coordinates must be float

    def test_step9_parameter_ranges(self, shoulder_smd):
        tp = shoulder_smd.get("tetrahedralProperties", {})
        if "minStrain" in tp:
            assert tp["minStrain"] > 0, "minStrain must be positive"
        if "maxStrain" in tp and "minStrain" in tp:
            assert tp["maxStrain"] > tp["minStrain"], "maxStrain must exceed minStrain"
        if "nTetSizeLevels" in tp:
            assert 1 <= tp["nTetSizeLevels"] <= 8
        if "maxDimMegatetSubdivs" in tp:
            assert 10 <= tp["maxDimMegatetSubdivs"] <= 100
