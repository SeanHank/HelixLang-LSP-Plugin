"""Generate golden snapshots for the 20 HelixLang examples.

Writes ``tests/golden/<nn_name>.json`` containing the publishDiagnostics
snapshot (expected zero errors) and a hover snapshot at the first codon.

Run: /opt/anaconda3/envs/helix/bin/python tests/generate_golden.py
"""

from __future__ import annotations

import glob
import json
import os

from helixlang_lsp.analysis import analyze
from helixlang_lsp.features.hover import hover

EXAMPLES_DIR = os.environ.get(
    "HELIX_EXAMPLES_DIR", "/Users/admin/PycharmProjects/HelixLang/examples")
GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")


def main() -> None:
    os.makedirs(GOLDEN_DIR, exist_ok=True)
    for path in sorted(glob.glob(os.path.join(EXAMPLES_DIR, "*.helix"))):
        uri = "file://" + path
        text = open(path, encoding="utf-8").read()
        ana = analyze(text, uri=uri)
        codons = ana.structure.codon_tokens
        position = {"line": codons[0].line0, "character": codons[0].col0 + 1} \
            if codons else {"line": 0, "character": 0}
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
