"""Golden-file tests: 20 examples must produce the recorded snapshots.

Each golden file records the publishDiagnostics payload (expected zero errors)
and a hover snapshot at a representative codon position (doc/03 §13).
"""

from __future__ import annotations

import glob
import json
import os

import pytest
from helixlang_lsp.analysis import analyze
from helixlang_lsp.features.hover import hover

EXAMPLES_DIR = os.environ.get(
    "HELIX_EXAMPLES_DIR", "/Users/admin/PycharmProjects/HelixLang/examples")
EXAMPLES = sorted(glob.glob(os.path.join(EXAMPLES_DIR, "*.helix")))
GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")

# every example must have a golden file
assert EXAMPLES, "no HelixLang examples found"
assert len(EXAMPLES) == 20


def _golden_path(example: str) -> str:
    name = os.path.basename(example).replace(".helix", ".json")
    return os.path.join(GOLDEN_DIR, name)


@pytest.mark.parametrize("path", EXAMPLES)
def test_example_zero_errors(path: str):
    text = open(path, encoding="utf-8").read()
    ana = analyze(text, uri="file://" + path)
    errors = [d for d in ana.diagnostics if d.severity == 1]
    assert errors == [], f"{os.path.basename(path)}: {errors}"


@pytest.mark.parametrize("path", EXAMPLES)
def test_golden_snapshot_matches(path: str):
    text = open(path, encoding="utf-8").read()
    ana = analyze(text, uri="file://" + path)
    codons = ana.structure.codon_tokens
    position = {"line": codons[0].line0, "character": codons[0].col0 + 1} \
        if codons else {"line": 0, "character": 0}
    hover_result = hover(text, ana, {"position": position})
    current = {
        "diagnostics": [d.to_dict() for d in ana.diagnostics],
        "hover": hover_result,
    }
    with open(_golden_path(path), encoding="utf-8") as fh:
        golden = json.load(fh)
    assert current == {
        "diagnostics": golden["diagnostics"],
        "hover": golden["hover"],
    }, f"{os.path.basename(path)} drifted from golden snapshot"


@pytest.mark.parametrize("path", EXAMPLES)
def test_golden_hover_is_meaningful(path: str):
    with open(_golden_path(path), encoding="utf-8") as fh:
        golden = json.load(fh)
    hov = golden["hover"]
    assert hov is not None
    value = hov["contents"]["value"]
    assert value and len(value) > 20
