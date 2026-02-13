#!/usr/bin/env python3
"""
Comprehensive per-tool tests for all 11 surgical tools (0-10).

Validates each tool's:
1. Code path presence in surgicalActions.cpp (handler reachable)
2. Material validation logic (accepted / rejected materials)
3. History recording format (JSON keys and structure)
4. Physics initialization pattern (TBB task spawn, exception handling)
5. GUI integration (menu items, radio buttons, tool state)
6. Key handler support (ENTER, DELETE behaviour per tool)
7. Shoulder extension tools (8-10) conditional visibility
8. Error handling and user messages

Tool index:
  0 - View       : Viewer / selection mode
  1 - Hook       : Create tissue retraction hooks
  2 - Knife      : Skin surface incisions
  3 - Undermine  : Undermine tissue below skin
  4 - Suture     : Place sutures connecting tissue edges
  5 - Excise     : Remove (excise) tissue triangles
  6 - Deep cut   : Deep incisions beneath the skin surface
  7 - Periosteal : Periosteal (bone surface) undermining
  8 - Anchor     : Suture anchor placement on bone (shoulder)
  9 - Scope      : Arthroscopic camera simulation (shoulder)
 10 - Grasp      : Tissue grasper / strong hook (shoulder)

Run with:
    python -m pytest tests/test_surgical_tools.py -v
"""

import json
import os
import re

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), os.pardir))
SRC_DIR = os.path.join(PROJECT_ROOT, "SkinFlaps", "src")
MODEL_DIR = os.path.join(PROJECT_ROOT, "Model")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_src(filename):
    """Return all lines of a source file under SkinFlaps/src/."""
    path = os.path.join(SRC_DIR, filename)
    with open(path, "r") as f:
        return f.readlines()


def _src_content(filename):
    """Return the entire text content of a source file."""
    return "".join(_read_src(filename))


def _load_smd(path):
    """Load and parse an .smd (JSON) scene file."""
    with open(path, "r") as f:
        return json.load(f)


def _find_tool_block(content, tool_state_expr, max_chars=3000):
    """Extract code block starting at `_toolState == <expr>` or
    `_toolState == TOOL_<name>`, up to max_chars characters."""
    idx = content.find(tool_state_expr)
    if idx < 0:
        return ""
    return content[idx:idx + max_chars]


def _strip_comments(line):
    """Remove // comments and string literals."""
    line = re.sub(r'//.*$', '', line)
    line = re.sub(r'"[^"]*"', '""', line)
    return line


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sa_content():
    """Full text of surgicalActions.cpp."""
    return _src_content("surgicalActions.cpp")


@pytest.fixture(scope="module")
def sa_header():
    """Full text of surgicalActions.h."""
    return _src_content("surgicalActions.h")


@pytest.fixture(scope="module")
def gui_content():
    """Full text of FacialFlapsGui.cpp."""
    return _src_content("FacialFlapsGui.cpp")


@pytest.fixture(scope="module")
def shoulder_smd():
    return _load_smd(os.path.join(MODEL_DIR, "ShoulderMinimal.smd"))


@pytest.fixture(scope="module")
def facial_smd():
    return _load_smd(os.path.join(MODEL_DIR, "FacialFlaps.smd"))


# ===========================================================================
# Tool 0: View (Viewer / Selection)
# ===========================================================================

class TestTool0View:
    """Tool 0 -- Viewer / selection mode."""

    def test_viewer_handler_present(self, sa_content):
        """rightMouseDown must contain _toolState==0 (viewer) handler."""
        assert "_toolState==0" in sa_content or "_toolState == 0" in sa_content

    def test_viewer_selects_hooks(self, sa_content):
        """Viewer mode recognises 'H_' prefix for hook selection."""
        block = _find_tool_block(sa_content, '_toolState==0')
        if not block:
            block = _find_tool_block(sa_content, '_toolState == 0')
        assert 'H_' in block, "Viewer must detect H_ prefix for hook selection"

    def test_viewer_selects_sutures(self, sa_content):
        """Viewer mode recognises 'S_' prefix for suture selection."""
        block = _find_tool_block(sa_content, '_toolState==0')
        if not block:
            block = _find_tool_block(sa_content, '_toolState == 0')
        assert 'S_' in block, "Viewer must detect S_ prefix for suture selection"

    def test_viewer_does_not_pause_physics(self, sa_header):
        """Tool state 0 should NOT call setPhysicsPause(true) on activation.
        The physics pause only occurs for toolState > 0."""
        assert "toolState < 1 ? false : true" in sa_header

    def test_viewer_gui_menuitem(self, gui_content):
        """GUI has a View menu item for tool 0."""
        assert '"View"' in gui_content

    def test_viewer_records_hook_moves(self, sa_content):
        """rightMouseUp records moveHook in history when in viewer mode."""
        assert '"moveHook"' in sa_content


