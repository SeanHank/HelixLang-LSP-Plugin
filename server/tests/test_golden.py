"""Golden-file tests: every example must produce a recorded snapshot.

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


def _golden_path(example: str) -> str:
    name = os.path.basename(example).replace(".helix", ".json")
    return os.path.join(GOLDEN_DIR, name)


def _representative_position(ana) -> dict[str, int]:
    """A hover position: the first codon, else the first annotation."""
    codons = ana.structure.codon_tokens
    if codons:
        return {"line": codons[0].line0, "character": codons[0].col0 + 1}
    anns = ana.structure.annotations
    if anns:
        return {"line": anns[0].line0, "character": anns[0].col0 + 2}
    return {"line": 0, "character": 0}


# Every example must have a golden file; the upstream example set can grow
# beyond the original 20, so only a baseline floor is enforced here.
assert EXAMPLES, "no HelixLang examples found"
assert len(EXAMPLES) >= 20, "HelixLang example set shrank below the 20-example baseline"
missing = [os.path.basename(e) for e in EXAMPLES if not os.path.exists(_golden_path(e))]
assert not missing, f"examples missing golden files: {missing}"


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
    position = _representative_position(ana)
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
