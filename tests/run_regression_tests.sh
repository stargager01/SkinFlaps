#!/bin/bash
# Regression test runner for SkinFlaps history files
# Tests that each history file can be loaded and parsed without errors
# (Full simulation replay requires the OpenGL context and is tested separately)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HISTORY_DIR="$SCRIPT_DIR/../History"
PASS=0
FAIL=0
ERRORS=""

echo "=== SkinFlaps Regression Test Suite ==="
echo "Testing history files in: $HISTORY_DIR"
echo ""

# Phase 1: JSON validation (can run headless)
echo "--- Phase 1: JSON Structure Validation ---"
echo ""

if [ ! -d "$HISTORY_DIR" ]; then
    echo "FATAL: History directory not found at $HISTORY_DIR"
    exit 1
fi

hst_count=0
for hst_file in "$HISTORY_DIR"/*.hst; do
    [ -f "$hst_file" ] || continue
    hst_count=$((hst_count + 1))
    filename=$(basename "$hst_file")
    echo -n "  Testing $filename ... "

    # Validate JSON structure
    if python3 -c "import json; json.load(open('$hst_file'))" 2>/dev/null; then
        echo "PASS (valid JSON)"
        PASS=$((PASS + 1))
    else
        echo "FAIL (invalid JSON)"
        FAIL=$((FAIL + 1))
        ERRORS="$ERRORS\n  - $filename: invalid JSON structure"
    fi
done

if [ "$hst_count" -eq 0 ]; then
    echo "WARNING: No .hst files found in $HISTORY_DIR"
    exit 1
fi

echo ""
echo "--- Phase 2: Structural Validation ---"
echo ""

# Phase 2: Deep structural validation via Python
if command -v python3 &>/dev/null; then
    if python3 "$SCRIPT_DIR/validate_history.py" "$HISTORY_DIR"; then
        echo "  Structural validation: PASS"
    else
        echo "  Structural validation: FAIL"
        FAIL=$((FAIL + 1))
        ERRORS="$ERRORS\n  - Structural validation failed (see above)"
    fi
else
    echo "  WARNING: python3 not found, skipping structural validation"
fi

echo ""
echo "=== Results ==="
echo "JSON Validation - Passed: $PASS  Failed: $FAIL  Total files: $hst_count"

if [ "$FAIL" -gt 0 ]; then
    echo -e "\nFailures:$ERRORS"
    exit 1
fi

echo ""
echo "All history file validation tests passed."
exit 0