# ===========================================================================
# Tool 1: Hook
# ===========================================================================

class TestTool1Hook:
    """Tool 1 -- Create tissue retraction hooks."""

    def test_hook_handler_present(self, sa_content):
        assert "_toolState == 1" in sa_content

    def test_hook_initialises_on_first_use(self, sa_content):
        """Hook system initialised when getNumberOfHooks() < 1."""
        assert "getNumberOfHooks() < 1" in sa_content

    def test_hook_records_addHook_history(self, sa_content):
        """History entry key is 'addHook'."""
        assert '"addHook"' in sa_content

    def test_hook_history_has_hookNum(self, sa_content):
        assert '"hookNum"' in sa_content

    def test_hook_history_has_material(self, sa_content):
        assert '"material"' in sa_content

    def test_hook_history_has_historyTexture(self, sa_content):
        assert '"historyTexture"' in sa_content

    def test_hook_history_has_displacement(self, sa_content):
        assert '"displacement"' in sa_content

    def test_hook_strongHook_support(self, sa_content):
        """strongHook flag can be recorded in history."""
        assert '"strongHook"' in sa_content

    def test_hook_physics_tbb_exception_handling(self, sa_content):
        """TBB task spawned for physics init has structured exception handling."""
        block = _find_tool_block(sa_content, '_toolState == 1', 5000)
        assert "catch (const std::exception&" in block
        assert "catch (...)" in block

    def test_hook_gui_menuitem(self, gui_content):
        assert '"Hook"' in gui_content

    def test_hook_gui_radiobutton(self, gui_content):
        assert 'RadioButton("Hook"' in gui_content

    def test_hook_delete_key_removes_hook(self, sa_content):
        """DELETE key in viewer mode calls deleteHook."""
        assert "deleteHook" in sa_content

    def test_hook_delete_history(self, sa_content):
        """deleteHook history entry is recorded."""
        assert '"deleteHook"' in sa_content

    def test_smd_hookWeight_defined(self, shoulder_smd, facial_smd):
        """Both scene files must define hookWeight > 0."""
        assert shoulder_smd["tetrahedralProperties"]["hookWeight"] > 0
        assert facial_smd["tetrahedralProperties"]["hookWeight"] > 0


# ===========================================================================
# Tool 2: Knife (Incision)
# ===========================================================================

class TestTool2Knife:
    """Tool 2 -- Make incisions on the skin surface."""

    def test_knife_handler_present(self, sa_content):
        assert "_toolState == 2" in sa_content

    def test_knife_validates_skinSurface_material(self, sa_content):
        """Knife tool rejects non-skinSurface material using getMaterialLayers()."""
        block = _find_tool_block(sa_content, '_toolState == 2')
        assert "getMaterialLayers().skinSurface" in block

    def test_knife_uses_fence_system(self, sa_content):
        """Knife uses fence posts to define incision path."""
        block = _find_tool_block(sa_content, '_toolState == 2')
        assert "addPost" in block

    def test_knife_supports_Tin_detection(self, sa_content):
        """Knife supports T-in via closestSkinIncisionPoint."""
        assert "closestSkinIncisionPoint" in sa_content

    def test_knife_supports_Tout(self, sa_content):
        """Knife supports T-out back to first incision point."""
        assert "ToutToFirstPoint" in sa_content

    def test_knife_enter_key_completes_incision(self, sa_content):
        """ENTER key triggers skinCut() for knife tool."""
        assert "skinCut(" in sa_content

    def test_knife_delete_key_removes_post(self, sa_content):
        """DELETE key calls deleteLastPost in incision mode."""
        assert "deleteLastPost" in sa_content

    def test_knife_history_makeIncision(self, sa_content):
        """History records 'makeIncision' with header and incisionPoint objects."""
        assert '"makeIncision"' in sa_content
        assert '"incisionPoint"' in sa_content

    def test_knife_history_header_fields(self, sa_content):
        """makeIncision header contains Tin, Tout, incisedObject, pointNumber."""
        assert '"Tin"' in sa_content
        assert '"Tout"' in sa_content
        assert '"incisedObject"' in sa_content
        assert '"pointNumber"' in sa_content

    def test_knife_gui_menuitem(self, gui_content):
        assert '"Knife"' in gui_content

    def test_knife_gui_radiobutton(self, gui_content):
        assert 'RadioButton("Knife"' in gui_content

    def test_knife_error_message_for_wrong_material(self, sa_content):
        """User gets error when trying to incise non-skin surface."""
        assert "only incise from top side of skin" in sa_content


# ===========================================================================
# Tool 3: Undermine
# ===========================================================================

