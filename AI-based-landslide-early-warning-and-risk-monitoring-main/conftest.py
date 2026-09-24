"""Pytest bootstrap for the monorepo.

The three Python packages live one directory down from the repository root
(`api/app`, `ingest/ingest`, `ml/ml`). Their parent directories therefore have
to be on `sys.path` before anything is imported.

The explicit insert matters because the repository root is itself on the path
during collection, and from there the outer `ingest/` folder looks like a
namespace package containing only `ingest` and `tests`. Importing
`ingest.terrain` then fails with ModuleNotFoundError even though the module
exists, because the namespace package shadows the real one. Putting the source
roots first resolves each name to the regular package that owns it.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent
SOURCE_ROOTS = ("api", "ingest", "ml")

for name in SOURCE_ROOTS:
    path = str((ROOT / name).resolve())
    if path in sys.path:
        sys.path.remove(path)
    sys.path.insert(0, path)
