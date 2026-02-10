#!/usr/bin/env python3
"""
Structural validation for SkinFlaps .hst (history) files.

History files are JSON arrays of action objects that record surgical procedures.
Each action object has exactly one key identifying its type, with the value
containing the action's parameters.

This validator checks:
  1. Valid JSON that deserializes to a top-level array
  2. First action is always "loadSceneFile"
  3. Every action object has exactly one recognized action key
  4. Required fields are present for each action type
  5. Coordinate values are within plausible ranges
  6. Array lengths match declared point counts
  7. Material IDs are within expected ranges

Supported action types (derived from surgicalActions::nextHistoryAction in
SkinFlaps/src/surgicalActions.cpp):
  - loadSceneFile                : string (scene filename, e.g. "FacialFlaps.smd")
  - addHook                      : object with material, hookNum, historyTexture, displacement
  - moveHook                     : array [hookNum, x, y, z]
  - deleteHook                   : int (hookNum)
  - makeIncision                 : array (header + incisionPoint objects)
  - undermine                    : array of underminePoint objects
  - excise                       : object with material, historyTexture, displacement
  - addSuture                    : object with sutureNum, linked, material0/1, historyTexture0/1, displacement0/1
  - deleteSuture                 : int or object with autoSuturesFor
  - makeDeepCut                  : array (header + deepCutPoint objects)
  - periostealUndermine          : array of periostealTriangle objects
  - promoteSutureApproximations  : int (value ignored by replay)
  - pausePhysics                 : int (value ignored by replay)

Usage:
    python3 validate_history.py                     # validate all files in ../History
    python3 validate_history.py /path/to/History     # validate all .hst in directory
    python3 validate_history.py /path/to/file.hst    # validate a single file
"""

import json
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# All recognized action types in the history replay system
KNOWN_ACTION_TYPES = {
    "loadSceneFile",
    "addHook",
    "moveHook",
    "deleteHook",
    "makeIncision",
    "undermine",
    "excise",
    "addSuture",
    "deleteSuture",
    "makeDeepCut",
    "periostealUndermine",
    "promoteSutureApproximations",
    "pausePhysics",
}

# Valid material IDs observed in the codebase:
#   2 = skin surface, 3-6 = other soft tissue, 7/8 = periosteal layers
VALID_MATERIALS = {2, 3, 4, 5, 6, 7, 8}

# Texture coordinates should normally be in [0, 1]
TEXTURE_MIN = 0.0
TEXTURE_MAX = 1.0

# Displacement values: generous range for physics-deformed coordinates
DISPLACEMENT_RANGE = 500.0


# ---------------------------------------------------------------------------
# Validation infrastructure
# ---------------------------------------------------------------------------

class ValidationError:
    """Represents a single validation issue."""
    def __init__(self, file_path, action_index, severity, message):
        self.file_path = file_path
        self.action_index = action_index
        self.severity = severity  # "ERROR" or "WARNING"
        self.message = message

    def __str__(self):
        loc = os.path.basename(self.file_path)
        if self.action_index is not None:
            loc += " [action %d]" % self.action_index
        return "  %s: %s: %s" % (self.severity, loc, self.message)