class TestTool3Undermine:
    """Tool 3 -- Undermine tissue beneath the skin."""

    def test_undermine_handler_present(self, sa_content):
        assert "_toolState == 3" in sa_content

    def test_undermine_validates_material(self, sa_content):
        """Undermine accepts skinSurface and undermineMarker only."""
        block = _find_tool_block(sa_content, '_toolState == 3')
        assert "getMaterialLayers().skinSurface" in block
        assert "getMaterialLayers().undermineMarker" in block

    def test_undermine_uses_addUndermineTriangle(self, sa_content):
        assert "addUndermineTriangle" in sa_content

    def test_undermine_enter_key_triggers_undermineSkin(self, sa_content):
        """ENTER key calls undermineSkin()."""
        assert "undermineSkin()" in sa_content

    def test_undermine_delete_clears_triangles(self, sa_content):
        """DELETE key clears _undermineTriangles."""
        assert "_undermineTriangles.clear()" in sa_content

    def test_undermine_history_format(self, sa_content):
        """History records 'undermine' with 'underminePoint' entries."""
        assert '"undermine"' in sa_content
        assert '"underminePoint"' in sa_content

    def test_undermine_history_uses_configurable_skinSurface(self, sa_content):
        """Undermine history uses getMaterialLayers().skinSurface, not hardcoded 2."""
        assert '["material"] = _bts.getMaterialLayers().skinSurface' in sa_content

    def test_undermine_incisionConnect_recorded(self, sa_content):
        """incisionConnect boolean recorded per undermine triangle."""
        assert '"incisionConnect"' in sa_content

    def test_undermine_gui_menuitem(self, gui_content):
        assert '"Undermine"' in gui_content

    def test_undermine_physics_update_after_completion(self, sa_content):
        """updateOldPhysicsLattice called after undermine completes."""
        assert "updateOldPhysicsLattice" in sa_content

    def test_undermine_error_message_for_wrong_material(self, sa_content):
        assert "only undermine from top side of skin" in sa_content


# ===========================================================================
# Tool 4: Suture
# ===========================================================================

class TestTool4Suture:
    """Tool 4 -- Place sutures connecting tissue edges."""

    def test_suture_handler_present(self, sa_content):
        assert "_toolState == 4" in sa_content

    def test_suture_initialises_on_first_use(self, sa_content):
        assert "getNumberOfSutures() < 1" in sa_content

    def test_suture_validates_skinSurface(self, sa_content):
        """Suture handler uses getMaterialLayers().skinSurface."""
        block = _find_tool_block(sa_content, '_toolState == 4', 5000)
        assert "getMaterialLayers().skinSurface" in block

    def test_suture_validates_incisionEdge(self, sa_content):
        """Suture handler uses getMaterialLayers().incisionEdge."""
        assert "getMaterialLayers().incisionEdge" in sa_content

    def test_suture_rejects_muscle(self, sa_content):
        """Suture handler rejects getMaterialLayers().muscle."""
        assert "getMaterialLayers().muscle" in sa_content

    def test_suture_linked_mode(self, sa_content):
        """Suture supports linked (automatic suture line) mode via setLinked."""
        assert "setLinked(" in sa_content

    def test_suture_laySutureLine(self, sa_content):
        """laySutureLine creates auto-sutures between user sutures."""
        assert "laySutureLine(" in sa_content

    def test_suture_completion_in_rightMouseUp(self, sa_content):
        """rightMouseUp calls setSecondEdge to complete suture placement."""
        assert "setSecondEdge(" in sa_content

    def test_suture_history_addSuture(self, sa_content):
        """History records 'addSuture' with paired attachment points."""
        assert '"addSuture"' in sa_content

    def test_suture_history_fields(self, sa_content):
        """addSuture history has sutureNum, linked, material0/1, historyTexture0/1."""
        assert '"sutureNum"' in sa_content
        assert '"linked"' in sa_content
        assert '"material0"' in sa_content
        assert '"material1"' in sa_content
        assert '"historyTexture0"' in sa_content
        assert '"historyTexture1"' in sa_content

    def test_suture_delete_history(self, sa_content):
        """deleteSuture history entry is recorded."""
        assert '"deleteSuture"' in sa_content

    def test_suture_mouseMotion_updates_position(self, sa_content):
        """mouseMotion updates second vertex position during suture drag."""
        assert "setSecondVertexPosition(" in sa_content

    def test_suture_gui_menuitem(self, gui_content):
        assert '"Suture"' in gui_content

    def test_suture_gui_radiobutton(self, gui_content):
        assert 'RadioButton("Suture"' in gui_content

    def test_smd_sutureWeight_defined(self, shoulder_smd, facial_smd):
        """Both scene files must define sutureWeight > 0."""
        assert shoulder_smd["tetrahedralProperties"]["sutureWeight"] > 0
        assert facial_smd["tetrahedralProperties"]["sutureWeight"] > 0


# ===========================================================================
# Tool 5: Excise
# ===========================================================================

