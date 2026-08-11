"""``python -m helixlang_lsp`` entry point.

The IDE client launches the server as ``<python> -m helixlang_lsp --stdio``
(doc/04 §4.2), so the package must be directly executable via ``-m``.
"""

import sys

from helixlang_lsp.main import main

if __name__ == "__main__":
    sys.exit(main())
