"""Generate golden snapshots for all HelixLang examples.

Writes ``tests/golden/<nn_name>.json`` containing the publishDiagnostics
snapshot (expected zero errors) and a hover snapshot at a representative
position (first codon, else first annotation).

Run: /opt/anaconda3/envs/helix/bin/python tests/generate_golden.py
"""

from __future__ import annotations

import glob
import json
import os
from typing import Any

from helixlang_lsp.analysis import analyze
from helixlang_lsp.features.hover import hover

EXAMPLES_DIR = os.environ.get(
    "HELIX_EXAMPLES_DIR", "/Users/admin/PycharmProjects/HelixLang/examples")
GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")


def representative_position(ana: Any) -> dict[str, int]:
    """A hover position: the first codon, else the first annotation."""
    codons = ana.structure.codon_tokens
    if codons:
        return {"line": codons[0].line0, "character": codons[0].col0 + 1}
    anns = ana.structure.annotations
    if anns:
        return {"line": anns[0].line0, "character": anns[0].col0 + 2}
    return {"line": 0, "character": 0}


def main() -> None:
    os.makedirs(GOLDEN_DIR, exist_ok=True)
    for path in sorted(glob.glob(os.path.join(EXAMPLES_DIR, "*.helix"))):
        uri = "file://" + path
        text = open(path, encoding="utf-8").read()
        ana = analyze(text, uri=uri)
        position = representative_position(ana)
        hover_result = hover(text, ana, {"position": position})
        snapshot = {
            "file": os.path.basename(path),
            "uri": uri,
            "diagnostics": [d.to_dict() for d in ana.diagnostics],
            "hover_position": position,
            "hover": hover_result,
        }
        out = os.path.join(GOLDEN_DIR, os.path.basename(path).replace(".helix", ".json"))
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(snapshot, fh, indent=2, ensure_ascii=False)
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