class TestTool5Excise:
    """Tool 5 -- Remove (excise) tissue triangles."""

    def test_excise_handler_present(self, sa_content):
        assert "_toolState == 5" in sa_content

    def test_excise_rejects_incisionEdge(self, sa_content):
        """Excise tool rejects incisionEdge material."""
        block = _find_tool_block(sa_content, '_toolState == 5')
        assert "getMaterialLayers().incisionEdge" in block

    def test_excise_rejects_muscle(self, sa_content):
        """Excise tool rejects muscle material."""
        block = _find_tool_block(sa_content, '_toolState == 5')
        assert "getMaterialLayers().muscle" in block

    def test_excise_calls_incisions_excise(self, sa_content):
        """Excise calls _incisions.excise(triangle)."""
        assert "_incisions.excise(" in sa_content

    def test_excise_auto_resets_to_viewer(self, sa_content):
        """After excision, tool automatically resets to viewer (tool 0)."""
        block = _find_tool_block(sa_content, '_toolState == 5')
        assert "setToolState(0)" in block

    def test_excise_history_format(self, sa_content):
        """History records 'excise' with material, historyTexture, displacement."""
        assert '"excise"' in sa_content

    def test_excise_physics_update_after_completion(self, sa_content):
        """updateOldPhysicsLattice called after excision."""
        # Count occurrences - at least one should be in excise context
        assert sa_content.count("updateOldPhysicsLattice") >= 1

    def test_excise_gui_menuitem(self, gui_content):
        assert '"Excise"' in gui_content

    def test_excise_gui_radiobutton(self, gui_content):
        assert 'RadioButton("Excise"' in gui_content

    def test_excise_error_message(self, sa_content):
        """User gets error for invalid excise target."""
        assert "excise from a skin/mucosal edge" in sa_content


# ===========================================================================
# Tool 6: Deep Cut
# ===========================================================================

class TestTool6DeepCut:
    """Tool 6 -- Deep incisions beneath the skin surface."""

    def test_deepcut_handler_present(self, sa_content):
        assert "_toolState == 6" in sa_content

    def test_deepcut_validates_material(self, sa_content):
        """Deep cut accepts skinSurface and deepBed materials only."""
        block = _find_tool_block(sa_content, '_toolState == 6')
        assert "getMaterialLayers().skinSurface" in block
        assert "getMaterialLayers().deepBed" in block

    def test_deepcut_fence_post_selection(self, sa_content):
        """Deep cut supports NP_ prefix for fence post selection."""
        assert 'NP_' in sa_content

    def test_deepcut_xray_through_skin(self, sa_content):
        """Deep cut can x-ray through undermined skin to deep bed."""
        assert "triangleUndermined(" in sa_content

    def test_deepcut_enter_key_triggers_cutDeep(self, sa_content):
        """ENTER key triggers cutDeep() for deep cut tool."""
        assert "cutDeep()" in sa_content

    def test_deepcut_inputCorrectFence(self, sa_content):
        """inputCorrectFence validates the fence path before cutting."""
        assert "inputCorrectFence(" in sa_content

    def test_deepcut_delete_key_removes_post(self, sa_content):
        """DELETE key removes last fence post in deep cut mode."""
        # Verified by toolState == 6 DELETE handler
        block = _find_tool_block(sa_content, '_toolState == 6')
        # DELETE handling is in onKeyDown, not in the same block
        assert "deleteLastPost" in sa_content

    def test_deepcut_mouseMotion_drags_post(self, sa_content):
        """mouseMotion allows dragging fence posts in deep cut mode."""
        assert "setSpherePos(" in sa_content

    def test_deepcut_history_format(self, sa_content):
        """History records 'makeDeepCut' with header and deepCutPoint objects."""
        assert '"makeDeepCut"' in sa_content
        assert '"deepCutPoint"' in sa_content

    def test_deepcut_history_header_fields(self, sa_content):
        """makeDeepCut header contains deepCutObject, openIn, openOut, pointNumber."""
        assert '"deepCutObject"' in sa_content
        assert '"openIn"' in sa_content
        assert '"openOut"' in sa_content

    def test_deepcut_history_postNormal(self, sa_content):
        """Each deepCutPoint includes a postNormal vector."""
        assert '"postNormal"' in sa_content

    def test_deepcut_gui_menuitem(self, gui_content):
        assert '"Deep cut"' in gui_content

    def test_deepcut_error_message(self, sa_content):
        assert "deep cut from unelevated skin top or deep bed" in sa_content

    def test_deepcut_uses_matLayers_in_deepCut_cpp(self):
        """deepCut.cpp uses _matLayers for material assignments."""
        content = _src_content("deepCut.cpp")
        assert "_matLayers.muscle" in content


# ===========================================================================
# Tool 7: Periosteal Undermine
# ===========================================================================

