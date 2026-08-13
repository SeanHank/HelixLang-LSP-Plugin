# HelixLang-LSP

Language Server Protocol (LSP) server for the **[HelixLang](https://github.com/SeanHank/HelixLang)**
domain-specific language (`.helix`).

It powers the **HelixLang IDE** plugin for PyCharm 2022.2+ — providing live
diagnostics, hover documentation, completion, navigation, structure view,
semantic tokens, inlay hints, folding, code actions, and formatting for HelixLang
source files.

## Installation

```bash
pip install helixlang-lsp
```

Requires Python 3.11+. The `helixlang` compiler/VM is pulled in automatically as
a dependency.

## Usage

Run the server standalone over stdio (the default):

```bash
helixlang-lsp --stdio
```

Or over TCP:

```bash
helixlang-lsp --host 127.0.0.1 --port 4389
```

### Command line options

| Option | Description |
|--------|-------------|
| `--stdio` | Serve over stdio (default) |
| `--host HOST` / `--port PORT` | Serve over TCP |
| `--dap` / `--dap-port PORT` | Debug adapter (DAP) mode |
| `--trace TRACE` | LSP trace level (`off`, `messages`, `verbose`) |
| `--loglevel {DEBUG,INFO,WARNING,ERROR}` | Logging verbosity |

## Features

- Publish diagnostics (errors & warnings)
- Hover documentation
- Completion with `#`, `=` and `>` triggers
- Go to definition & find references
- Document & workspace symbols
- Folding ranges
- Semantic tokens (keyword / type / function / variable / number / string / comment / operator / arrow)
- Quick-fix code actions
- Document formatting
- Inlay hints

## Development

```bash
git clone https://github.com/SeanHank/HelixLang-LSP-Plugin.git
cd HelixLang-LSP-Plugin
python -m pip install -e "server[dev]"

# Quality gates
cd server
python -m ruff check .
python -m mypy helixlang_lsp
python -m pytest tests --cov=helixlang_lsp --cov-fail-under=85
```

See the project's [CONTRIBUTING.md](https://github.com/SeanHank/HelixLang-LSP-Plugin/CONTRIBUTING.md) for details.

## License

This project is licensed under the **GNU Affero General Public License v3.0** (AGPLv3).

Copyright © 2026 Sean Hank.