class HistoryValidator:
    """Validates a single .hst history file against the expected schema."""

    def __init__(self, file_path):
        self.file_path = str(file_path)
        self.errors = []
        self.warnings = []
        self.action_count = 0

    # -- helpers --

    def _add_error(self, action_index, message):
        self.errors.append(
            ValidationError(self.file_path, action_index, "ERROR", message)
        )

    def _add_warning(self, action_index, message):
        self.warnings.append(
            ValidationError(self.file_path, action_index, "WARNING", message)
        )

    def _validate_float_array(self, index, arr, expected_len, field_name):
        """Validate a numeric array of expected length. Returns True on success."""
        if not isinstance(arr, list):
            self._add_error(index,
                "%s must be an array, got %s" % (field_name, type(arr).__name__))
            return False
        if len(arr) != expected_len:
            self._add_error(index,
                "%s must have %d elements, got %d" % (field_name, expected_len, len(arr)))
            return False
        for i, v in enumerate(arr):
            if not isinstance(v, (int, float)):
                self._add_error(index,
                    "%s[%d] must be numeric, got %s" % (field_name, i, type(v).__name__))
                return False
        return True

    def _validate_texture_coords(self, index, arr, field_name):
        """Validate texture coordinates are in [0, 1] range."""
        if not self._validate_float_array(index, arr, 2, field_name):
            return
        for i, v in enumerate(arr):
            if v < TEXTURE_MIN or v > TEXTURE_MAX:
                self._add_warning(index,
                    "%s[%d] = %s is outside [0, 1] range" % (field_name, i, v))

    def _validate_displacement(self, index, arr, field_name):
        """Validate displacement vector is within plausible range."""
        if not self._validate_float_array(index, arr, 3, field_name):
            return
        for i, v in enumerate(arr):
            if abs(v) > DISPLACEMENT_RANGE:
                self._add_warning(index,
                    "%s[%d] = %s has unusually large magnitude" % (field_name, i, v))

    def _validate_material(self, index, material, field_name):
        """Validate material ID is an integer in the expected set."""
        if not isinstance(material, int):
            self._add_error(index,
                "%s must be an integer, got %s" % (field_name, type(material).__name__))
            return
        if material not in VALID_MATERIALS:
            self._add_warning(index,
                "%s = %d is not a commonly seen material ID" % (field_name, material))

    # -- top-level entry point --

    def validate(self):
        """Run all validation checks. Returns True if no errors found."""
        # Step 1: Load and parse JSON
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            self._add_error(None, "Invalid JSON: %s" % e)
            return False
        except IOError as e:
            self._add_error(None, "Cannot read file: %s" % e)
            return False

        # Step 2: Must be a top-level array
        if not isinstance(data, list):
            self._add_error(None,
                "Top-level structure must be a JSON array, got %s" % type(data).__name__)
            return False

        if len(data) == 0:
            self._add_error(None, "History file is empty (zero actions)")
            return False

        self.action_count = len(data)

        # Step 3: First action must be loadSceneFile
        first = data[0]
        if not isinstance(first, dict) or "loadSceneFile" not in first:
            self._add_error(0, "First action must be 'loadSceneFile'")

        # Step 4: Validate each action
        for i, action in enumerate(data):
            self._validate_action(i, action)

        return len(self.errors) == 0

    # -- per-action dispatch --

    def _validate_action(self, index, action):
        """Validate a single action object."""
        if not isinstance(action, dict):
            self._add_error(index,
                "Action must be a JSON object, got %s" % type(action).__name__)
            return

        keys = list(action.keys())
        if len(keys) == 0:
            self._add_error(index, "Action object has no keys")
            return

        if len(keys) > 1:
            self._add_warning(index,
                "Action object has multiple keys: %s (expected exactly one)" % keys)

        action_type = keys[0]
        if action_type not in KNOWN_ACTION_TYPES:
            self._add_error(index, "Unknown action type: '%s'" % action_type)
            return

        # Dispatch to type-specific validator
        validator_method = getattr(self, "_validate_%s" % action_type, None)
        if validator_method:
            validator_method(index, action[action_type])

    # -- type-specific validators --

    def _validate_loadSceneFile(self, index, value):
        """loadSceneFile must be a string ending in .smd"""
        if not isinstance(value, str):
            self._add_error(index,
                "loadSceneFile value must be a string, got %s" % type(value).__name__)
            return
        if not value.endswith(".smd"):
            self._add_warning(index,
                "loadSceneFile '%s' does not end with .smd" % value)

    def _validate_addHook(self, index, value):
        """addHook: object with material, hookNum, historyTexture[2], displacement[3].
        Optional field: strongHook (bool)."""
        if not isinstance(value, dict):
            self._add_error(index,
                "addHook value must be an object, got %s" % type(value).__name__)
            return
        required = {"material", "hookNum", "historyTexture", "displacement"}
        missing = required - set(value.keys())
        if missing:
            self._add_error(index, "addHook missing required fields: %s" % missing)
            return

        self._validate_material(index, value["material"], "addHook.material")
        if not isinstance(value["hookNum"], int):
            self._add_error(index, "addHook.hookNum must be an integer")
        self._validate_texture_coords(index, value["historyTexture"], "addHook.historyTexture")
        self._validate_displacement(index, value["displacement"], "addHook.displacement")

    def _validate_moveHook(self, index, value):
        """moveHook: array [hookNum, x, y, z]"""
        if not isinstance(value, list):
            self._add_error(index,
                "moveHook value must be an array, got %s" % type(value).__name__)
            return
        if len(value) != 4:
            self._add_error(index,
                "moveHook must have 4 elements [hookNum, x, y, z], got %d" % len(value))
            return
        if not isinstance(value[0], int):
            self._add_error(index, "moveHook[0] (hookNum) must be an integer")
        for i in range(1, 4):
            if not isinstance(value[i], (int, float)):
                self._add_error(index, "moveHook[%d] must be numeric" % i)

    def _validate_deleteHook(self, index, value):
        """deleteHook: integer (hookNum)"""
        if not isinstance(value, int):
            self._add_error(index,
                "deleteHook value must be an integer, got %s" % type(value).__name__)

    def _validate_makeIncision(self, index, value):
        """makeIncision: array with header object followed by incisionPoint objects.
        Header contains: Tin (bool), Tout (bool), incisedObject (int), pointNumber (int).
        Each point contains: incisionPoint.{material, historyTexture, displacement}."""
        if not isinstance(value, list):
            self._add_error(index,
                "makeIncision value must be an array, got %s" % type(value).__name__)
            return
        if len(value) < 2:
            self._add_error(index,
                "makeIncision must have at least 2 elements (header + points)")
            return

        # Validate header
        header = value[0]
        if not isinstance(header, dict):
            self._add_error(index, "makeIncision[0] (header) must be an object")
            return

        header_required = {"Tin", "Tout", "incisedObject", "pointNumber"}
        missing = header_required - set(header.keys())
        if missing:
            self._add_error(index,
                "makeIncision header missing fields: %s" % missing)
            return

        point_number = header.get("pointNumber", 0)
        if not isinstance(point_number, int) or point_number < 1:
            self._add_error(index,
                "makeIncision.pointNumber must be a positive integer, got %s" % point_number)
            return

        expected_total = point_number + 1  # header + N points
        if len(value) != expected_total:
            self._add_error(index,
                "makeIncision declares %d points but array has %d point entries"
                % (point_number, len(value) - 1))

        # Validate each incision point
        for i in range(1, min(len(value), expected_total)):
            pt = value[i]
            if not isinstance(pt, dict) or "incisionPoint" not in pt:
                self._add_error(index,
                    "makeIncision[%d] must contain 'incisionPoint'" % i)
                continue
            ip = pt["incisionPoint"]
            if not isinstance(ip, dict):
                self._add_error(index,
                    "makeIncision[%d].incisionPoint must be an object" % i)
                continue
            ip_required = {"material", "historyTexture", "displacement"}
            ip_missing = ip_required - set(ip.keys())
            if ip_missing:
                self._add_error(index,
                    "makeIncision[%d].incisionPoint missing fields: %s" % (i, ip_missing))
                continue
            self._validate_material(
                index, ip["material"], "makeIncision[%d].material" % i)
            self._validate_texture_coords(
                index, ip["historyTexture"], "makeIncision[%d].historyTexture" % i)
            self._validate_displacement(
                index, ip["displacement"], "makeIncision[%d].displacement" % i)

    def _validate_undermine(self, index, value):
        """undermine: array of objects each containing 'underminePoint'.
        Each underminePoint has: material, historyTexture, displacement.
        Optional field: incisionConnect (bool)."""
        if not isinstance(value, list):
            self._add_error(index,
                "undermine value must be an array, got %s" % type(value).__name__)
            return
        if len(value) == 0:
            self._add_warning(index, "undermine array is empty")
            return

        for i, item in enumerate(value):
            if not isinstance(item, dict) or "underminePoint" not in item:
                self._add_error(index,
                    "undermine[%d] must contain 'underminePoint'" % i)
                continue
            up = item["underminePoint"]
            if not isinstance(up, dict):
                self._add_error(index,
                    "undermine[%d].underminePoint must be an object" % i)
                continue
            up_required = {"material", "historyTexture", "displacement"}
            up_missing = up_required - set(up.keys())
            if up_missing:
                self._add_error(index,
                    "undermine[%d].underminePoint missing fields: %s" % (i, up_missing))
                continue
            self._validate_material(
                index, up["material"], "undermine[%d].material" % i)
            self._validate_texture_coords(
                index, up["historyTexture"], "undermine[%d].historyTexture" % i)
            self._validate_displacement(
                index, up["displacement"], "undermine[%d].displacement" % i)

    def _validate_excise(self, index, value):
        """excise: object with material, historyTexture, displacement."""
        if not isinstance(value, dict):
            self._add_error(index,
                "excise value must be an object, got %s" % type(value).__name__)
            return
        required = {"material", "historyTexture", "displacement"}
        missing = required - set(value.keys())
        if missing:
            self._add_error(index, "excise missing required fields: %s" % missing)
            return
        self._validate_material(index, value["material"], "excise.material")
        self._validate_texture_coords(
            index, value["historyTexture"], "excise.historyTexture")
        self._validate_displacement(
            index, value["displacement"], "excise.displacement")

    def _validate_addSuture(self, index, value):
        """addSuture: object with paired attachment points.
        Required fields: sutureNum, linked, material0, historyTexture0, displacement0,
                         material1, historyTexture1, displacement1."""
        if not isinstance(value, dict):
            self._add_error(index,
                "addSuture value must be an object, got %s" % type(value).__name__)
            return
        required = {
            "sutureNum", "linked",
            "material0", "historyTexture0", "displacement0",
            "material1", "historyTexture1", "displacement1",
        }
        missing = required - set(value.keys())
        if missing:
            self._add_error(index, "addSuture missing required fields: %s" % missing)
            return

        if not isinstance(value["sutureNum"], int):
            self._add_error(index, "addSuture.sutureNum must be an integer")
        if not isinstance(value["linked"], bool):
            self._add_error(index, "addSuture.linked must be a boolean")

        for side in ("0", "1"):
            self._validate_material(
                index, value["material%s" % side], "addSuture.material%s" % side)
            self._validate_texture_coords(
                index, value["historyTexture%s" % side],
                "addSuture.historyTexture%s" % side)
            self._validate_displacement(
                index, value["displacement%s" % side],
                "addSuture.displacement%s" % side)

    def _validate_deleteSuture(self, index, value):
        """deleteSuture: int (suture number) or object with autoSuturesFor (int)."""
        if isinstance(value, int):
            return  # simple form is valid
        if isinstance(value, dict):
            if "autoSuturesFor" not in value:
                self._add_error(index,
                    "deleteSuture object must contain 'autoSuturesFor'")
            elif not isinstance(value["autoSuturesFor"], int):
                self._add_error(index,
                    "deleteSuture.autoSuturesFor must be an integer")
        else:
            self._add_error(index,
                "deleteSuture must be int or object, got %s" % type(value).__name__)

    def _validate_makeDeepCut(self, index, value):
        """makeDeepCut: array with header object followed by deepCutPoint objects.
        Header contains: deepCutObject (int), openIn (bool), openOut (bool), pointNumber (int).
        Each point contains: deepCutPoint.{material, historyTexture, displacement, postNormal}."""
        if not isinstance(value, list):
            self._add_error(index,
                "makeDeepCut value must be an array, got %s" % type(value).__name__)
            return
        if len(value) < 2:
            self._add_error(index,
                "makeDeepCut must have at least 2 elements (header + points)")
            return

        header = value[0]
        if not isinstance(header, dict):
            self._add_error(index, "makeDeepCut[0] (header) must be an object")
            return

        header_required = {"deepCutObject", "openIn", "openOut", "pointNumber"}
        missing = header_required - set(header.keys())
        if missing:
            self._add_error(index,
                "makeDeepCut header missing fields: %s" % missing)
            return

        point_number = header.get("pointNumber", 0)
        if not isinstance(point_number, int) or point_number < 1:
            self._add_error(index,
                "makeDeepCut.pointNumber must be a positive integer, got %s"
                % point_number)
            return

        expected_total = point_number + 1
        if len(value) != expected_total:
            self._add_error(index,
                "makeDeepCut declares %d points but array has %d point entries"
                % (point_number, len(value) - 1))

        for i in range(1, min(len(value), expected_total)):
            pt = value[i]
            if not isinstance(pt, dict) or "deepCutPoint" not in pt:
                self._add_error(index,
                    "makeDeepCut[%d] must contain 'deepCutPoint'" % i)
                continue
            dp = pt["deepCutPoint"]
            if not isinstance(dp, dict):
                self._add_error(index,
                    "makeDeepCut[%d].deepCutPoint must be an object" % i)
                continue
            dp_required = {"material", "historyTexture", "displacement", "postNormal"}
            dp_missing = dp_required - set(dp.keys())
            if dp_missing:
                self._add_error(index,
                    "makeDeepCut[%d].deepCutPoint missing fields: %s" % (i, dp_missing))
                continue
            self._validate_material(
                index, dp["material"], "makeDeepCut[%d].material" % i)
            self._validate_texture_coords(
                index, dp["historyTexture"], "makeDeepCut[%d].historyTexture" % i)
            self._validate_displacement(
                index, dp["displacement"], "makeDeepCut[%d].displacement" % i)
            self._validate_float_array(
                index, dp["postNormal"], 3, "makeDeepCut[%d].postNormal" % i)

    def _validate_periostealUndermine(self, index, value):
        """periostealUndermine: array of objects each containing 'periostealTriangle'.
        Each periostealTriangle has: material, historyTexture, displacement.
        Optional field: incisionConnect (bool)."""
        if not isinstance(value, list):
            self._add_error(index,
                "periostealUndermine value must be an array, got %s"
                % type(value).__name__)
            return
        if len(value) == 0:
            self._add_warning(index, "periostealUndermine array is empty")
            return

        for i, item in enumerate(value):
            if not isinstance(item, dict) or "periostealTriangle" not in item:
                self._add_error(index,
                    "periostealUndermine[%d] must contain 'periostealTriangle'" % i)
                continue
            pt = item["periostealTriangle"]
            if not isinstance(pt, dict):
                self._add_error(index,
                    "periostealUndermine[%d].periostealTriangle must be an object" % i)
                continue
            pt_required = {"material", "historyTexture", "displacement"}
            pt_missing = pt_required - set(pt.keys())
            if pt_missing:
                self._add_error(index,
                    "periostealUndermine[%d].periostealTriangle missing fields: %s"
                    % (i, pt_missing))
                continue
            self._validate_material(
                index, pt["material"],
                "periostealUndermine[%d].material" % i)
            self._validate_texture_coords(
                index, pt["historyTexture"],
                "periostealUndermine[%d].historyTexture" % i)
            self._validate_displacement(
                index, pt["displacement"],
                "periostealUndermine[%d].displacement" % i)

    def _validate_promoteSutureApproximations(self, index, value):
        """promoteSutureApproximations: integer (value is ignored by replay)."""
        if not isinstance(value, int):
            self._add_warning(index,
                "promoteSutureApproximations value should be int, got %s"
                % type(value).__name__)

    def _validate_pausePhysics(self, index, value):
        """pausePhysics: integer (value is ignored by replay)."""
        if not isinstance(value, int):
            self._add_warning(index,
                "pausePhysics value should be int, got %s" % type(value).__name__)