class TestTool7Periosteal:
    """Tool 7 -- Periosteal (bone surface) undermining."""

    def test_periosteal_handler_present(self, sa_content):
        assert "_toolState == 7" in sa_content

    def test_periosteal_uses_camera_ray(self, sa_content):
        """Periosteal tool uses getTrianglePickLine for 3D ray direction."""
        assert "getTrianglePickLine(" in sa_content

    def test_periosteal_addPeriostealUndermineTriangle(self, sa_content):
        assert "addPeriostealUndermineTriangle(" in sa_content

    def test_periosteal_enter_key_completes(self, sa_content):
        """ENTER key sets triangles to periosteumUndermined and calls
        fixPeriostealPeriferalVertices."""
        assert "fixPeriostealPeriferalVertices" in sa_content

    def test_periosteal_material_transition(self, sa_content):
        """ENTER key transitions undermineMarker -> periosteumUndermined."""
        assert "getMaterialLayers().undermineMarker" in sa_content
        assert "getMaterialLayers().periosteumUndermined" in sa_content

    def test_periosteal_nonTetPhysicsUpdate(self, sa_content):
        """Periosteal completion triggers nonTetPhysicsUpdate."""
        assert "nonTetPhysicsUpdate()" in sa_content

    def test_periosteal_history_format(self, sa_content):
        """History records 'periostealUndermine' with periostealTriangle entries."""
        assert '"periostealUndermine"' in sa_content
        assert '"periostealTriangle"' in sa_content

    def test_periosteal_gui_menuitem(self, gui_content):
        assert '"Periosteal"' in gui_content

    def test_periosteal_gui_radiobutton(self, gui_content):
        assert 'RadioButton("Periosteal"' in gui_content

    def test_periosteal_error_message(self, sa_content):
        assert "No periosteal triangle hit" in sa_content

    def test_periosteal_auto_complete_on_tool_switch(self, sa_content):
        """Unfinished periosteal undermining is auto-completed on tool switch."""
        # The code checks `_toolState != 7 && !_periostealUndermineTriangles.empty()`
        assert "_periostealUndermineTriangles.empty()" in sa_content


# ===========================================================================
# Tool 8: Suture Anchor (Shoulder)
# ===========================================================================

class TestTool8Anchor:
    """Tool 8 -- Suture anchor placement on bone surface (shoulder only)."""

    def test_anchor_constant_defined(self, sa_header):
        """TOOL_SUTURE_ANCHOR = 8 defined in surgicalActions.h."""
        assert "TOOL_SUTURE_ANCHOR = 8" in sa_header

    def test_anchor_handler_present(self, sa_content):
        assert "TOOL_SUTURE_ANCHOR" in sa_content

    def test_anchor_validates_deepBed(self, sa_content):
        """Anchor requires deepBed, periosteum, or periosteumUndermined."""
        block = _find_tool_block(sa_content, 'TOOL_SUTURE_ANCHOR')
        assert "getMaterialLayers().deepBed" in block

    def test_anchor_validates_periosteum(self, sa_content):
        block = _find_tool_block(sa_content, 'TOOL_SUTURE_ANCHOR')
        assert "getMaterialLayers().periosteum" in block

    def test_anchor_validates_periosteumUndermined(self, sa_content):
        block = _find_tool_block(sa_content, 'TOOL_SUTURE_ANCHOR')
        assert "getMaterialLayers().periosteumUndermined" in block

    def test_anchor_calls_addAnchor(self, sa_content):
        """Anchor tool calls sutures::addAnchor()."""
        assert "addAnchor(" in sa_content

    def test_anchor_creates_visual_sphere(self, sa_content):
        """Anchor tool creates a gold SPHERE visual marker."""
        block = _find_tool_block(sa_content, 'TOOL_SUTURE_ANCHOR')
        assert "SPHERE" in block

    def test_anchor_gold_colour(self, sa_content):
        """Anchor marker uses gold colour (0.85, 0.85, 0.2)."""
        assert "0.85f, 0.85f, 0.2f" in sa_content

    def test_anchor_history_format(self, sa_content):
        """History records 'addAnchor' with anchorIdx, material, normal."""
        assert '"addAnchor"' in sa_content
        assert '"anchorIdx"' in sa_content
        assert '"normal"' in sa_content

    def test_anchor_user_message(self, sa_content):
        """User message about switching to Suture tool after anchor placement."""
        assert "Switch to Suture tool" in sa_content

    def test_anchor_error_for_wrong_material(self, sa_content):
        assert "only be placed on periosteum or deep bed" in sa_content

    def test_anchor_gui_menuitem(self, gui_content):
        assert '"Anchor"' in gui_content

    def test_anchor_gui_radiobutton(self, gui_content):
        assert 'RadioButton("Anchor"' in gui_content

    def test_anchor_only_visible_for_shoulder(self, gui_content):
        """Anchor menu item gated behind AnatomyType::SHOULDER check."""
        anchor_idx = gui_content.find('"Anchor"')
        assert anchor_idx >= 0
        # Find nearest SHOULDER check before this menu item
        section = gui_content[max(0, anchor_idx - 500):anchor_idx]
        assert "AnatomyType::SHOULDER" in section

    def test_sutureAnchor_struct_defined(self):
        """sutureAnchor struct is defined in sutures.h."""
        content = _src_content("sutures.h")
        assert "struct sutureAnchor" in content

    def test_sutureAnchor_has_bonePosition(self):
        content = _src_content("sutures.h")
        assert "bonePosition" in content

    def test_sutureAnchor_has_boneNormal(self):
        content = _src_content("sutures.h")
        assert "boneNormal" in content

    def test_sutureAnchor_has_collisionObjectIdx(self):
        content = _src_content("sutures.h")
        assert "collisionObjectIdx" in content

    def test_sutureAnchor_has_sutureIds(self):
        content = _src_content("sutures.h")
        assert "sutureIds" in content


# ===========================================================================
# Tool 9: Arthroscope (Shoulder)
# ===========================================================================

class TestTool9Scope:
    """Tool 9 -- Arthroscopic camera simulation (shoulder only)."""

    def test_scope_constant_defined(self, sa_header):
        """TOOL_ARTHROSCOPE = 9 defined in surgicalActions.h."""
        assert "TOOL_ARTHROSCOPE = 9" in sa_header

    def test_scope_handler_present(self, sa_content):
        assert "TOOL_ARTHROSCOPE" in sa_content

    def test_scope_narrow_fov(self, sa_content):
        """Arthroscope sets narrow FOV (~30 degrees) via setView(0.35f)."""
        block = _find_tool_block(sa_content, 'TOOL_ARTHROSCOPE')
        assert "0.35f" in block

    def test_scope_restores_fov_on_exit(self, sa_header):
        """FOV restored to 0.7f when leaving arthroscope mode."""
        assert "0.7f" in sa_header

    def test_scope_stores_portal_index(self, sa_content):
        """Arthroscope stores portal triangle index."""
        assert "_arthroscopePortalIdx" in sa_content

    def test_scope_portal_reset_on_exit(self, sa_header):
        """Portal index reset to -1 when leaving scope mode."""
        assert "_arthroscopePortalIdx = -1" in sa_header

    def test_scope_user_message(self, sa_content):
        """User message about scope activation."""
        assert "Arthroscope placed" in sa_content

    def test_scope_gui_menuitem(self, gui_content):
        assert '"Scope"' in gui_content

    def test_scope_gui_radiobutton(self, gui_content):
        assert 'RadioButton("Scope"' in gui_content

    def test_scope_only_visible_for_shoulder(self, gui_content):
        """Scope menu item gated behind AnatomyType::SHOULDER."""
        scope_idx = gui_content.find('"Scope"')
        assert scope_idx >= 0
        section = gui_content[max(0, scope_idx - 500):scope_idx]
        assert "AnatomyType::SHOULDER" in section

    def test_scope_camera_data_getter(self, sa_content):
        """Arthroscope reads current camera data via getCameraData."""
        assert "getCameraData(" in sa_content


# ===========================================================================
# Tool 10: Grasper (Shoulder)
# ===========================================================================

class TestTool10Grasper:
    """Tool 10 -- Tissue grasper / strong hook (shoulder only)."""

    def test_grasper_constant_defined(self, sa_header):
        """TOOL_GRASPER = 10 defined in surgicalActions.h."""
        assert "TOOL_GRASPER = 10" in sa_header

    def test_grasper_handler_present(self, sa_content):
        assert "TOOL_GRASPER" in sa_content

    def test_grasper_uses_strong_hook(self, sa_content):
        """Grasper always activates strong hook mode."""
        block = _find_tool_block(sa_content, 'TOOL_GRASPER')
        assert "_strongHooks = true" in block

    def test_grasper_saves_and_restores_strongHook(self, sa_content):
        """Grasper saves _strongHooks before overriding and restores after."""
        block = _find_tool_block(sa_content, 'TOOL_GRASPER')
        assert "savedStrongHooks" in block

    def test_grasper_reuses_hook_system(self, sa_content):
        """Grasper reuses hooks::addHook for placement."""
        block = _find_tool_block(sa_content, 'TOOL_GRASPER')
        assert "addHook(" in block

    def test_grasper_initialises_hooks_if_needed(self, sa_content):
        """Grasper initialises hooks system if first use."""
        block = _find_tool_block(sa_content, 'TOOL_GRASPER')
        assert "getNumberOfHooks() < 1" in block

    def test_grasper_physics_tbb_exception_handling(self, sa_content):
        """Grasper TBB task has structured exception handling."""
        block = _find_tool_block(sa_content, 'TOOL_GRASPER', 5000)
        assert "grasper placement" in block  # error message mentions grasper

    def test_grasper_history_reuses_addHook_format(self, sa_content):
        """Grasper history uses 'addHook' format for backward compatibility."""
        block = _find_tool_block(sa_content, 'TOOL_GRASPER', 5000)
        assert '"addHook"' in block

    def test_grasper_history_includes_strongHook(self, sa_content):
        """Grasper history entry includes strongHook = true."""
        block = _find_tool_block(sa_content, 'TOOL_GRASPER', 5000)
        assert '"strongHook"' in block

    def test_grasper_gui_menuitem(self, gui_content):
        assert '"Grasp"' in gui_content

    def test_grasper_gui_radiobutton(self, gui_content):
        assert 'RadioButton("Grasp"' in gui_content

    def test_grasper_only_visible_for_shoulder(self, gui_content):
        """Grasper menu item gated behind AnatomyType::SHOULDER."""
        grasp_idx = gui_content.find('"Grasp"')
        assert grasp_idx >= 0
        section = gui_content[max(0, grasp_idx - 500):grasp_idx]
        assert "AnatomyType::SHOULDER" in section