# ---------------------------------------------------------------------------
# File and directory validation entry points
# ---------------------------------------------------------------------------

def validate_file(file_path):
    """Validate a single .hst file. Returns (success, validator)."""
    validator = HistoryValidator(file_path)
    success = validator.validate()
    return success, validator


def validate_directory(dir_path):
    """Validate all .hst files in a directory. Returns overall success."""
    hst_files = sorted(Path(dir_path).glob("*.hst"))

    if not hst_files:
        print("  No .hst files found in %s" % dir_path)
        return False

    total_errors = 0
    total_warnings = 0
    total_actions = 0
    all_passed = True

    for hst_file in hst_files:
        success, validator = validate_file(str(hst_file))
        total_actions += validator.action_count

        filename = hst_file.name
        n_err = len(validator.errors)
        n_warn = len(validator.warnings)
        total_errors += n_err
        total_warnings += n_warn

        status = "PASS" if success else "FAIL"
        detail = "%d actions" % validator.action_count
        if n_warn > 0:
            detail += ", %d warning(s)" % n_warn
        if n_err > 0:
            detail += ", %d error(s)" % n_err

        print("  %s: %s (%s)" % (filename, status, detail))

        if not success:
            all_passed = False
            for err in validator.errors:
                print("    %s" % err)
        for warn in validator.warnings:
            print("    %s" % warn)

    print("")
    print("  Summary: %d files, %d total actions, %d error(s), %d warning(s)"
          % (len(hst_files), total_actions, total_errors, total_warnings))

    return all_passed


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def find_history_dir():
    """Locate the History/ directory relative to this script."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    history_dir = os.path.join(repo_root, "History")
    if os.path.isdir(history_dir):
        return history_dir

    # Fallback: try current working directory
    cwd_history = os.path.join(os.getcwd(), "History")
    if os.path.isdir(cwd_history):
        return cwd_history

    return None


def main():
    if len(sys.argv) >= 2:
        target = sys.argv[1]
    else:
        target = find_history_dir()
        if target is None:
            print("ERROR: Could not find History/ directory.", file=sys.stderr)
            print("  Looked relative to script and current working directory.",
                  file=sys.stderr)
            sys.exit(1)

    if os.path.isfile(target):
        success, validator = validate_file(target)
        filename = os.path.basename(target)
        status = "PASS" if success else "FAIL"
        detail = "%d actions" % validator.action_count
        if len(validator.warnings) > 0:
            detail += ", %d warning(s)" % len(validator.warnings)
        if len(validator.errors) > 0:
            detail += ", %d error(s)" % len(validator.errors)
        print("  %s: %s (%s)" % (filename, status, detail))
        if not success:
            for err in validator.errors:
                print("    %s" % err)
        for warn in validator.warnings:
            print("    %s" % warn)
        sys.exit(0 if success else 1)

    elif os.path.isdir(target):
        print("Validating history files in %s ..." % target)
        success = validate_directory(target)
        if success:
            print("")
            print("All history file structural validation tests passed.")
        sys.exit(0 if success else 1)

    else:
        print("ERROR: %s is neither a file nor a directory" % target,
              file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