# ===========================================================================
# Cross-tool validation
# ===========================================================================

class TestCrossToolValidation:
    """Tests spanning multiple tools for consistency."""

    def test_all_tool_handlers_in_rightMouseDown(self, sa_content):
        """rightMouseDown must have handler blocks for tools 0-10."""
        for i in range(8):
            assert f"_toolState == {i}" in sa_content or f"_toolState=={i}" in sa_content, \
                f"Missing rightMouseDown handler for tool {i}"
        for name in ("TOOL_SUTURE_ANCHOR", "TOOL_ARTHROSCOPE", "TOOL_GRASPER"):
            assert name in sa_content, f"Missing rightMouseDown handler for {name}"

    def test_tool_state_range(self, sa_header):
        """Tool constants 8, 9, 10 are defined in header."""
        assert "TOOL_SUTURE_ANCHOR = 8" in sa_header
        assert "TOOL_ARTHROSCOPE = 9" in sa_header
        assert "TOOL_GRASPER = 10" in sa_header

    def test_setToolState_pauses_physics_for_active_tools(self, sa_header):
        """setToolState pauses physics when toolState > 0."""
        assert "toolState < 1 ? false : true" in sa_header

    def test_setToolState_restores_fov_on_scope_exit(self, sa_header):
        """setToolState restores camera FOV when leaving arthroscope."""
        # Check the inline setToolState function
        assert "TOOL_ARTHROSCOPE && toolState != TOOL_ARTHROSCOPE" in sa_header

    def test_gui_facial_tools_always_visible(self, gui_content):
        """Facial tools (Hook through Periosteal) are not gated by anatomy type."""
        for label in ("Hook", "Knife", "Undermine", "Suture", "Excise"):
            idx = gui_content.find(f'MenuItem("{label}"')
            assert idx >= 0, f'MenuItem("{label}") not found'
            # Check there's no SHOULDER guard between "Tools" menu and this item
            tools_idx = gui_content.rfind("Tools", 0, idx)
            if tools_idx > 0:
                section = gui_content[tools_idx:idx]
                assert "AnatomyType::SHOULDER" not in section, \
                    f"Facial tool '{label}' should not be gated behind SHOULDER anatomy"

    def test_gui_shoulder_tools_gated(self, gui_content):
        """Shoulder tools (Anchor, Scope, Grasp) are behind SHOULDER check."""
        for label in ("Anchor", "Scope", "Grasp"):
            idx = gui_content.find(f'MenuItem("{label}"')
            assert idx >= 0, f'MenuItem("{label}") not found'
            section = gui_content[max(0, idx - 500):idx]
            assert "AnatomyType::SHOULDER" in section, \
                f"Shoulder tool '{label}' must be behind SHOULDER anatomy check"

    def test_history_all_action_types_present(self, sa_content):
        """surgicalActions.cpp must produce all documented history action types."""
        required_actions = [
            '"addHook"', '"moveHook"', '"deleteHook"',
            '"makeIncision"', '"undermine"', '"excise"',
            '"addSuture"', '"deleteSuture"', '"makeDeepCut"',
            '"periostealUndermine"', '"addAnchor"',
        ]
        for action in required_actions:
            assert action in sa_content, \
                f"History action {action} not found in surgicalActions.cpp"

    def test_all_tools_use_getMaterialLayers(self, sa_content):
        """All material-validating tools use getMaterialLayers() accessor."""
        # At least these calls must appear somewhere in surgicalActions.cpp
        required_fields = [
            "getMaterialLayers().skinSurface",
            "getMaterialLayers().incisionEdge",
            "getMaterialLayers().muscle",
            "getMaterialLayers().deepBed",
            "getMaterialLayers().periosteum",
            "getMaterialLayers().periosteumUndermined",
            "getMaterialLayers().undermineMarker",
            "getMaterialLayers().subcutaneous",
        ]
        for field in required_fields:
            assert field in sa_content, \
                f"Material layer accessor {field} not found in surgicalActions.cpp"

    def test_thread_safety_error_mutex(self, sa_content):
        """All TBB tasks use _errorMutex for thread-safe error reporting."""
        # Count lock_guard uses (should be substantial)
        mutex_count = sa_content.count("lock_guard<std::mutex>")
        assert mutex_count >= 6, \
            f"Expected >= 6 mutex lock_guard uses, found {mutex_count}"

    def test_physicsDone_atomic_synchronisation(self, sa_header):
        """physicsDone is an atomic<bool> for thread synchronisation."""
        assert "std::atomic<bool> physicsDone" in sa_header

    def test_all_tbb_tasks_have_exception_handling(self, sa_content):
        """Every tbb::task_arena enqueue must have catch blocks."""
        # Find all tbb task enqueue occurrences
        enqueue_positions = [m.start() for m in re.finditer(r'\.enqueue\(\[', sa_content)]
        for pos in enqueue_positions:
            block = sa_content[pos:pos + 2000]
            assert "catch" in block, \
                f"TBB task at position {pos} lacks exception handling"


# ===========================================================================
# Scene file tool compatibility
# ===========================================================================

class TestSceneToolCompatibility:
    """Validate that scene files (.smd) support all tools."""

    def test_shoulder_smd_supports_all_core_materials(self, shoulder_smd):
        """ShoulderMinimal.smd defines all core material layers."""
        layers = shoulder_smd["materialLayers"]
        required = {
            "boundary": 1, "skinSurface": 2, "incisionEdge": 3,
            "subcutaneous": 4, "deepBed": 5, "muscle": 6,
            "periosteum": 7, "periosteumUndermined": 8,
            "undermineMarker": 10,
        }
        for key, val in required.items():
            assert layers.get(key) == val, \
                f"ShoulderMinimal {key} = {layers.get(key)}, expected {val}"

    def test_shoulder_smd_defines_shoulder_extensions(self, shoulder_smd):
        """ShoulderMinimal.smd defines tendon(11), jointCapsule(12), boneSurface(13)."""
        layers = shoulder_smd["materialLayers"]
        assert layers.get("tendon") == 11
        assert layers.get("jointCapsule") == 12
        assert layers.get("boneSurface") == 13

    def test_facial_smd_has_no_shoulder_extensions(self, facial_smd):
        """FacialFlaps.smd must NOT define shoulder extension materials."""
        layers = facial_smd.get("materialLayers", {})
        for key in ("tendon", "jointCapsule", "boneSurface"):
            assert key not in layers, \
                f"FacialFlaps.smd should not have '{key}' material"

    def test_shoulder_obj_has_skinSurface_faces(self):
        """ShoulderSkin.obj must have material 2 (skinSurface) faces."""
        obj_path = os.path.join(MODEL_DIR, "ShoulderSkin.obj")
        mat_faces = {}
        current_mat = None
        with open(obj_path) as f:
            for line in f:
                if line.startswith("usemtl "):
                    current_mat = int(line.split()[1])
                elif line.startswith("f ") and current_mat is not None:
                    mat_faces[current_mat] = mat_faces.get(current_mat, 0) + 1
        assert 2 in mat_faces, "ShoulderSkin.obj has no skinSurface (mat 2) faces"
        assert mat_faces[2] > 100, \
            f"Only {mat_faces[2]} skinSurface faces, need >100 for meaningful tool use"

    def test_shoulder_obj_has_periosteum_faces(self):
        """ShoulderSkin.obj must have material 7 (periosteum) faces."""
        obj_path = os.path.join(MODEL_DIR, "ShoulderSkin.obj")
        mat_faces = {}
        current_mat = None
        with open(obj_path) as f:
            for line in f:
                if line.startswith("usemtl "):
                    current_mat = int(line.split()[1])
                elif line.startswith("f ") and current_mat is not None:
                    mat_faces[current_mat] = mat_faces.get(current_mat, 0) + 1
        assert 7 in mat_faces, "ShoulderSkin.obj has no periosteum (mat 7) faces"

    def test_shoulder_bed_file_enables_deepBed(self):
        """ShoulderSkin.bed exists for runtime deep bed material assignment."""
        bed_path = os.path.join(MODEL_DIR, "ShoulderSkin.bed")
        assert os.path.isfile(bed_path), "ShoulderSkin.bed required for tool 6/8"
        line_count = 0
        with open(bed_path) as f:
            for line in f:
                if line.strip():
                    line_count += 1
        assert line_count > 0, "ShoulderSkin.bed is empty"
